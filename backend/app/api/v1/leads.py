"""Leads API.

Surfaces the lead-tracking columns on `contacts` (lead_status,
lead_next_action, lead_summary, etc.) as a dedicated dashboard tab.

Conceptually a "lead" is a Contact with at least one inbound or outbound
message — i.e., someone we've actually talked to. Pure address-book
contacts (created via campaign upload but never replied) are filtered out
by default but can be included with `?include_silent=true`.

Endpoints:
  * GET  /leads                  — paginated list, filterable by status/q/next_action
  * GET  /leads/{contact_id}     — detail with current conversation
  * PATCH /leads/{contact_id}    — operator override of status/next_action/notes
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user, db_dep
from app.models.contact import Contact
from app.models.conversation import Conversation, Message
from app.models.user import User

router = APIRouter(prefix="/leads", tags=["leads"])


# -------------------- Schemas --------------------


class LeadOut(BaseModel):
    contact_id: uuid.UUID
    phone_e164: str
    name: str | None = None
    city: str | None = None
    state: str | None = None
    property_type: str | None = None
    monthly_bill: str | None = None
    lead_status: str | None = None
    lead_next_action: str | None = None
    lead_next_action_at: dt.datetime | None = None
    lead_summary: str | None = None
    lead_score: int | None = None
    lead_extracted_attributes: dict = Field(default_factory=dict)
    lead_updated_at: dt.datetime | None = None
    last_message_at: dt.datetime | None = None
    message_count: int = 0


class LeadDetail(LeadOut):
    recent_messages: list[dict] = Field(default_factory=list)
    conversation_state: str | None = None
    conversation_id: uuid.UUID | None = None


class LeadPage(BaseModel):
    items: list[LeadOut]
    total: int
    limit: int
    offset: int


class LeadUpdateRequest(BaseModel):
    lead_status: str | None = None
    lead_next_action: str | None = None
    lead_next_action_at: dt.datetime | None = None
    lead_summary: str | None = None
    lead_score: int | None = Field(None, ge=0, le=100)
    notes: str | None = None


# -------------------- Helpers --------------------


_VALID_STATUSES = {
    "new",
    "contacted",
    "interested",
    "qualified",
    "hot",
    "converted",
    "lost",
    "nurturing",
}


def _last_message_subq(db: Session):
    """Subquery returning latest message timestamp + count per conversation."""
    return (
        select(
            Conversation.contact_id.label("contact_id"),
            func.max(Message.created_at).label("last_at"),
            func.count(Message.id).label("msg_count"),
        )
        .join(Message, Message.conversation_id == Conversation.id)
        .group_by(Conversation.contact_id)
        .subquery()
    )


def _to_out(contact: Contact, last_at, msg_count) -> LeadOut:
    return LeadOut(
        contact_id=contact.id,
        phone_e164=contact.phone_e164,
        name=contact.name,
        city=contact.city,
        state=contact.state,
        property_type=contact.property_type,
        monthly_bill=contact.monthly_bill,
        lead_status=contact.lead_status,
        lead_next_action=contact.lead_next_action,
        lead_next_action_at=contact.lead_next_action_at,
        lead_summary=contact.lead_summary,
        lead_score=contact.lead_score,
        lead_extracted_attributes=contact.lead_extracted_attributes or {},
        lead_updated_at=contact.lead_updated_at,
        last_message_at=last_at,
        message_count=int(msg_count or 0),
    )


# -------------------- Routes --------------------


@router.get("", response_model=LeadPage)
def list_leads(
    status_filter: str | None = Query(None, alias="status", description="Filter by lead_status"),
    q: str | None = Query(None, description="Match against name/phone/city/summary"),
    next_action: str | None = Query(None, description="Substring match on lead_next_action"),
    include_silent: bool = Query(
        False,
        description="If true, include contacts with no messages (e.g. campaign uploads).",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> LeadPage:
    last_msg = _last_message_subq(db)

    base = (
        select(Contact, last_msg.c.last_at, last_msg.c.msg_count)
        .join(last_msg, last_msg.c.contact_id == Contact.id, isouter=include_silent)
    )

    if status_filter:
        base = base.where(Contact.lead_status == status_filter.lower())
    if next_action:
        base = base.where(Contact.lead_next_action.ilike(f"%{next_action}%"))
    if q:
        like = f"%{q.strip()}%"
        base = base.where(
            or_(
                Contact.name.ilike(like),
                Contact.phone_e164.ilike(like),
                Contact.city.ilike(like),
                Contact.lead_summary.ilike(like),
            )
        )

    # Most recently updated leads first; fall back to last message activity.
    sortable = base.order_by(
        desc(func.coalesce(Contact.lead_updated_at, last_msg.c.last_at, Contact.created_at))
    )

    total = db.scalar(select(func.count()).select_from(sortable.subquery())) or 0
    rows = db.execute(sortable.limit(limit).offset(offset)).all()

    items = [_to_out(contact, last_at, msg_count) for contact, last_at, msg_count in rows]
    return LeadPage(items=items, total=int(total), limit=limit, offset=offset)


@router.get("/{contact_id}", response_model=LeadDetail)
def get_lead(
    contact_id: uuid.UUID,
    message_limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> LeadDetail:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lead not found")

    last_msg = _last_message_subq(db)
    row = db.execute(
        select(last_msg.c.last_at, last_msg.c.msg_count).where(
            last_msg.c.contact_id == contact_id
        )
    ).one_or_none()
    last_at, msg_count = (row[0], row[1]) if row else (None, 0)

    convo = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.contact_id == contact_id)
        .order_by(desc(Conversation.updated_at))
        .limit(1)
    )

    recent_messages: list[dict] = []
    convo_state: str | None = None
    convo_id: uuid.UUID | None = None
    if convo is not None:
        convo_state = convo.state.value if hasattr(convo.state, "value") else str(convo.state)
        convo_id = convo.id
        msgs = sorted(convo.messages or [], key=lambda m: m.created_at)[-message_limit:]
        for m in msgs:
            direction = m.direction.value if hasattr(m.direction, "value") else str(m.direction)
            recent_messages.append(
                {
                    "id": str(m.id),
                    "direction": direction,
                    "body": m.body,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "sender_kind": getattr(m, "sender_kind", None),
                }
            )

    out = _to_out(contact, last_at, msg_count)
    return LeadDetail(
        **out.model_dump(),
        recent_messages=recent_messages,
        conversation_state=convo_state,
        conversation_id=convo_id,
    )


@router.patch("/{contact_id}", response_model=LeadOut)
def update_lead(
    contact_id: uuid.UUID,
    body: LeadUpdateRequest,
    db: Session = Depends(db_dep),
    user: User = Depends(current_user),
) -> LeadOut:
    """Operator override of lead fields. Updates `lead_updated_at` so the
    extractor knows a human edited this row."""
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lead not found")

    data = body.model_dump(exclude_unset=True)
    if "lead_status" in data and data["lead_status"]:
        v = data["lead_status"].strip().lower()
        if v not in _VALID_STATUSES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"lead_status must be one of {sorted(_VALID_STATUSES)}",
            )
        contact.lead_status = v
    if "lead_next_action" in data:
        contact.lead_next_action = (data["lead_next_action"] or None)
    if "lead_next_action_at" in data:
        contact.lead_next_action_at = data["lead_next_action_at"]
    if "lead_summary" in data:
        contact.lead_summary = (data["lead_summary"] or None)
    if "lead_score" in data:
        contact.lead_score = data["lead_score"]
    if "notes" in data and data["notes"] is not None:
        contact.notes = data["notes"][:1000]

    contact.lead_updated_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(contact)

    last_msg = _last_message_subq(db)
    row = db.execute(
        select(last_msg.c.last_at, last_msg.c.msg_count).where(
            last_msg.c.contact_id == contact_id
        )
    ).one_or_none()
    last_at, msg_count = (row[0], row[1]) if row else (None, 0)
    return _to_out(contact, last_at, msg_count)
