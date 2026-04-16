"""Conversation state machine + handoff logic.

Rules enforced here:

* Default new conversation  -> AI_ACTIVE
* Human sends from dashboard -> HUMAN_ACTIVE (AI stops immediately)
* External/mobile takeover   -> HUMAN_ACTIVE (AI stops immediately)
* Manual pause               -> AI_PAUSED
* Only explicit resume moves back to AI_ACTIVE
* All transitions produce a ConversationStateLog and HandoffEvent entry
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import (
    Conversation,
    ConversationState,
    ConversationStateLog,
    HandoffEvent,
)
from app.utils.audit import audit


def _transition(
    db: Session,
    conversation: Conversation,
    to_state: ConversationState,
    *,
    actor_user_id: uuid.UUID | None,
    reason: str | None,
) -> None:
    if conversation.state == to_state:
        return
    db.add(
        ConversationStateLog(
            conversation_id=conversation.id,
            from_state=conversation.state,
            to_state=to_state,
            actor_user_id=actor_user_id,
            reason=reason,
        )
    )
    conversation.state = to_state


def can_ai_respond(conversation: Conversation) -> bool:
    return conversation.state == ConversationState.AI_ACTIVE


def take_over(
    db: Session,
    conversation: Conversation,
    *,
    actor_user_id: uuid.UUID,
    source: str = "dashboard",
) -> None:
    """Operator takes over. AI must stop immediately."""
    _transition(
        db,
        conversation,
        ConversationState.HUMAN_ACTIVE,
        actor_user_id=actor_user_id,
        reason=f"human takeover via {source}",
    )
    conversation.assigned_user_id = actor_user_id
    db.add(
        HandoffEvent(
            conversation_id=conversation.id,
            kind="takeover",
            actor_user_id=actor_user_id,
            source=source,
        )
    )
    audit(
        db,
        action="conversation.takeover",
        entity_type="conversation",
        entity_id=conversation.id,
        actor_user_id=actor_user_id,
        details={"source": source},
    )


def external_takeover(
    db: Session, conversation: Conversation, *, source: str = "provider"
) -> None:
    """A human replied via AiSensy inbox or mobile — pause AI immediately."""
    if conversation.state in (ConversationState.HUMAN_ACTIVE, ConversationState.CLOSED):
        return
    _transition(
        db,
        conversation,
        ConversationState.HUMAN_ACTIVE,
        actor_user_id=None,
        reason=f"external human intervention via {source}",
    )
    db.add(
        HandoffEvent(
            conversation_id=conversation.id,
            kind="external",
            actor_user_id=None,
            source=source,
        )
    )
    audit(
        db,
        action="conversation.external_takeover",
        entity_type="conversation",
        entity_id=conversation.id,
        details={"source": source},
    )


def pause_ai(
    db: Session,
    conversation: Conversation,
    *,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> None:
    _transition(
        db,
        conversation,
        ConversationState.AI_PAUSED,
        actor_user_id=actor_user_id,
        reason=reason or "manual pause",
    )
    db.add(
        HandoffEvent(
            conversation_id=conversation.id,
            kind="pause",
            actor_user_id=actor_user_id,
            source="dashboard",
        )
    )
    audit(
        db,
        action="conversation.ai_paused",
        entity_type="conversation",
        entity_id=conversation.id,
        actor_user_id=actor_user_id,
    )


def resume_ai(
    db: Session,
    conversation: Conversation,
    *,
    actor_user_id: uuid.UUID,
) -> None:
    _transition(
        db,
        conversation,
        ConversationState.AI_ACTIVE,
        actor_user_id=actor_user_id,
        reason="resume ai",
    )
    conversation.assigned_user_id = None
    db.add(
        HandoffEvent(
            conversation_id=conversation.id,
            kind="resume",
            actor_user_id=actor_user_id,
            source="dashboard",
        )
    )
    audit(
        db,
        action="conversation.ai_resumed",
        entity_type="conversation",
        entity_id=conversation.id,
        actor_user_id=actor_user_id,
    )


def close(
    db: Session,
    conversation: Conversation,
    *,
    actor_user_id: Optional[uuid.UUID] = None,
) -> None:
    _transition(
        db,
        conversation,
        ConversationState.CLOSED,
        actor_user_id=actor_user_id,
        reason="closed",
    )
    db.add(
        HandoffEvent(
            conversation_id=conversation.id,
            kind="close",
            actor_user_id=actor_user_id,
            source="dashboard",
        )
    )
    audit(
        db,
        action="conversation.closed",
        entity_type="conversation",
        entity_id=conversation.id,
        actor_user_id=actor_user_id,
    )
