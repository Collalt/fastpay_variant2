"""Print a readable checklist of assignment requirements for CI demo logs."""


CHECKLIST = [
    (
        "Use mocks for the external bank gateway",
        "unittest.mock.patch replaces fastpay.gateway.requests.post",
        "Bank responses are simulated; no real bank network call is made.",
    ),
    (
        "Successful authorization",
        "test_successful_authorization; test_bank_approved_without_transaction_id_generates_local_id",
        "approved from bank -> FastPay returns status=authorized.",
    ),
    (
        "Insufficient funds / declined",
        "test_insufficient_funds_returns_declined",
        "declined from bank -> FastPay returns status=declined.",
    ),
    (
        "CVV validation error",
        "test_invalid_cvv_validation_error_and_no_gateway_call",
        "bad CVV -> HTTP 400 and bank gateway is not called.",
    ),
    (
        "Payment payload validation",
        "test_invalid_payment_payload_returns_400_without_gateway_call; test_missing_required_field_returns_400_without_gateway_call",
        "bad amount, expiry, merchant_id or missing field -> HTTP 400 and no bank call.",
    ),
    (
        "Gateway timeout and retry logic",
        "test_gateway_timeout_is_retried_then_authorized",
        "first call timeout, second call approved -> exactly two bank calls.",
    ),
    (
        "Gateway timeout after retry",
        "test_gateway_timeout_after_retry_returns_504",
        "two timeouts -> HTTP 504 gateway_timeout.",
    ),
    (
        "Gateway technical and contract errors",
        "test_gateway_technical_error_returns_502; test_unknown_gateway_status_returns_502",
        "bank 500 or unknown status -> HTTP 502 gateway_error.",
    ),
    (
        "HTTP API contract errors",
        "test_invalid_json_returns_400; test_unknown_endpoint_returns_404",
        "malformed JSON -> HTTP 400; unknown endpoint -> HTTP 404.",
    ),
    (
        "PAN and CVV are not written to logs",
        "test_pan_and_cvv_are_not_written_to_logs",
        "full card number and CVV are absent from captured test logs.",
    ),
]


def main() -> None:
    print("=" * 88)
    print("FASTPAY VARIANT 2 - CI DEMO CHECKLIST")
    print("=" * 88)
    for number, (requirement, test, expected) in enumerate(CHECKLIST, start=1):
        print(f"{number}. REQUIREMENT: {requirement}")
        print(f"   COVERED BY:  {test}")
        print(f"   EXPECTED:    {expected}")
    print("=" * 88)


if __name__ == "__main__":
    main()
