"""AiSensy webhook endpoints.

Two endpoints are exposed:

  * POST /webhooks/aisensy/inbound   — inbound customer messages
  * POST /webhooks/aisensy/status    — outbound delivery/read/failure events

Both persist the raw payload first (auditability) and are idempotent via
`raw_webhook_events.dedupe_key`. Webhook signature validation is performed if
`AISENSY_WEBHOOK_SECRET` is non-empty. The secret must match what you configure
in AiSensy; the inbound request must include a compatible HMAC of the raw body.

If you see **401 missing signature / bad signature** in production, either align
the secret and header with AiSensy, or temporarily set `AISENSY_WEBHOOK_SECRET=`
(empty) to disable verification while debugging (not recommended long-term).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import db_dep
from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.aisensy import normalize_inbound, normalize_status
from app.models.audit import RawWebhookEvent
from app.services.messaging.status_processor import apply_status
from app.services.messaging.webhook_processor import process_inbound
from app.workers.queue import enqueue_ai_reply

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("webhooks.aisensy")

# Header names to try (HTTP stacks lower-case keys; Starlette uses lower-case).
_SIGNATURE_HEADER_KEYS = (
    "x-aisensy-signature",
    "x-webhook-signature",
    "x-hub-signature-256",
    "x-signature",
)


def _extract_signature_header(request: Request) -> str | None:
    """Best-effort: providers use different header names for the same HMAC."""
    for key in _SIGNATURE_HEADER_KEYS:
        v = request.headers.get(key)
        if v:
            return v.strip()
    return None


def _hmac_sha256_raw(secret: str, raw_body: bytes) -> bytes:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()


def _signature_valid(secret: str, raw_body: bytes, given_header: str) -> bool:
    """Accept hex or base64 digests, optional ``sha256=`` prefix (GitHub style)."""
    given = given_header.strip()
    if given.lower().startswith("sha256="):
        given = given[7:].strip()
    digest = _hmac_sha256_raw(secret, raw_body)
    hex_expected = digest.hex()
    given_lower = given.lower().strip()

    # Hex (64 chars)
    if len(given_lower) == 64:
        try:
            if hmac.compare_digest(hex_expected, given_lower):
                return True
        except (TypeError, ValueError):
            pass

    # Base64(raw HMAC bytes)
    try:
        decoded = base64.b64decode(given, validate=False)
        if len(decoded) == 32 and hmac.compare_digest(digest, decoded):
            return True
    except (binascii.Error, ValueError):
        pass

    # Hex with spaces / mixed case already handled by compare_digest on hex
    return False


def _validate_signature(request: Request, raw_body: bytes, signature: str | None) -> None:
    settings = get_settings()
    secret = (settings.aisensy_webhook_secret or "").strip()
    if not secret:
        return

    sig = signature or _extract_signature_header(request)
    if sig is None:
        if settings.app_env != "local":
            logger.warning(
                "webhook_signature_missing",
                path=str(request.url.path),
                header_keys_present=[k for k in _SIGNATURE_HEADER_KEYS if request.headers.get(k)],
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing signature")
        return
    if not _signature_valid(secret, raw_body, sig):
        logger.warning("webhook_signature_mismatch", path=str(request.url.path))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")


def _diagnose_unnormalizable(payload: Any) -> str:
    """Best-effort human explanation of why the normalizer returned None.

    The normalizer only gives up when it cannot find a sender phone number, so
    focus on that. Returns a short string that's safe to surface in the admin
    diagnostics list.
    """
    if not isinstance(payload, dict):
        return f"payload is not a JSON object (got {type(payload).__name__})"
    top_keys = sorted(payload.keys())
    if not top_keys:
        return "payload is an empty object"
    # Surface the shape so we know which fields AiSensy actually sent.
    known_phone_fields = (
        "from", "waId", "mobile", "senderMobile", "senderMobileNumber",
        "senderPhone", "senderPhoneNumber", "customerPhone", "whatsappNumber",
        "waNumber", "source",
    )
    if not any(payload.get(k) for k in known_phone_fields):
        nested = []
        for k in ("message", "payload", "data", "sender"):
            v = payload.get(k)
            if isinstance(v, dict):
                nested.append(f"{k}={sorted(v.keys())[:12]}")
        nested_str = f" nested[{', '.join(nested)}]" if nested else ""
        return (
            f"no sender phone field found (looked for {list(known_phone_fields)}); "
            f"top-level keys were {top_keys[:20]}{nested_str}"
        )
    return "sender field present but value was empty or not a phone number"


def _dedupe_key(payload: dict[str, Any], kind: str) -> str:
    mid = (
        payload.get("messageId")
        or payload.get("id")
        or (payload.get("message") or {}).get("id")
        or payload.get("providerMessageId")
        or ""
    )
    return f"aisensy:{kind}:{mid}" if mid else f"aisensy:{kind}:hash:{hashlib.sha256(str(payload).encode()).hexdigest()[:24]}"


@router.post("/aisensy/inbound", status_code=202)
async def aisensy_inbound(
    request: Request,
    db: Session = Depends(db_dep),
) -> dict:
    raw = await request.body()
    logger.info(
        "inbound_webhook_received",
        path=str(request.url.path),
        bytes=len(raw),
        content_type=request.headers.get("content-type"),
        signature_header_present=any(
            request.headers.get(k) for k in _SIGNATURE_HEADER_KEYS
        ),
    )
    _validate_signature(request, raw, _extract_signature_header(request))
    try:
        payload = await request.json()
    except Exception:
        logger.warning("inbound_invalid_json", body_preview=raw[:200].decode("utf-8", "replace"))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json")

    if isinstance(payload, dict):
        logger.info(
            "inbound_payload_parsed",
            top_level_keys=sorted(payload.keys())[:30],
        )

    dedupe = _dedupe_key(payload, "inbound")
    existing = db.query(RawWebhookEvent).filter_by(dedupe_key=dedupe).first()
    if existing:
        logger.info("inbound_dedup_hit", dedupe=dedupe)
        return {"ok": True, "dedupe": True}

    raw_event = RawWebhookEvent(
        provider="aisensy",
        kind="inbound",
        dedupe_key=dedupe,
        payload=payload,
    )
    db.add(raw_event)
    db.commit()
    logger.info("inbound_raw_persisted", raw_event_id=str(raw_event.id), dedupe=dedupe)

    try:
        normalized = normalize_inbound(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("normalize_failed", error=str(exc), raw_event_id=str(raw_event.id))
        raw_event.error = str(exc)[:500]
        db.commit()
        return {"ok": True, "normalized": False}

    if normalized is None:
        reason = _diagnose_unnormalizable(payload)
        raw_event.error = f"normalizer returned None: {reason}"[:500]
        raw_event.processed = True
        db.commit()
        logger.warning(
            "inbound_unnormalizable",
            raw_event_id=str(raw_event.id),
            reason=reason,
            dedupe=dedupe,
        )
        return {"ok": True, "processed": False, "reason": reason}

    logger.info(
        "inbound_normalized",
        raw_event_id=str(raw_event.id),
        from_phone=normalized.from_phone_e164,
        text_preview=(normalized.text or "")[:100],
        provider_message_id=normalized.provider_message_id,
        human_intervention=normalized.human_intervention,
    )

    result = process_inbound(db, normalized)
    raw_event.processed = True
    db.commit()

    if result is not None:
        conversation_id, message_id = result
        logger.info(
            "inbound_enqueueing_ai_reply",
            raw_event_id=str(raw_event.id),
            conversation_id=str(conversation_id),
            message_id=str(message_id),
        )
        enqueue_ai_reply(conversation_id, message_id)
    else:
        logger.info(
            "inbound_no_ai_reply",
            raw_event_id=str(raw_event.id),
            note="conversation not in AI_ACTIVE state or processor declined",
        )

    return {"ok": True}


@router.post("/aisensy/status", status_code=202)
async def aisensy_status(
    request: Request,
    db: Session = Depends(db_dep),
) -> dict:
    raw = await request.body()
    _validate_signature(request, raw, _extract_signature_header(request))
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json")

    dedupe = _dedupe_key(payload, "status")
    if db.query(RawWebhookEvent).filter_by(dedupe_key=dedupe).first():
        return {"ok": True, "dedupe": True}

    raw_event = RawWebhookEvent(
        provider="aisensy",
        kind="status",
        dedupe_key=dedupe,
        payload=payload,
    )
    db.add(raw_event)
    db.commit()

    normalized = normalize_status(payload)
    if normalized is None:
        raw_event.processed = True
        db.commit()
        return {"ok": True, "processed": False}

    apply_status(db, normalized)
    raw_event.processed = True
    db.commit()
    return {"ok": True}
