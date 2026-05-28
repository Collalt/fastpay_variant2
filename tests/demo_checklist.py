"""Print a readable checklist of assignment requirements for CI demo logs."""


CHECKLIST = [
    (
        "Use mocks for the external bank gateway",
        "unittest.mock.patch replaces fastpay.gateway.requests.post",
        "Bank responses are simulated; no real bank network call is made.",
    ),
    (
        "Successful authorization",
        "test_successful_authorization",
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
