from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import requests

from fastpay.config import BANK_GATEWAY_URL, REQUEST_TIMEOUT_SECONDS, RETRY_COUNT
from fastpay.logging_utils import sanitize_payload

logger = logging.getLogger("fastpay.gateway")


class GatewayTimeout(RuntimeError):
    """Raised when the external bank gateway does not respond after retries."""


class GatewayError(RuntimeError):
    """Raised when the external bank gateway returns a technical error."""


def build_gateway_payload(payment: dict[str, Any]) -> dict[str, Any]:
    """Map FastPay API fields to a bank gateway authorization request."""
    return {
        "pan": payment["card_number"],
        "expiry": payment["expiry"],
        "cvv": payment["cvv"],
        "amount": str(Decimal(str(payment["amount"]))),
        "merchant_id": payment["merchant_id"],
    }


def authorize(payment: dict[str, Any], *, retries: int = RETRY_COUNT) -> dict[str, Any]:
    """Authorize a payment through an external bank gateway.

    The function retries only transport timeouts. Business declines are returned
    as normal responses because they are expected payment outcomes.
    """
    gateway_payload = build_gateway_payload(payment)

    for attempt in range(retries + 1):
        try:
            logger.info(
                "Calling bank gateway, attempt=%s payload=%s",
                attempt + 1,
                sanitize_payload(gateway_payload),
            )
            response = requests.post(
                BANK_GATEWAY_URL,
                json=gateway_payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code >= 500:
                raise GatewayError(f"Gateway technical error: HTTP {response.status_code}")
            return response.json()
        except requests.Timeout as exc:
            logger.warning("Bank gateway timeout on attempt=%s", attempt + 1)
            if attempt >= retries:
                raise GatewayTimeout("Bank gateway timeout after retry") from exc

    raise GatewayTimeout("Bank gateway timeout after retry")
