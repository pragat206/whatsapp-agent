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

    def _session_auth_headers(self) -> list[dict[str, str]]:
        """Auth header candidates for `/direct-apis/*` calls.

        AiSensy has shipped two auth styles over time:
          * `Authorization: Bearer <token>` — modern direct-apis projects
          * `X-AiSensy-Project-API-Pwd: <password>` — legacy Project API projects

        Different AiSensy accounts also expose either one token (works
        everywhere) or separate Project/Campaign credentials, and we
        occasionally see values swapped between env vars.

        The candidate list is ordered so the most likely combination runs
        first. On auth failure (`401` or `422 invalid token`) the caller keeps
        walking the list. `AISENSY_AUTH_METHOD` pins the style when a project
        is known to use only one.
        """
        token = (self.settings.aisensy_api_token or "").strip()
        key = (self.settings.aisensy_api_key or "").strip()
        values: list[str] = []
        seen: set[str] = set()
        for value in (token, key):
            if value and value not in seen:
                values.append(value)
                seen.add(value)

        method = (getattr(self.settings, "aisensy_auth_method", "auto") or "auto").lower()
        styles: list[str]
        if method == "bearer":
            styles = ["bearer"]
        elif method == "project_pwd":
            styles = ["project_pwd"]
        else:
            styles = ["bearer", "project_pwd"]

        candidates: list[dict[str, str]] = []
        for style in styles:
            for value in values:
                if style == "bearer":
                    candidates.append({"Authorization": f"Bearer {value}"})
                else:
                    candidates.append({"X-AiSensy-Project-API-Pwd": value})
        return candidates

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
        # AiSensy `/direct-apis/t1/messages` is a thin proxy over WhatsApp
        # Cloud API — it expects the Cloud API body shape including
        # `messaging_product: "whatsapp"`. Omitting it causes AiSensy to
        # return 400/422. Authentication is a header (handled in _post);
        # do NOT include `apiKey` in the body for direct-apis.
        to = _strip_plus(payload.destination)
        if payload.media_url:
            media_type = payload.media_type or "image"
            body: dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": to,
                "recipient_type": "individual",
                "type": media_type,
                media_type: {
                    "link": payload.media_url,
                    **({"caption": payload.body} if payload.body else {}),
                },
            }
        else:
            body = {
                "messaging_product": "whatsapp",
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
        is_session_send = path.strip() == self.settings.aisensy_session_endpoint.strip()
        auth_candidates = self._session_auth_headers() if is_session_send else [{}]
        auth_styles = [_header_style_label(h) for h in auth_candidates]
        logger.info(
            "aisensy_request",
            path=path,
            destination=body.get("destination") or body.get("to"),
            campaign_name=body.get("campaignName"),
            type_=body.get("type"),
            body_keys=sorted(body.keys()),
            auth_candidates=len(auth_candidates),
            auth_styles=auth_styles,
            apikey_in_body=("apiKey" in body),
        )
        resp: httpx.Response | None = None
        used_headers: dict[str, str] = {}
        for headers in auth_candidates:
            used_headers = headers
            try:
                resp = self._client.post(path, json=body, headers=headers)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                logger.warning("aisensy_transient_network", path=path, error=str(exc))
                raise ProviderTransientError(str(exc)) from exc
            body_lc = resp.text.lower()
            is_bad_token = (
                resp.status_code == 401
                or (resp.status_code == 422 and "invalid token" in body_lc)
            )
            # For session sends only: try next candidate on auth failure.
            if is_session_send and is_bad_token and headers != auth_candidates[-1]:
                logger.warning(
                    "aisensy_session_auth_retry",
                    path=path,
                    status=resp.status_code,
                    tried_style=_header_style_label(headers),
                )
                continue
            break
        assert resp is not None

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
                last_auth_style=_header_style_label(used_headers),
                auth_styles_tried=auth_styles,
                apikey_in_body=("apiKey" in body),
                hint=(
                    "AiSensy rejected every configured credential for /direct-apis/. "
                    "This endpoint authenticates via a header — Bearer `AISENSY_API_TOKEN` "
                    "(newer projects) or `X-AiSensy-Project-API-Pwd` (legacy). Both are "
                    "auto-tried unless AISENSY_AUTH_METHOD is pinned. Campaign sends use "
                    "AISENSY_API_KEY in the body — that is a DIFFERENT value in most "
                    "accounts. Fix: open AiSensy dashboard → Manage → API Key, copy the "
                    "token shown for direct-apis / project API into AISENSY_API_TOKEN, "
                    "and the campaign API key into AISENSY_API_KEY. Check for trailing "
                    "whitespace/newlines in Railway env values."
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


def _header_style_label(headers: dict[str, str]) -> str:
    """Short name for the auth style in a candidate header map (for logs)."""
    if not headers:
        return "none"
    if "Authorization" in headers:
        return "bearer"
    if "X-AiSensy-Project-API-Pwd" in headers:
        return "project_pwd"
    return ",".join(sorted(headers.keys()))


_client_singleton: AiSensyClient | None = None


def get_aisensy_client() -> AiSensyClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = AiSensyClient()
    return _client_singleton
