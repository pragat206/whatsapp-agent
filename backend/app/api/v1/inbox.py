"""Inbox API: conversations list, detail, send, takeover, pause, resume, close."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user, db_dep
from app.integrations.aisensy import SessionSendPayload
from app.integrations.aisensy.client import get_aisensy_client
from app.models.conversation import Conversation, ConversationState, Message
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    MessageOut,
    SendMessageRequest,
    StateChangeRequest,
)
from app.services.conversation.repo import add_outbound_message, mark_failed, mark_sent
from app.services.conversation.state import (
    close as close_conversation,
    pause_ai,
    resume_ai,
    take_over,
)
from app.services.messaging.window import in_service_window
from app.utils.retries import ProviderPermanentError, ProviderTransientError

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("/conversations", response_model=Page[ConversationSummary])
def list_conversations(
    state: ConversationState | None = None,
    unread_only: bool = False,
    campaign_only: bool = False,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> Page[ConversationSummary]:
    stmt = select(Conversation).options(selectinload(Conversation.contact))
    if state:
        stmt = stmt.where(Conversation.state == state)
    if unread_only:
        stmt = stmt.where(Conversation.unread_count > 0)
    if campaign_only:
        stmt = stmt.where(Conversation.source_campaign_id.isnot(None))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (
        db.execute(stmt.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return Page[ConversationSummary](
        items=[ConversationSummary.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def _get(db: Session, conversation_id: uuid.UUID) -> Conversation:
    convo = db.get(Conversation, conversation_id)
    if convo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return convo


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(
    conversation_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> ConversationDetail:
    convo = (
        db.query(Conversation)
        .options(selectinload(Conversation.contact), selectinload(Conversation.messages))
        .filter(Conversation.id == conversation_id)
        .one_or_none()
    )
    if convo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    convo.unread_count = 0  # mark read on open
    db.commit()
    detail = ConversationDetail.model_validate(convo)
    detail.messages = [MessageOut.model_validate(m) for m in convo.messages]
    return detail


@router.post("/conversations/{conversation_id}/takeover")
def takeover(
    conversation_id: uuid.UUID,
    db: Session = Depends(db_dep),
    user: User = Depends(current_user),
) -> dict:
    convo = _get(db, conversation_id)
    take_over(db, convo, actor_user_id=user.id)
    db.commit()
    return {"ok": True, "state": convo.state.value}


@router.post("/conversations/{conversation_id}/pause-ai")
def pause(
    conversation_id: uuid.UUID,
    body: StateChangeRequest,
    db: Session = Depends(db_dep),
    user: User = Depends(current_user),
) -> dict:
    convo = _get(db, conversation_id)
    pause_ai(db, convo, actor_user_id=user.id, reason=body.reason)
    db.commit()
    return {"ok": True, "state": convo.state.value}


@router.post("/conversations/{conversation_id}/resume-ai")
def resume(
    conversation_id: uuid.UUID,
    db: Session = Depends(db_dep),
    user: User = Depends(current_user),
) -> dict:
    convo = _get(db, conversation_id)
    resume_ai(db, convo, actor_user_id=user.id)
    db.commit()
    return {"ok": True, "state": convo.state.value}


@router.post("/conversations/{conversation_id}/close")
def close(
    conversation_id: uuid.UUID,
    db: Session = Depends(db_dep),
    user: User = Depends(current_user),
) -> dict:
    convo = _get(db, conversation_id)
    close_conversation(db, convo, actor_user_id=user.id)
    db.commit()
    return {"ok": True, "state": convo.state.value}


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def send_human_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    db: Session = Depends(db_dep),
    user: User = Depends(current_user),
) -> MessageOut:
    convo = _get(db, conversation_id)

    # Sending from dashboard = human takeover, immediately.
    if convo.state != ConversationState.HUMAN_ACTIVE:
        take_over(db, convo, actor_user_id=user.id)

    if not in_service_window(convo):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Conversation is outside the 24h service window. Use a template campaign instead.",
        )

    msg = add_outbound_message(
        db,
        conversation=convo,
        body=body.body,
        sender_kind="human",
        sender_user_id=user.id,
        media_url=body.media_url,
        media_type=body.media_type,
    )
    db.commit()

    try:
        resp = get_aisensy_client().send_session_message(
            SessionSendPayload(
                destination=convo.contact.phone_e164,
                body=body.body,
                media_url=body.media_url,
                media_type=body.media_type,
            )
        )
    except (ProviderTransientError, ProviderPermanentError) as exc:
        mark_failed(db, msg, error=str(exc))
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"provider error: {exc}")

    mark_sent(db, msg, provider_message_id=_first_id(resp), payload=resp)
    db.commit()
    return MessageOut.model_validate(msg)


def _first_id(resp) -> str | None:
    if not isinstance(resp, dict):
        return None
    for key in ("messageId", "id", "message_id", "providerMessageId"):
        if resp.get(key):
            return str(resp[key])
    data = resp.get("data") or {}
    for key in ("messageId", "id"):
        if data.get(key):
            return str(data[key])
    return None
