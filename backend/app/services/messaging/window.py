"""Service-window guard.

WhatsApp only allows free-form replies inside a ~24h window after the user's
last inbound message. Outside that window, any business-initiated send must go
through an approved template. This module is the single place that answers
"can I send a free-form reply to this conversation right now?".
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation import Conversation


def in_service_window(conversation: Conversation, now: dt.datetime | None = None) -> bool:
    settings = get_settings()
    now = now or dt.datetime.now(dt.timezone.utc)
    last = conversation.last_inbound_at
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=dt.timezone.utc)
    delta = now - last
    return delta <= dt.timedelta(hours=settings.service_window_hours)


def assert_window(db: Session, conversation: Conversation) -> None:
    """Raises ValueError if outside service window. Caller must handle."""
    if not in_service_window(conversation):
        raise OutOfServiceWindow(
            "Conversation is outside the service window; use a template or escalate."
        )


class OutOfServiceWindow(Exception):
    pass
