from app.utils.phone import normalize, safe_normalize


def test_normalize_indian_number_with_space():
    assert normalize("+91 98765 43210") == "+919876543210"


def test_normalize_raw_10_digit():
    assert normalize("9876543210") == "+919876543210"


def test_safe_normalize_bad_number_returns_none():
    assert safe_normalize("abc") is None
    assert safe_normalize("") is None
