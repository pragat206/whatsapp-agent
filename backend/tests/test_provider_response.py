"""Regression tests for AiSensy response interpretation.

The campaign V2 API returns `{"success": true, "message": "Success"}` on a
successful send — no `messageId`. Earlier logic treated the missing id as a
failure and marked every campaign recipient `failed`, making the product look
like a dummy box. These tests pin down the new behavior: only explicit error
signals are failures.
"""
from __future__ import annotations

from app.services.campaign.sender import (
    _extract_provider_id,
    _response_error_hint,
)


class TestCampaignResponseErrorHint:
    def test_aisensy_success_dict_is_not_an_error(self):
        assert _response_error_hint({"success": True, "message": "Success"}) is None

    def test_status_success_is_not_an_error(self):
        assert _response_error_hint({"status": "success"}) is None

    def test_success_false_flagged(self):
        assert _response_error_hint({"success": False, "message": "rate limit"}) == "rate limit"

    def test_status_error_flagged(self):
        assert _response_error_hint({"status": "error", "message": "bad template"}) == "bad template"

    def test_status_failed_flagged(self):
        hint = _response_error_hint({"status": "failed"})
        assert hint == "provider status=failed"

    def test_plain_error_field(self):
        assert _response_error_hint({"error": "invalid apiKey"}) == "invalid apiKey"

    def test_errors_list(self):
        assert _response_error_hint({"errors": ["a", "b"]}) == "a, b"

    def test_non_dict_not_an_error(self):
        assert _response_error_hint("OK") is None
        assert _response_error_hint(None) is None

    def test_numeric_code_4xx(self):
        hint = _response_error_hint({"code": 400, "message": "bad req"})
        assert hint is not None
        assert "400" in hint

    def test_numeric_code_2xx_not_error(self):
        assert _response_error_hint({"code": 200, "message": "Success"}) is None


class TestExtractProviderId:
    def test_top_level_message_id(self):
        assert _extract_provider_id({"messageId": "wamid.123"}) == "wamid.123"

    def test_nested_data(self):
        assert _extract_provider_id({"data": {"id": "xyz"}}) == "xyz"

    def test_missing_id_returns_none(self):
        # Campaign V2 case: success without id — must not crash, returns None,
        # and caller (sender) must still mark the recipient as sent.
        assert _extract_provider_id({"success": True, "message": "Success"}) is None
