from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPk


class ConversationState(str, enum.Enum):
    AI_ACTIVE = "AI_ACTIVE"
    AI_PAUSED = "AI_PAUSED"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    CLOSED = "CLOSED"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class MessageStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"
    received = "received"


class Conversation(UUIDPk, Timestamped, Base):
    __tablename__ = "conversations"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    state: Mapped[ConversationState] = mapped_column(
        Enum(ConversationState, name="conversation_state"),
        default=ConversationState.AI_ACTIVE,
        nullable=False,
        index=True,
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    last_inbound_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_outbound_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_preview: Mapped[str | None] = mapped_column(String(500))
    unread_count: Mapped[int] = mapped_column(default=0, nullable=False)
    source_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True, index=True
    )
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    contact = relationship("Contact")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(UUIDPk, Timestamped, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction"), nullable=False
    )
    sender_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # user | ai | human
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_url: Mapped[str | None] = mapped_column(String(1000))
    media_type: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status"),
        default=MessageStatus.queued,
        nullable=False,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(120), index=True)
    provider_payload: Mapped[dict | None] = mapped_column(JSON)
    template_name: Mapped[str | None] = mapped_column(String(120))
    template_params: Mapped[list | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))

    conversation = relationship("Conversation", back_populates="messages")


Index(
    "ix_messages_conversation_created",
    Message.conversation_id,
    Message.created_at,
)


class MessageStatusEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "message_status_events"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False, index=True
    )
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status"), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSON)


class ConversationStateLog(UUIDPk, Timestamped, Base):
    __tablename__ = "conversation_state_logs"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    from_state: Mapped[ConversationState | None] = mapped_column(
        Enum(ConversationState, name="conversation_state")
    )
    to_state: Mapped[ConversationState] = mapped_column(
        Enum(ConversationState, name="conversation_state"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(500))


class HandoffEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "handoff_events"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # takeover | pause | resume | close | external
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="dashboard")
    details: Mapped[dict | None] = mapped_column(JSON)
