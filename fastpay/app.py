from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from uuid import uuid4

from fastpay.gateway import GatewayError, GatewayTimeout, authorize
from fastpay.logging_utils import sanitize_payload

logger = logging.getLogger("fastpay.api")

REQUIRED_FIELDS = {"card_number", "expiry", "cvv", "amount", "merchant_id"}
EXPIRY_RE = re.compile(r"^(0[1-9]|1[0-2])/\d{2}$")


def validate_payment_payload(payload: dict[str, Any]) -> tuple[bool, str | None]:
    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        return False, f"Missing required fields: {', '.join(sorted(missing))}"

    pan = str(payload["card_number"])
    if not pan.isdigit() or not 13 <= len(pan) <= 19:
        return False, "Invalid card_number"

    expiry = str(payload["expiry"])
    if not EXPIRY_RE.match(expiry):
        return False, "Invalid expiry format; expected MM/YY"

    cvv = str(payload["cvv"])
    if not cvv.isdigit() or len(cvv) not in {3, 4}:
        return False, "Invalid CVV"

    try:
        amount = Decimal(str(payload["amount"]))
    except (InvalidOperation, ValueError):
        return False, "Invalid amount"
    if amount <= 0:
        return False, "Amount must be positive"

    if not str(payload["merchant_id"]).strip():
        return False, "Invalid merchant_id"

    return True, None


def create_payment(payload: dict[str, Any]) -> tuple[dict[str, Any], HTTPStatus]:
    """Main FastPay use case behind POST /v1/payment."""
    logger.info("Payment request received: %s", sanitize_payload(payload))

    is_valid, error = validate_payment_payload(payload)
    if not is_valid:
        logger.info("Payment validation failed: %s payload=%s", error, sanitize_payload(payload))
        return {"transaction_id": None, "status": "validation_error", "error": error}, HTTPStatus.BAD_REQUEST

    try:
        gateway_response = authorize(payload)
    except GatewayTimeout:
        return {
            "transaction_id": None,
            "status": "gateway_timeout",
            "error": "Bank gateway did not respond after retry",
        }, HTTPStatus.GATEWAY_TIMEOUT
    except GatewayError:
        return {
            "transaction_id": None,
            "status": "gateway_error",
            "error": "Bank gateway technical error",
        }, HTTPStatus.BAD_GATEWAY

    gateway_status = gateway_response.get("status")
    transaction_id = gateway_response.get("transaction_id") or f"txn_{uuid4().hex[:12]}"

    if gateway_status in {"approved", "authorized"}:
        return {"transaction_id": transaction_id, "status": "authorized"}, HTTPStatus.OK

    if gateway_status == "declined":
        return {
            "transaction_id": transaction_id,
            "status": "declined",
            "reason": gateway_response.get("reason", "unknown"),
        }, HTTPStatus.OK

    return {
        "transaction_id": transaction_id,
        "status": "gateway_error",
        "error": "Unknown gateway response",
    }, HTTPStatus.BAD_GATEWAY


class FastPayHandler(BaseHTTPRequestHandler):
    """Small HTTP API used by integration tests.

    A real project would likely use FastAPI, Flask, Django, or aiohttp. Here the
    standard library keeps the assignment self-contained while still testing via
    real HTTP calls made with requests.
    """

    server_version = "FastPayDemo/1.0"

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/v1/payment":
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"transaction_id": None, "status": "validation_error", "error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        body, status = create_payment(payload)
        self._send_json(body, status)

    def log_message(self, format: str, *args: Any) -> None:
        # Route server access logs through Python logging. Request body is not logged.
        logging.getLogger("fastpay.http").info(format, *args)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
