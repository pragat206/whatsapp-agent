"""Attribute an inbound reply to the most recent campaign recipient."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.campaign import (
    CampaignRecipient,
    CampaignRecipientStatus,
)


def attribute_reply(db: Session, *, phone_e164: str) -> uuid.UUID | None:
    settings = get_settings()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        hours=settings.campaign_attribution_hours
    )
    recipient = db.scalar(
        select(CampaignRecipient)
        .where(CampaignRecipient.phone_e164 == phone_e164)
        .where(CampaignRecipient.sent_at.isnot(None))
        .where(CampaignRecipient.sent_at >= cutoff)
        .order_by(CampaignRecipient.sent_at.desc())
        .limit(1)
    )
    if recipient is None:
        return None
    if recipient.status not in (
        CampaignRecipientStatus.replied,
        CampaignRecipientStatus.failed,
    ):
        recipient.status = CampaignRecipientStatus.replied
        recipient.replied_at = dt.datetime.now(dt.timezone.utc)
    return recipient.campaign_id
