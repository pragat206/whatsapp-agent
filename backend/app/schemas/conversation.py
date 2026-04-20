from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.conversation import (
    ConversationState,
    MessageDirection,
    MessageStatus,
)
from app.schemas.contact import ContactOut


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: MessageDirection
    sender_kind: str
    body: str
    media_url: str | None = None
    media_type: str | None = None
    status: MessageStatus
    provider_message_id: str | None = None
    template_name: str | None = None
    error: str | None = None
    created_at: dt.datetime


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state: ConversationState
    contact: ContactOut
    last_inbound_at: dt.datetime | None = None
    last_outbound_at: dt.datetime | None = None
    last_message_preview: str | None = None
    unread_count: int = 0
    source_campaign_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    tags: list[str] = []
    updated_at: dt.datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut] = []


class SendMessageRequest(BaseModel):
    body: str
    media_url: str | None = None
    media_type: str | None = None


class StateChangeRequest(BaseModel):
    reason: str | None = None


class StartConversationRequest(BaseModel):
    phone: str
    name: str | None = None
    body: str
    media_url: str | None = None
    media_type: str | None = None
