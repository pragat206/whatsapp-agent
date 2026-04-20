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


def _dig(d: dict, *paths: tuple[str, ...]) -> Any:
    """Return the first non-empty value at any of the dotted paths."""
    for path in paths:
        cur: Any = d
        ok = True
        for key in path:
            if not isinstance(cur, dict) or key not in cur or cur[key] in (None, "", []):
                ok = False
                break
            cur = cur[key]
        if ok:
            return cur
    return None


def normalize_inbound(raw: dict[str, Any]) -> NormalizedInbound | None:
    """Convert an AiSensy inbound webhook body into NormalizedInbound.

    Returns None if the payload cannot produce a usable message (e.g. system
    notification with no sender).

    AiSensy uses several shapes across topics/versions. The fields below cover
    `message.sender.user` and older `direct-apis` shapes observed in the wild.
    If a customer sees inbound webhook events stored but no conversations
    created, that means this normalizer didn't recognise the payload — inspect
    `raw_webhook_events.payload` and add the missing field path here.
    """
    # Many AiSensy payloads nest the actual message under `payload` or `message`
    # or `data`. Look there as a fallback source too.
    msg = raw.get("message") if isinstance(raw.get("message"), dict) else {}
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    inner_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    sender_obj = payload.get("sender") if isinstance(payload.get("sender"), dict) else {}
    if not sender_obj:
        sender_obj = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}

    provider_id = (
        raw.get("messageId")
        or raw.get("id")
        or raw.get("providerMessageId")
        or msg.get("id")
        or msg.get("messageId")
        or payload.get("id")
        or payload.get("messageId")
        or data.get("messageId")
        or data.get("id")
        or ""
    )
    sender_raw_candidate = raw.get("sender") if not isinstance(raw.get("sender"), dict) else None
    sender_candidates = (
        raw.get("from"),
        raw.get("waId"),
        sender_raw_candidate,
        raw.get("mobile"),
        raw.get("senderMobile"),
        raw.get("senderMobileNumber"),
        raw.get("senderPhoneNumber"),
        raw.get("senderPhone"),
        raw.get("customerPhone"),
        raw.get("whatsappNumber"),
        raw.get("waNumber"),
        raw.get("source") if not isinstance(raw.get("source"), dict) else None,
        msg.get("from"),
        msg.get("waId"),
        payload.get("source") if not isinstance(payload.get("source"), dict) else None,
        payload.get("from"),
        payload.get("senderMobile"),
        sender_obj.get("phone"),
        sender_obj.get("mobile"),
        sender_obj.get("waId"),
        data.get("from"),
        data.get("senderMobile"),
    )
    sender = next((s for s in sender_candidates if s), None)
    if not sender:
        return None
    phone_e164 = safe_normalize(str(sender))
    if not phone_e164:
        return None

    name = (
        raw.get("senderName")
        or raw.get("profileName")
        or raw.get("customerName")
        or msg.get("senderName")
        or payload.get("senderName")
        or sender_obj.get("name")
        or data.get("senderName")
    )

    # Text can live in `text`, `body`, `message`, or nested under payload/data.
    text_val = (
        raw.get("text")
        or raw.get("body")
        or raw.get("message")
        or raw.get("content")
        or msg.get("text")
        or msg.get("body")
        or payload.get("text")
        or payload.get("body")
        or inner_payload.get("text")
        or inner_payload.get("body")
        or data.get("text")
        or data.get("body")
        or ""
    )
    if isinstance(text_val, dict):
        text_val = (
            text_val.get("body")
            or text_val.get("content")
            or text_val.get("text")
            or ""
        )

    media = raw.get("media") if isinstance(raw.get("media"), dict) else {}
    if not media and isinstance(payload.get("media"), dict):
        media = payload["media"]
    media_url = (
        media.get("url")
        or raw.get("mediaUrl")
        or msg.get("mediaUrl")
        or payload.get("mediaUrl")
    )
    media_type = (
        media.get("type")
        or raw.get("mediaType")
        or msg.get("mediaType")
        or payload.get("mediaType")
        or raw.get("messageType")
        or payload.get("type")
    )

    received_at = _parse_ts(
        raw.get("timestamp")
        or raw.get("createdAt")
        or raw.get("receivedAt")
        or msg.get("timestamp")
        or payload.get("timestamp")
    )

    event_type = (raw.get("eventType") or raw.get("type") or raw.get("topic") or "").lower()
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
