from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests


def api_post(url: str, **kwargs):
    """Use a Session so patching fastpay.gateway.requests.post does not mock the test client."""
    return requests.Session().post(url, **kwargs)

VALID_PAYMENT = {
    "card_number": "4111111111111111",
    "expiry": "12/30",
    "cvv": "123",
    "amount": "100.00",
    "merchant_id": "m_1001",
}


def gateway_response(status_code: int, body: dict) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = body
    return response


def test_successful_authorization(fastpay_server):
    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(
            200,
            {"transaction_id": "bank_txn_001", "status": "approved"},
        )

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    assert response.status_code == 200
    assert response.json() == {"transaction_id": "bank_txn_001", "status": "authorized"}
    bank_post.assert_called_once()


def test_insufficient_funds_returns_declined(fastpay_server):
    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(
            200,
            {
                "transaction_id": "bank_txn_002",
                "status": "declined",
                "reason": "insufficient_funds",
            },
        )

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    assert response.status_code == 200
    assert response.json()["transaction_id"] == "bank_txn_002"
    assert response.json()["status"] == "declined"
    assert response.json()["reason"] == "insufficient_funds"
    bank_post.assert_called_once()


@pytest.mark.parametrize("bad_cvv", ["", "12", "12345", "12a", None])
def test_invalid_cvv_validation_error_and_no_gateway_call(fastpay_server, bad_cvv):
    payload = {**VALID_PAYMENT, "cvv": bad_cvv}

    with patch("fastpay.gateway.requests.post") as bank_post:
        response = api_post(f"{fastpay_server}/v1/payment", json=payload, timeout=2)

    assert response.status_code == 400
    assert response.json()["status"] == "validation_error"
    assert "CVV" in response.json()["error"]
    bank_post.assert_not_called()


def test_gateway_timeout_is_retried_then_authorized(fastpay_server):
    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.side_effect = [
            requests.Timeout("network timeout"),
            gateway_response(200, {"transaction_id": "bank_txn_003", "status": "approved"}),
        ]

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=3)

    assert response.status_code == 200
    assert response.json() == {"transaction_id": "bank_txn_003", "status": "authorized"}
    assert bank_post.call_count == 2


def test_gateway_timeout_after_retry_returns_504(fastpay_server):
    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.side_effect = [
            requests.Timeout("network timeout 1"),
            requests.Timeout("network timeout 2"),
        ]

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=3)

    assert response.status_code == 504
    assert response.json()["status"] == "gateway_timeout"
    assert bank_post.call_count == 2


def test_pan_and_cvv_are_not_written_to_logs(fastpay_server, caplog):
    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(
            200,
            {"transaction_id": "bank_txn_004", "status": "approved"},
        )

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    assert response.status_code == 200
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert VALID_PAYMENT["card_number"] not in log_text
    assert VALID_PAYMENT["cvv"] not in log_text
    assert "411111******1111" in log_text
    assert "***" in log_text
