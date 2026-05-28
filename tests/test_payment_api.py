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


def show_demo_case(title: str, checking: str, expected: str) -> None:
    """Print a readable test card for CI demo output."""
    print("\n" + "=" * 78)
    print(f"SCENARIO: {title}")
    print(f"CHECKING: {checking}")
    print(f"EXPECTED: {expected}")
    print("=" * 78)


def show_actual_response(response, bank_post: Mock | None = None) -> None:
    """Print the actual API response and mocked gateway calls for CI demo output."""
    print(f"ACTUAL HTTP STATUS: {response.status_code}")
    try:
        print(f"ACTUAL RESPONSE: {response.json()}")
    except ValueError:
        print(f"ACTUAL RESPONSE TEXT: {response.text}")
    if bank_post is not None:
        print(f"MOCKED BANK CALLS: {bank_post.call_count}")


def gateway_response(status_code: int, body: dict) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = body
    return response


def test_successful_authorization(fastpay_server):
    show_demo_case(
        "Successful payment authorization",
        "FastPay sends valid payment data to the mocked bank gateway.",
        "HTTP 200, status=authorized, transaction_id from the bank, gateway called once.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(
            200,
            {"transaction_id": "bank_txn_001", "status": "approved"},
        )

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 200
    assert response.json() == {"transaction_id": "bank_txn_001", "status": "authorized"}
    bank_post.assert_called_once()


def test_insufficient_funds_returns_declined(fastpay_server):
    show_demo_case(
        "Bank declines payment because of insufficient funds",
        "FastPay receives a business decline from the mocked bank gateway.",
        "HTTP 200, status=declined, reason=insufficient_funds, no false authorization.",
    )

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

    show_actual_response(response, bank_post)

    assert response.status_code == 200
    assert response.json()["transaction_id"] == "bank_txn_002"
    assert response.json()["status"] == "declined"
    assert response.json()["reason"] == "insufficient_funds"
    bank_post.assert_called_once()


def test_bank_approved_without_transaction_id_generates_local_id(fastpay_server):
    show_demo_case(
        "Bank approves payment without transaction_id",
        "FastPay receives approved from bank, but the gateway response has no transaction_id.",
        "HTTP 200, status=authorized, FastPay generates a local txn_* identifier.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(200, {"status": "approved"})

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 200
    assert response.json()["status"] == "authorized"
    assert response.json()["transaction_id"].startswith("txn_")
    bank_post.assert_called_once()


@pytest.mark.parametrize("bad_cvv", ["", "12", "12345", "12a", None])
def test_invalid_cvv_validation_error_and_no_gateway_call(fastpay_server, bad_cvv):
    show_demo_case(
        f"CVV validation rejects invalid value: {bad_cvv!r}",
        "FastPay validates CVV before calling the external bank.",
        "HTTP 400, status=validation_error, mocked bank gateway is not called.",
    )

    payload = {**VALID_PAYMENT, "cvv": bad_cvv}

    with patch("fastpay.gateway.requests.post") as bank_post:
        response = api_post(f"{fastpay_server}/v1/payment", json=payload, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 400
    assert response.json()["status"] == "validation_error"
    assert "CVV" in response.json()["error"]
    bank_post.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("amount", "0", "Amount must be positive"),
        ("amount", "-10.00", "Amount must be positive"),
        ("amount", "not-a-number", "Invalid amount"),
        ("expiry", "13/30", "Invalid expiry"),
        ("merchant_id", "   ", "Invalid merchant_id"),
    ],
)
def test_invalid_payment_payload_returns_400_without_gateway_call(
    fastpay_server,
    field,
    value,
    expected_error,
):
    show_demo_case(
        f"Payload validation rejects invalid {field}: {value!r}",
        "FastPay validates payment fields before calling the external bank.",
        f"HTTP 400, error contains {expected_error!r}, mocked bank gateway is not called.",
    )

    payload = {**VALID_PAYMENT, field: value}

    with patch("fastpay.gateway.requests.post") as bank_post:
        response = api_post(f"{fastpay_server}/v1/payment", json=payload, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 400
    assert response.json()["status"] == "validation_error"
    assert expected_error in response.json()["error"]
    bank_post.assert_not_called()


def test_missing_required_field_returns_400_without_gateway_call(fastpay_server):
    show_demo_case(
        "Payload validation rejects missing required field",
        "FastPay receives a request without merchant_id.",
        "HTTP 400, status=validation_error, mocked bank gateway is not called.",
    )

    payload = {key: value for key, value in VALID_PAYMENT.items() if key != "merchant_id"}

    with patch("fastpay.gateway.requests.post") as bank_post:
        response = api_post(f"{fastpay_server}/v1/payment", json=payload, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 400
    assert response.json()["status"] == "validation_error"
    assert "merchant_id" in response.json()["error"]
    bank_post.assert_not_called()


def test_gateway_timeout_is_retried_then_authorized(fastpay_server):
    show_demo_case(
        "Gateway timeout is retried and then succeeds",
        "The first mocked bank call raises timeout, the second returns approved.",
        "HTTP 200, status=authorized, exactly two gateway calls.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.side_effect = [
            requests.Timeout("network timeout"),
            gateway_response(200, {"transaction_id": "bank_txn_003", "status": "approved"}),
        ]

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=3)

    show_actual_response(response, bank_post)

    assert response.status_code == 200
    assert response.json() == {"transaction_id": "bank_txn_003", "status": "authorized"}
    assert bank_post.call_count == 2


def test_gateway_timeout_after_retry_returns_504(fastpay_server):
    show_demo_case(
        "Gateway timeout remains after retry",
        "Both mocked bank calls raise timeout.",
        "HTTP 504, status=gateway_timeout, exactly two gateway calls.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.side_effect = [
            requests.Timeout("network timeout 1"),
            requests.Timeout("network timeout 2"),
        ]

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=3)

    show_actual_response(response, bank_post)

    assert response.status_code == 504
    assert response.json()["status"] == "gateway_timeout"
    assert bank_post.call_count == 2


