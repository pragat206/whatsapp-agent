"""HTTP client for AiSensy.

Covers two send paths:
  * campaign send (templated, business-initiated)
  * session send (free-form, inside the 24h service window)

All outbound errors are surfaced as either `ProviderTransientError`
(retryable) or `ProviderPermanentError` (not retryable).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.aisensy.schemas import (
    CampaignSendPayload,
    SessionSendPayload,
)
from app.utils.retries import (
    ProviderPermanentError,
    ProviderTransientError,
    with_retry,
)

logger = get_logger("aisensy.client")


class AiSensyClient:
    def __init__(self, settings=None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(
            base_url=self.settings.aisensy_base_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    def _bearer_token(self) -> str:
        """The credential used for `Authorization: Bearer ...`.

        AiSensy's `/direct-apis/` endpoint only accepts Bearer auth — the legacy
        `apiKey` in request body is ignored there. The `aisensy_api_token`
        env var lets you set a distinct token, but on accounts where the same
        credential works for both, leaving it unset falls back to the key.
        """
        return (self.settings.aisensy_api_token or self.settings.aisensy_api_key or "").strip()

    # ------------------------------------------------------------------
    # Outbound: campaign (templated)
    # ------------------------------------------------------------------
    @with_retry()
    def send_campaign(self, payload: CampaignSendPayload) -> dict[str, Any]:
        """Send a campaign message via AiSensy's campaign API.

        AiSensy's campaign v2 endpoint accepts a JSON body with:
            apiKey, campaignName, destination, userName, source,
            media, templateParams, tags, attributes
        """
        body: dict[str, Any] = {
            "apiKey": self.settings.aisensy_api_key,
            "campaignName": payload.campaign_name,
            "destination": payload.destination,
            "userName": payload.user_name or "",
            "source": payload.source or self.settings.aisensy_source,
            "templateParams": payload.template_params,
            "tags": payload.tags,
            "attributes": payload.attributes or {},
        }
        if payload.media:
            body["media"] = {
                "url": payload.media.url,
                "filename": payload.media.filename or "",
            }

        return self._post(self.settings.aisensy_campaign_endpoint, body)

    # ------------------------------------------------------------------
    # Outbound: session (free-form, 24h window)
    # ------------------------------------------------------------------
    @with_retry()
    def send_session_message(self, payload: SessionSendPayload) -> dict[str, Any]:
        """Send a free-form reply within the service window."""
        # AiSensy `/direct-apis/t1/messages` authenticates via
        # `Authorization: Bearer <token>` (handled in _post). Do NOT include
        # `apiKey` in the body — AiSensy returns 401 if the Bearer header is
        # missing regardless of body contents.
        to = _strip_plus(payload.destination)
        if payload.media_url:
            body: dict[str, Any] = {
                "to": to,
                "recipient_type": "individual",
                "type": payload.media_type or "image",
                "media": {"url": payload.media_url},
                "caption": payload.body,
            }
        else:
            body = {
                "to": to,
                "recipient_type": "individual",
                "type": "text",
                "text": {"body": payload.body},
            }
        return self._post(self.settings.aisensy_session_endpoint, body)

    # ------------------------------------------------------------------
    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        # Strip secrets from logs while keeping the rest of the body visible.
        loggable_body = {k: ("<redacted>" if k.lower() in {"apikey", "api_key"} else v)
                         for k, v in body.items()}
        token = self._bearer_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        logger.info(
            "aisensy_request",
            path=path,
            destination=body.get("destination") or body.get("to"),
            campaign_name=body.get("campaignName"),
            type_=body.get("type"),
            body_keys=sorted(body.keys()),
            auth_header_present=bool(token),
            apikey_in_body=("apiKey" in body),
        )
        try:
            resp = self._client.post(path, json=body, headers=headers)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            logger.warning("aisensy_transient_network", path=path, error=str(exc))
            raise ProviderTransientError(str(exc)) from exc

        logger.info(
            "aisensy_response",
            path=path,
            status=resp.status_code,
            body_preview=resp.text[:500],
        )

        if resp.status_code >= 500:
            logger.warning("aisensy_5xx", status=resp.status_code, body=resp.text[:500], request_body=loggable_body)
            raise ProviderTransientError(f"5xx from AiSensy: {resp.status_code}")
        if resp.status_code == 429:
            logger.warning("aisensy_429", body=resp.text[:500])
            raise ProviderTransientError("rate limited")
        # AiSensy uses both 401 ("Unauthorized") and 422 ("Invalid Token!") to
        # signal a bad credential — surface them with the same remediation.
        body_lc = resp.text.lower()
        is_bad_token = (
            resp.status_code == 401
            or (resp.status_code == 422 and "invalid token" in body_lc)
        )
        if is_bad_token:
            logger.error(
                "aisensy_bad_token",
                path=path,
                status=resp.status_code,
                body=resp.text[:500],
                auth_header_present=bool(token),
                apikey_in_body=("apiKey" in body),
                hint=(
                    "AiSensy rejected the credential. /direct-apis/ uses the Bearer "
                    "header (AISENSY_API_TOKEN, falling back to AISENSY_API_KEY). "
                    "/campaign/ uses the apiKey body field (AISENSY_API_KEY). "
                    "If your AiSensy dashboard shows distinct Project API and Campaign "
                    "API tokens, try: AISENSY_API_TOKEN=<Project API>, "
                    "AISENSY_API_KEY=<Campaign API>. If still rejected, swap them. "
                    "Also check for trailing whitespace/newlines in the Railway values."
                ),
            )
            raise ProviderPermanentError(f"{resp.status_code}: {resp.text[:300]}")
        if resp.status_code >= 400:
            logger.error("aisensy_4xx", status=resp.status_code, body=resp.text[:500], request_body=loggable_body)
            raise ProviderPermanentError(f"{resp.status_code}: {resp.text[:300]}")

        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}


def _strip_plus(phone: str) -> str:
    """AiSensy direct-apis expect the destination without a leading `+`."""
    return phone[1:] if phone.startswith("+") else phone


_client_singleton: AiSensyClient | None = None


def get_aisensy_client() -> AiSensyClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = AiSensyClient()
    return _client_singleton
