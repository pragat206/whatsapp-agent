import datetime as dt

from app.models.conversation import Conversation, ConversationState
from app.services.messaging.window import in_service_window


def _convo(last_inbound: dt.datetime | None) -> Conversation:
    c = Conversation(state=ConversationState.AI_ACTIVE)
    c.last_inbound_at = last_inbound
    return c


def test_no_inbound_means_outside_window():
    assert in_service_window(_convo(None)) is False


def test_recent_inbound_is_in_window():
    recent = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    assert in_service_window(_convo(recent)) is True


def test_old_inbound_is_outside_window():
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=30)
    assert in_service_window(_convo(old)) is False
