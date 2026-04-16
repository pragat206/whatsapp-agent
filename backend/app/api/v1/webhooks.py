"""AiSensy webhook endpoints.

Two endpoints are exposed:

  * POST /webhooks/aisensy/inbound   — inbound customer messages
  * POST /webhooks/aisensy/status    — outbound delivery/read/failure events

Both persist the raw payload first (auditability) and are idempotent via
`raw_webhook_events.dedupe_key`. Webhook signature validation is performed if
AiSensy is configured with `AISENSY_WEBHOOK_SECRET`.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
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


def _validate_signature(raw_body: bytes, signature: str | None) -> None:
    settings = get_settings()
    secret = settings.aisensy_webhook_secret
    if not secret:
        return
    # AiSensy sends an HMAC-SHA256 of the body with the configured secret.
    # If the header is missing entirely we still accept in `local` env for
    # developer UX, but reject in non-local.
    if signature is None:
        if settings.app_env != "local":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing signature")
        return
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    # Accept with or without "sha256=" prefix.
    given = signature.lower().replace("sha256=", "").strip()
    if not hmac.compare_digest(digest, given):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")


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
    x_aisensy_signature: str | None = Header(default=None),
) -> dict:
    raw = await request.body()
    _validate_signature(raw, x_aisensy_signature)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json")

    dedupe = _dedupe_key(payload, "inbound")
    existing = db.query(RawWebhookEvent).filter_by(dedupe_key=dedupe).first()
    if existing:
        return {"ok": True, "dedupe": True}

    raw_event = RawWebhookEvent(
        provider="aisensy",
        kind="inbound",
        dedupe_key=dedupe,
        payload=payload,
    )
    db.add(raw_event)
    db.commit()

    try:
        normalized = normalize_inbound(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("normalize_failed", error=str(exc))
        raw_event.error = str(exc)[:500]
        db.commit()
        return {"ok": True, "normalized": False}

    if normalized is None:
        raw_event.processed = True
        db.commit()
        return {"ok": True, "processed": False}

    result = process_inbound(db, normalized)
    raw_event.processed = True
    db.commit()

    if result is not None:
        conversation_id, message_id = result
        enqueue_ai_reply(conversation_id, message_id)

    return {"ok": True}


@router.post("/aisensy/status", status_code=202)
async def aisensy_status(
    request: Request,
    db: Session = Depends(db_dep),
    x_aisensy_signature: str | None = Header(default=None),
) -> dict:
    raw = await request.body()
    _validate_signature(raw, x_aisensy_signature)
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
