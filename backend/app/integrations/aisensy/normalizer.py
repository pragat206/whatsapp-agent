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


def _normalize_sender_phone(raw_sender: Any) -> str | None:
    """Best-effort normalize provider sender values to E.164.

    AiSensy often sends `phone_number` as `9198...` (no leading '+').
    """
    if raw_sender is None:
        return None
    s = str(raw_sender).strip()
    if not s:
        return None

    # Try as-is first.
    norm = safe_normalize(s)
    if norm:
        return norm

    # Retry with only digits and explicit '+' (common provider shape: 91xxxxxxxxxx).
    digits = "".join(ch for ch in s if ch.isdigit())
    if 10 <= len(digits) <= 15:
        norm = safe_normalize(f"+{digits}")
        if norm:
            return norm
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
    data_msg = data.get("message") if isinstance(data.get("message"), dict) else {}
    inner_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    sender_obj = payload.get("sender") if isinstance(payload.get("sender"), dict) else {}
    if not sender_obj:
        sender_obj = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}

    # Prefer the WhatsApp `wamid` (carried on the inner message) over the
    # webhook envelope id. The envelope id changes per delivery attempt and
    # cannot be correlated with outbound status callbacks, while the wamid is
    # what AiSensy references in subsequent `message.status` events.
    provider_id = (
        data_msg.get("messageId")
        or msg.get("messageId")
        or payload.get("messageId")
        or data.get("messageId")
        or raw.get("messageId")
        or raw.get("providerMessageId")
        or data_msg.get("id")
        or msg.get("id")
        or payload.get("id")
        or data.get("id")
        or raw.get("id")
        or _dig(raw, ("data", "message", "context", "id"))
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
        data_msg.get("from"),
        data_msg.get("waId"),
        data_msg.get("phone_number"),
        data_msg.get("phoneNumber"),
        data_msg.get("senderMobile"),
        _dig(raw, ("data", "message", "context", "from")),
    )
    sender = next((s for s in sender_candidates if s), None)
    if not sender:
        return None
    phone_e164 = _normalize_sender_phone(sender)
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
        or data_msg.get("userName")
        or data_msg.get("senderName")
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
        or data_msg.get("text")
        or data_msg.get("body")
        or _dig(raw, ("data", "message", "message_content", "text"))
        or _dig(raw, ("data", "message", "message_content", "body"))
        or _dig(raw, ("data", "message", "message_content", "title"))
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
        or _dig(raw, ("data", "message", "media", "url"))
        or _dig(raw, ("data", "message", "message_content", "url"))
    )
    media_type = (
        media.get("type")
        or raw.get("mediaType")
        or msg.get("mediaType")
        or payload.get("mediaType")
        or raw.get("messageType")
        or payload.get("type")
        or data_msg.get("message_type")
        or _dig(raw, ("data", "message", "media", "type"))
    )

    received_at = _parse_ts(
        raw.get("timestamp")
        or raw.get("createdAt")
        or raw.get("created_at")
        or raw.get("receivedAt")
        or msg.get("timestamp")
        or payload.get("timestamp")
        or data_msg.get("sent_at")
        or data_msg.get("created_at")
    )

    event_type = (raw.get("eventType") or raw.get("type") or raw.get("topic") or "").lower()
    sender_kind = str(data_msg.get("sender") or "").upper()
    human_intervention = bool(
        raw.get("humanIntervention")
        or event_type in {"agent_reply", "human_reply", "human_intervention"}
        or sender_kind in {"AGENT", "HUMAN"}
    )

    metadata = {
        "context": raw.get("context"),
        "campaign": raw.get("campaign") or raw.get("campaignName") or data_msg.get("campaign"),
        "eventType": event_type or None,
        "meta": raw.get("meta"),
        "topic": raw.get("topic"),
        "message_type": data_msg.get("message_type"),
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
    msg = raw.get("message") if isinstance(raw.get("message"), dict) else {}
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    data_msg = data.get("message") if isinstance(data.get("message"), dict) else {}
    # As with inbound: prefer the inner wamid over the webhook envelope id so
    # status updates can be correlated to the originally stored message.
    provider_id = (
        data_msg.get("messageId")
        or msg.get("messageId")
        or data.get("messageId")
        or raw.get("messageId")
        or raw.get("providerMessageId")
        or data_msg.get("id")
        or msg.get("id")
        or data.get("id")
        or raw.get("id")
        or _dig(raw, ("data", "message", "context", "id"))
    )
    if not provider_id:
        return None
    status = str(
        raw.get("status")
        or raw.get("event")
        or msg.get("status")
        or data.get("status")
        or data_msg.get("status")
        or ""
    ).lower()
    mapped = _STATUS_MAP.get(status, "sent" if status else "sent")
    error_val = (
        raw.get("error")
        or raw.get("reason")
        or data_msg.get("failureResponse")
        or msg.get("error")
    )
    at_val = (
        raw.get("timestamp")
        or raw.get("at")
        or raw.get("updatedAt")
        or raw.get("created_at")
        or data_msg.get("read_at")
        or data_msg.get("delivered_at")
        or data_msg.get("sent_at")
    )
    return NormalizedStatus(
        provider_message_id=str(provider_id),
        status=mapped,
        error=str(error_val) if error_val else None,
        at=_parse_ts(at_val),
        raw=raw,
    )
