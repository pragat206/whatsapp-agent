"""Repository-style helpers for conversations, contacts, messages."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.conversation import (
    Conversation,
    ConversationState,
    Message,
    MessageDirection,
    MessageStatus,
)


def get_or_create_contact(
    db: Session,
    *,
    phone_e164: str,
    name: str | None = None,
) -> Contact:
    contact = db.scalar(select(Contact).where(Contact.phone_e164 == phone_e164))
    if contact:
        if name and not contact.name:
            contact.name = name
        return contact
    contact = Contact(phone_e164=phone_e164, name=name)
    db.add(contact)
    db.flush()
    return contact


def get_or_open_conversation(
    db: Session,
    *,
    contact: Contact,
    source_campaign_id: uuid.UUID | None = None,
) -> Conversation:
    convo = db.scalar(
        select(Conversation)
        .where(Conversation.contact_id == contact.id)
        .where(Conversation.state != ConversationState.CLOSED)
        .order_by(Conversation.updated_at.desc())
    )
    if convo:
        if source_campaign_id and not convo.source_campaign_id:
            convo.source_campaign_id = source_campaign_id
        return convo
    convo = Conversation(
        contact_id=contact.id,
        state=ConversationState.AI_ACTIVE,
        source_campaign_id=source_campaign_id,
    )
    db.add(convo)
    db.flush()
    return convo


def add_inbound_message(
    db: Session,
    *,
    conversation: Conversation,
    body: str,
    provider_message_id: str,
    media_url: str | None = None,
    media_type: str | None = None,
    received_at: dt.datetime | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.inbound,
        sender_kind="user",
        body=body,
        media_url=media_url,
        media_type=media_type,
        status=MessageStatus.received,
        provider_message_id=provider_message_id,
    )
    db.add(msg)
    conversation.last_inbound_at = received_at or dt.datetime.now(dt.timezone.utc)
    conversation.last_message_preview = (body or "").strip()[:500]
    conversation.unread_count = (conversation.unread_count or 0) + 1
    db.flush()
    return msg


def add_outbound_message(
    db: Session,
    *,
    conversation: Conversation,
    body: str,
    sender_kind: str,  # "ai" | "human"
    sender_user_id: uuid.UUID | None = None,
    template_name: str | None = None,
    template_params: list | None = None,
    media_url: str | None = None,
    media_type: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.outbound,
        sender_kind=sender_kind,
        sender_user_id=sender_user_id,
        body=body,
        template_name=template_name,
        template_params=template_params,
        media_url=media_url,
        media_type=media_type,
        status=MessageStatus.queued,
    )
    db.add(msg)
    conversation.last_message_preview = body.strip()[:500]
    db.flush()
    return msg


def mark_sent(
    db: Session,
    message: Message,
    *,
    provider_message_id: str | None,
    payload: dict | None,
) -> None:
    message.status = MessageStatus.sent
    message.provider_message_id = provider_message_id
    message.provider_payload = payload
    convo = db.get(Conversation, message.conversation_id)
    if convo:
        convo.last_outbound_at = dt.datetime.now(dt.timezone.utc)


def mark_failed(db: Session, message: Message, *, error: str) -> None:
    message.status = MessageStatus.failed
    message.error = error[:500]
