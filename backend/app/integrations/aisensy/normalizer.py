"""Normalize raw AiSensy webhook payloads into internal shapes.

AiSensy's exact webhook body is not publicly guaranteed to be stable. We code
against the fields that AiSensy historically emits and isolate all
provider-specific field names in this single module. When AiSensy changes a
field, this is the only file you touch.

Assumptions documented inline. The normalizer is resilient: if a field is
missing it falls back to a sensible default so the webhook handler can still
persist a raw event for debugging.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from app.integrations.aisensy.schemas import NormalizedInbound, NormalizedStatus
from app.utils.phone import safe_normalize


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_ts(val: Any) -> dt.datetime:
    if val is None:
        return _now()
    if isinstance(val, (int, float)):
        # Accept seconds or milliseconds.
        if val > 1e12:
            val = val / 1000.0
        return dt.datetime.fromtimestamp(val, dt.timezone.utc)
    if isinstance(val, str):
        try:
            return dt.datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return _now()
    return _now()


def normalize_inbound(raw: dict[str, Any]) -> NormalizedInbound | None:
    """Convert an AiSensy inbound webhook body into NormalizedInbound.

    Returns None if the payload cannot produce a usable message (e.g. system
    notification with no sender).

    Fields we read (best-effort; real AiSensy payloads may differ, in which
    case adapt here only):
      - `messageId` or `id` or `providerMessageId`  -> provider_message_id
      - `from` or `waId` or `sender` or `mobile`    -> phone
      - `senderName` or `profileName`               -> contact_name
      - `text` or `body` or `message` or `content`  -> text
      - `media.url` / `mediaUrl`                    -> media_url
      - `media.type` / `mediaType`                  -> media_type
      - `timestamp` / `createdAt`                   -> received_at
      - `eventType` == "agent_reply" or
        `humanIntervention` flag                    -> human_intervention
      - `meta`, `context` preserved as metadata
    """
    msg = raw.get("message") if isinstance(raw.get("message"), dict) else raw
    provider_id = (
        raw.get("messageId")
        or raw.get("id")
        or raw.get("providerMessageId")
        or msg.get("id")
        or msg.get("messageId")
        or ""
    )
    sender = (
        raw.get("from")
        or raw.get("waId")
        or raw.get("sender")
        or raw.get("mobile")
        or msg.get("from")
        or msg.get("waId")
    )
    if not sender:
        return None
    phone_e164 = safe_normalize(str(sender))
    if not phone_e164:
        return None

    name = raw.get("senderName") or raw.get("profileName") or msg.get("senderName")

    text_val = (
        raw.get("text")
        or raw.get("body")
        or raw.get("message")
        or raw.get("content")
        or msg.get("text")
        or msg.get("body")
        or ""
    )
    if isinstance(text_val, dict):
        text_val = text_val.get("body") or text_val.get("content") or ""

    media = raw.get("media") if isinstance(raw.get("media"), dict) else {}
    media_url = media.get("url") or raw.get("mediaUrl") or msg.get("mediaUrl")
    media_type = media.get("type") or raw.get("mediaType") or msg.get("mediaType")

    received_at = _parse_ts(
        raw.get("timestamp") or raw.get("createdAt") or msg.get("timestamp")
    )

    event_type = (raw.get("eventType") or raw.get("type") or "").lower()
    human_intervention = bool(
        raw.get("humanIntervention")
        or event_type in {"agent_reply", "human_reply", "human_intervention"}
    )

    metadata = {
        "context": raw.get("context"),
        "campaign": raw.get("campaign") or raw.get("campaignName"),
        "eventType": event_type or None,
        "meta": raw.get("meta"),
    }

    return NormalizedInbound(
        provider_message_id=str(provider_id or f"unknown-{received_at.timestamp()}"),
        from_phone_e164=phone_e164,
        contact_name=str(name) if name else None,
        text=str(text_val or "").strip(),
        media_url=str(media_url) if media_url else None,
        media_type=str(media_type) if media_type else None,
        received_at=received_at,
        human_intervention=human_intervention,
        metadata={k: v for k, v in metadata.items() if v is not None},
    )


_STATUS_MAP = {
    "sent": "sent",
    "delivered": "delivered",
    "read": "read",
    "failed": "failed",
    "rejected": "failed",
    "undelivered": "failed",
}


def normalize_status(raw: dict[str, Any]) -> NormalizedStatus | None:
    provider_id = (
        raw.get("messageId")
        or raw.get("id")
        or raw.get("providerMessageId")
        or (raw.get("message") or {}).get("id")
    )
    if not provider_id:
        return None
    status = str(raw.get("status") or raw.get("event") or "").lower()
    mapped = _STATUS_MAP.get(status, "sent" if status else "sent")
    return NormalizedStatus(
        provider_message_id=str(provider_id),
        status=mapped,
        error=raw.get("error") or raw.get("reason"),
        at=_parse_ts(raw.get("timestamp") or raw.get("at") or raw.get("updatedAt")),
        raw=raw,
    )
