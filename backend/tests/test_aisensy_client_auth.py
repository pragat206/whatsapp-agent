from __future__ import annotations

from types import SimpleNamespace

import httpx

from app.integrations.aisensy.client import AiSensyClient
from app.integrations.aisensy.schemas import CampaignSendPayload, SessionSendPayload


class _DummyHttpClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.calls: list[dict] = []

    def post(self, path: str, json: dict, headers: dict | None = None) -> httpx.Response:
        self.calls.append({"path": path, "json": json, "headers": headers or {}})
        return self._responses.pop(0)

    def close(self) -> None:
        return None


def _resp(status: int, payload: str | dict) -> httpx.Response:
    req = httpx.Request("POST", "https://backend.aisensy.com/direct-apis/t1/messages")
    if isinstance(payload, dict):
        return httpx.Response(status, json=payload, request=req)
    return httpx.Response(status, text=payload, request=req)


def _settings(
    auth_method: str = "auto",
    session_endpoint: str = "/direct-apis/t1/messages",
    project_id: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        aisensy_base_url="https://backend.aisensy.com",
        aisensy_campaign_base_url="https://backend.aisensy.com",
        aisensy_api_key="campaign-key",
        aisensy_api_token="project-token",
        aisensy_campaign_endpoint="/campaign/t1/api/v2",
        aisensy_session_endpoint=session_endpoint,
        aisensy_project_id=project_id,
        aisensy_auth_method=auth_method,
        aisensy_source="terrarex-dashboard",
    )


def test_session_send_retries_with_alternate_credential_on_401() -> None:
    client = AiSensyClient(settings=_settings())
    client._client = _DummyHttpClient(
        [
            _resp(401, '{"message":"Authentication Failed!"}'),
            _resp(200, {"success": True}),
        ]
    )
    out = client.send_session_message(SessionSendPayload(destination="+911234567890", body="hello"))
    assert out["success"] is True
    assert len(client._client.calls) == 2
    assert client._client.calls[0]["headers"]["Authorization"] == "Bearer project-token"
    assert client._client.calls[1]["headers"]["Authorization"] == "Bearer campaign-key"


def test_campaign_send_uses_body_apikey_without_authorization_header() -> None:
    client = AiSensyClient(settings=_settings())
    client._client = _DummyHttpClient([_resp(200, {"success": True})])
    out = client.send_campaign(
        CampaignSendPayload(
            campaign_name="test",
            destination="911234567890",
            template_params=[],
            tags=[],
            attributes={},
        )
    )
    assert out["success"] is True
    assert len(client._client.calls) == 1
    assert client._client.calls[0]["headers"] == {}
    assert client._client.calls[0]["json"]["apiKey"] == "campaign-key"


def test_session_send_includes_messaging_product_whatsapp() -> None:
    """AiSensy's /direct-apis is a WhatsApp Cloud proxy and needs messaging_product."""
    client = AiSensyClient(settings=_settings())
    client._client = _DummyHttpClient([_resp(200, {"success": True})])
    client.send_session_message(SessionSendPayload(destination="+911234567890", body="hi"))
    sent = client._client.calls[0]["json"]
    assert sent["messaging_product"] == "whatsapp"
    assert sent["to"] == "911234567890"
    assert sent["type"] == "text"
    assert sent["text"] == {"body": "hi"}


def test_session_send_falls_back_to_project_pwd_header_after_bearer_fails() -> None:
    """When Bearer+token and Bearer+key both fail with 401/422, try the legacy X-AiSensy-Project-API-Pwd header."""
    client = AiSensyClient(settings=_settings())
    client._client = _DummyHttpClient(
        [
            _resp(401, '{"message":"Authentication Failed!"}'),
            _resp(401, '{"message":"Authentication Failed!"}'),
            _resp(200, {"success": True}),
        ]
    )
    out = client.send_session_message(SessionSendPayload(destination="+911234567890", body="hi"))
    assert out["success"] is True
    assert len(client._client.calls) == 3
    assert client._client.calls[0]["headers"]["Authorization"] == "Bearer project-token"
    assert client._client.calls[1]["headers"]["Authorization"] == "Bearer campaign-key"
    assert client._client.calls[2]["headers"]["X-AiSensy-Project-API-Pwd"] == "project-token"


def test_session_send_auth_method_pinned_to_project_pwd_skips_bearer() -> None:
    client = AiSensyClient(settings=_settings(auth_method="project_pwd"))
    client._client = _DummyHttpClient([_resp(200, {"success": True})])
    client.send_session_message(SessionSendPayload(destination="+911234567890", body="hi"))
    headers = client._client.calls[0]["headers"]
    assert "Authorization" not in headers
    assert headers["X-AiSensy-Project-API-Pwd"] == "project-token"


def test_session_send_interpolates_project_id_into_endpoint() -> None:
    """Project API v1 endpoint contains `{project_id}` that must be substituted."""
    settings = _settings(
        session_endpoint="/project-apis/v1/project/{project_id}/messages",
        project_id="abc123",
    )
    settings.aisensy_base_url = "https://apis.aisensy.com"
    client = AiSensyClient(settings=settings)
    client._client = _DummyHttpClient([_resp(200, {"success": True})])
    client.send_session_message(SessionSendPayload(destination="+911234567890", body="hi"))
    url = client._client.calls[0]["path"]
    assert url == "https://apis.aisensy.com/project-apis/v1/project/abc123/messages"


def test_session_send_fails_fast_when_project_id_missing() -> None:
    """If the endpoint contains {project_id} but AISENSY_PROJECT_ID is empty, raise immediately."""
    from app.utils.retries import ProviderPermanentError

    settings = _settings(
        session_endpoint="/project-apis/v1/project/{project_id}/messages",
        project_id="",
    )
    settings.aisensy_base_url = "https://apis.aisensy.com"
    client = AiSensyClient(settings=settings)
    client._client = _DummyHttpClient([])
    try:
        client.send_session_message(SessionSendPayload(destination="+911234567890", body="hi"))
    except ProviderPermanentError as exc:
        assert "AISENSY_PROJECT_ID" in str(exc)
        assert client._client.calls == []
    else:
        raise AssertionError("expected ProviderPermanentError")


def test_campaign_and_session_use_different_base_urls() -> None:
    """Project API v1 lives on apis.aisensy.com; campaigns stay on backend.aisensy.com."""
    settings = _settings(
        session_endpoint="/project-apis/v1/project/{project_id}/messages",
        project_id="p1",
    )
    settings.aisensy_base_url = "https://apis.aisensy.com"
    settings.aisensy_campaign_base_url = "https://backend.aisensy.com"
    client = AiSensyClient(settings=settings)
    client._client = _DummyHttpClient(
        [_resp(200, {"success": True}), _resp(200, {"success": True})]
    )
    client.send_session_message(SessionSendPayload(destination="+911234567890", body="hi"))
    client.send_campaign(
        CampaignSendPayload(
            campaign_name="c",
            destination="911234567890",
            template_params=[],
            tags=[],
            attributes={},
        )
    )
    assert client._client.calls[0]["path"].startswith("https://apis.aisensy.com/")
    assert client._client.calls[1]["path"].startswith("https://backend.aisensy.com/")
