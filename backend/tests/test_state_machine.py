"""Conversation state machine tests — no DB required (in-memory mock)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.models.conversation import Conversation, ConversationState
from app.services.conversation.state import (
    can_ai_respond,
    external_takeover,
    pause_ai,
    resume_ai,
    take_over,
)


def _convo():
    c = Conversation(state=ConversationState.AI_ACTIVE)
    c.id = uuid.uuid4()
    return c


def test_default_state_allows_ai():
    assert can_ai_respond(_convo()) is True


def test_takeover_blocks_ai():
    db = MagicMock()
    c = _convo()
    take_over(db, c, actor_user_id=uuid.uuid4())
    assert c.state == ConversationState.HUMAN_ACTIVE
    assert can_ai_respond(c) is False


def test_external_takeover_blocks_ai():
    db = MagicMock()
    c = _convo()
    external_takeover(db, c, source="provider")
    assert c.state == ConversationState.HUMAN_ACTIVE
    assert can_ai_respond(c) is False


def test_pause_then_resume():
    db = MagicMock()
    c = _convo()
    pause_ai(db, c, actor_user_id=uuid.uuid4())
    assert c.state == ConversationState.AI_PAUSED
    assert can_ai_respond(c) is False
    resume_ai(db, c, actor_user_id=uuid.uuid4())
    assert c.state == ConversationState.AI_ACTIVE
    assert can_ai_respond(c) is True


def test_resume_does_not_leak_assignment():
    db = MagicMock()
    c = _convo()
    take_over(db, c, actor_user_id=uuid.uuid4())
    resume_ai(db, c, actor_user_id=uuid.uuid4())
    assert c.assigned_user_id is None
