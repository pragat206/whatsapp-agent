"""Apply an outbound status webhook to a message + campaign recipient."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.aisensy.schemas import NormalizedStatus
from app.models.campaign import CampaignRecipient, CampaignRecipientEvent, CampaignRecipientStatus
from app.models.conversation import Message, MessageStatus, MessageStatusEvent


def _map_status(s: str) -> MessageStatus:
    try:
        return MessageStatus(s)
    except ValueError:
        return MessageStatus.sent


def apply_status(db: Session, event: NormalizedStatus) -> None:
    # Update message status (if we own it)
    msg = db.scalar(
        select(Message).where(Message.provider_message_id == event.provider_message_id)
    )
    if msg:
        msg.status = _map_status(event.status)
        if event.error:
            msg.error = event.error[:500]
        db.add(
            MessageStatusEvent(
                message_id=msg.id,
                status=msg.status,
                raw=event.raw,
            )
        )

    # Update campaign recipient status (if this was a campaign send)
    recipient = db.scalar(
        select(CampaignRecipient).where(
            CampaignRecipient.provider_message_id == event.provider_message_id
        )
    )
    if recipient:
        now = dt.datetime.now(dt.timezone.utc)
        if event.status == "delivered":
            recipient.status = CampaignRecipientStatus.delivered
            recipient.delivered_at = event.at or now
        elif event.status == "read":
            recipient.status = CampaignRecipientStatus.read
            recipient.read_at = event.at or now
        elif event.status == "failed":
            recipient.status = CampaignRecipientStatus.failed
            recipient.error = (event.error or "")[:1000]
        db.add(
            CampaignRecipientEvent(
                recipient_id=recipient.id,
                kind=event.status,
                raw=event.raw,
            )
        )
    db.commit()
