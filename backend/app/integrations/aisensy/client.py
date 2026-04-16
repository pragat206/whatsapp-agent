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
        if payload.media_url:
            body: dict[str, Any] = {
                "apiKey": self.settings.aisensy_api_key,
                "to": payload.destination,
                "type": payload.media_type or "image",
                "media": {"url": payload.media_url},
                "caption": payload.body,
            }
        else:
            body = {
                "apiKey": self.settings.aisensy_api_key,
                "to": payload.destination,
                "type": "text",
                "text": {"body": payload.body},
            }
        return self._post(self.settings.aisensy_session_endpoint, body)

    # ------------------------------------------------------------------
    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post(path, json=body)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            logger.warning("aisensy_transient_network", path=path, error=str(exc))
            raise ProviderTransientError(str(exc)) from exc

        if resp.status_code >= 500:
            logger.warning("aisensy_5xx", status=resp.status_code, body=resp.text[:500])
            raise ProviderTransientError(f"5xx from AiSensy: {resp.status_code}")
        if resp.status_code == 429:
            raise ProviderTransientError("rate limited")
        if resp.status_code >= 400:
            logger.error("aisensy_4xx", status=resp.status_code, body=resp.text[:500])
            raise ProviderPermanentError(f"{resp.status_code}: {resp.text[:300]}")

        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}


_client_singleton: AiSensyClient | None = None


def get_aisensy_client() -> AiSensyClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = AiSensyClient()
    return _client_singleton
