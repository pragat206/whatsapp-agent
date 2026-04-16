"""Lightweight operational analytics."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, db_dep
from app.models.ai_run import AiRun
from app.models.campaign import Campaign, CampaignRecipient, CampaignRecipientStatus, CampaignStatus
from app.models.conversation import Conversation, ConversationState, HandoffEvent
from app.models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    day = now - dt.timedelta(hours=24)

    conv_counts = dict(
        db.execute(
            select(Conversation.state, func.count()).group_by(Conversation.state)
        ).all()
    )
    conv_counts_by_state = {s.value: conv_counts.get(s, 0) for s in ConversationState}

    campaigns_active = db.scalar(
        select(func.count())
        .select_from(Campaign)
        .where(Campaign.status.in_([CampaignStatus.sending, CampaignStatus.scheduled]))
    ) or 0

    recip_24h = dict(
        db.execute(
            select(CampaignRecipient.status, func.count())
            .where(CampaignRecipient.sent_at >= day)
            .group_by(CampaignRecipient.status)
        ).all()
    )
    recip_by_status = {s.value: recip_24h.get(s, 0) for s in CampaignRecipientStatus}

    ai_24h = dict(
        db.execute(
            select(AiRun.outcome, func.count())
            .where(AiRun.created_at >= day)
            .group_by(AiRun.outcome)
        ).all()
    )

    takeovers_24h = db.scalar(
        select(func.count())
        .select_from(HandoffEvent)
        .where(HandoffEvent.kind.in_(["takeover", "external"]))
        .where(HandoffEvent.created_at >= day)
    ) or 0

    return {
        "conversations": conv_counts_by_state,
        "active_conversations": sum(conv_counts_by_state.values())
        - conv_counts_by_state.get("CLOSED", 0),
        "campaigns_active": campaigns_active,
        "recipients_last_24h": recip_by_status,
        "ai_runs_last_24h": ai_24h,
        "takeovers_last_24h": takeovers_24h,
    }