def test_gateway_technical_error_returns_502(fastpay_server):
    show_demo_case(
        "Bank gateway returns a technical 500 error",
        "The mocked bank gateway responds with HTTP 500.",
        "HTTP 502, status=gateway_error, one gateway call.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(500, {"status": "error"})

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 502
    assert response.json()["status"] == "gateway_error"
    bank_post.assert_called_once()


def test_unknown_gateway_status_returns_502(fastpay_server):
    show_demo_case(
        "Bank gateway returns an unknown business status",
        "The mocked bank gateway responds with an unsupported status value.",
        "HTTP 502, status=gateway_error, transaction_id is preserved for diagnostics.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(
            200,
            {"transaction_id": "bank_txn_005", "status": "manual_review"},
        )

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 502
    assert response.json()["transaction_id"] == "bank_txn_005"
    assert response.json()["status"] == "gateway_error"
    bank_post.assert_called_once()


def test_invalid_json_returns_400(fastpay_server):
    show_demo_case(
        "API rejects malformed JSON",
        "Client sends a broken JSON body to POST /v1/payment.",
        "HTTP 400, status=validation_error, request is rejected before payment processing.",
    )

    response = api_post(
        f"{fastpay_server}/v1/payment",
        data="{not-valid-json",
        headers={"Content-Type": "application/json"},
        timeout=2,
    )

    show_actual_response(response)

    assert response.status_code == 400
    assert response.json()["status"] == "validation_error"
    assert response.json()["error"] == "Invalid JSON"


def test_unknown_endpoint_returns_404(fastpay_server):
    show_demo_case(
        "API rejects unknown endpoint",
        "Client sends POST request to a path outside the payment API contract.",
        "HTTP 404, error=not_found.",
    )

    response = api_post(f"{fastpay_server}/v1/unknown", json=VALID_PAYMENT, timeout=2)

    show_actual_response(response)

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_pan_and_cvv_are_not_written_to_logs(fastpay_server, caplog):
    show_demo_case(
        "PAN and CVV are masked in logs",
        "FastPay processes a valid payment and writes operational logs.",
        "Full PAN and CVV are absent; masked PAN and *** are present.",
    )

    with patch("fastpay.gateway.requests.post") as bank_post:
        bank_post.return_value = gateway_response(
            200,
            {"transaction_id": "bank_txn_004", "status": "approved"},
        )

        response = api_post(f"{fastpay_server}/v1/payment", json=VALID_PAYMENT, timeout=2)

    show_actual_response(response, bank_post)

    assert response.status_code == 200
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    print(f"FULL PAN FOUND IN LOGS: {VALID_PAYMENT['card_number'] in log_text}")
    print(f"CVV FOUND IN LOGS: {VALID_PAYMENT['cvv'] in log_text}")
    print("MASKED PAN FOUND IN LOGS: " + str("411111******1111" in log_text))
    print("MASKED CVV FOUND IN LOGS: " + str("***" in log_text))
    assert VALID_PAYMENT["card_number"] not in log_text
    assert VALID_PAYMENT["cvv"] not in log_text
    assert "411111******1111" in log_text
    assert "***" in log_text
