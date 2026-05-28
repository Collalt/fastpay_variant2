from __future__ import annotations

from collections.abc import Mapping

SENSITIVE_KEYS = {"cvv", "cvc", "security_code"}


def mask_pan(value: object) -> str:
    """Mask a card number, leaving enough digits for operational diagnostics."""
    pan = "" if value is None else str(value)
    if len(pan) <= 4:
        return "****"
    if len(pan) <= 10:
        return "*" * (len(pan) - 4) + pan[-4:]
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


def sanitize_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of a payment payload with sensitive values redacted."""
    sanitized: dict[str, object] = {}
    for key, value in payload.items():
        normalized_key = key.lower()
        if normalized_key in {"card_number", "pan"}:
            sanitized[key] = mask_pan(value)
        elif normalized_key in SENSITIVE_KEYS:
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized
