"""Phone normalization. Defaults to Indian dial code for Terra Rex Energy."""
from __future__ import annotations

import phonenumbers

DEFAULT_REGION = "IN"


class PhoneParseError(ValueError):
    pass


def normalize(raw: str, default_region: str = DEFAULT_REGION) -> str:
    if raw is None:
        raise PhoneParseError("empty phone")
    raw = str(raw).strip()
    if not raw:
        raise PhoneParseError("empty phone")
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException as exc:
        raise PhoneParseError(str(exc)) from exc
    if not phonenumbers.is_valid_number(parsed):
        raise PhoneParseError(f"invalid number: {raw}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def safe_normalize(raw: str, default_region: str = DEFAULT_REGION) -> str | None:
    try:
        return normalize(raw, default_region)
    except PhoneParseError:
        return None
