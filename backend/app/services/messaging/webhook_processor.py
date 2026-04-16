"""Processes a normalized inbound event.

Steps:
 1. Upsert contact from phone.
 2. Open or reuse conversation.
 3. Attribute to campaign if applicable.
 4. If provider signaled human_intervention, mark HUMAN_ACTIVE before storing
    (AI must never answer after this).
 5. Store message and update conversation preview/unread.
 6. Enqueue AI run if still AI_ACTIVE (worker will re-check state).

Idempotency is enforced at the HTTP layer via `raw_webhook_events.dedupe_key`.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.redis import lock
from app.integrations.aisensy.schemas import NormalizedInbound
from app.models.conversation import ConversationState
from app.services.campaign.attribution import attribute_reply
from app.services.conversation.repo import (
    add_inbound_message,
    get_or_create_contact,
    get_or_open_conversation,
)
from app.services.conversation.state import external_takeover

logger = get_logger("messaging.processor")


def process_inbound(db: Session, event: NormalizedInbound) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Returns (conversation_id, message_id) or None if skipped."""
    key = f"inbound-lock:{event.from_phone_e164}"
    with lock(key, ttl_ms=15_000, wait_ms=3_000) as acquired:
        if not acquired:
            logger.info("inbound_lock_busy", phone=event.from_phone_e164)
            return None

        contact = get_or_create_contact(
            db, phone_e164=event.from_phone_e164, name=event.contact_name
        )

        source_campaign_id = attribute_reply(db, phone_e164=event.from_phone_e164)
        conversation = get_or_open_conversation(
            db, contact=contact, source_campaign_id=source_campaign_id
        )

        if event.human_intervention:
            external_takeover(db, conversation, source="provider")

        msg = add_inbound_message(
            db,
            conversation=conversation,
            body=event.text,
            provider_message_id=event.provider_message_id,
            media_url=event.media_url,
            media_type=event.media_type,
            received_at=event.received_at,
        )

        db.commit()

        if conversation.state == ConversationState.AI_ACTIVE:
            return conversation.id, msg.id
        return None
