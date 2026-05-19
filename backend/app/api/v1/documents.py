"""Documents API: browse every customer-shared attachment in one place.

The inbox renders attachments inside each conversation, but operators
also need a single-pane view to triage incoming bills/Aadhaar/photos
without opening every chat. This module powers the standalone
``/documents`` dashboard page.

Filtering supported:
- ``kind=image|document|audio|video`` — coarse media classification
- ``q=<text>``                       — substring match on contact name
                                       or phone (E.164)
- pagination via ``limit`` and ``offset``

Files are served by the existing
``GET /inbox/messages/{message_id}/media`` endpoint — this router only
returns metadata so the frontend can list and link to each file.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user, db_dep
from app.models.contact import Contact
from app.models.conversation import (
    Conversation,
    Message,
    MessageDirection,
)
from app.models.user import User
from app.schemas.common import Page

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: uuid.UUID
    conversation_id: uuid.UUID
    contact_id: uuid.UUID
    contact_name: str | None
    contact_phone: str
    media_type: str | None
    local_media_path: str | None
    media_url: str | None
    body_preview: str
    created_at: dt.datetime


_IMAGE_HINTS = {"image", "photo", "img"}
_AUDIO_HINTS = {"audio", "voice", "ptt"}
_VIDEO_HINTS = {"video"}


def _classify(media_type: str | None, path: str | None) -> str:
    """Map AiSensy/WhatsApp media_type or a file extension to a coarse kind."""
    mt = (media_type or "").lower().strip()
    if mt.startswith("image/") or mt in _IMAGE_HINTS:
        return "image"
    if mt.startswith("audio/") or mt in _AUDIO_HINTS:
        return "audio"
    if mt.startswith("video/") or mt in _VIDEO_HINTS:
        return "video"
    ext = ""
    if path:
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext in {"jpg", "jpeg", "png", "gif", "webp"}:
        return "image"
    if ext in {"mp3", "ogg", "oga", "m4a", "wav", "amr"}:
        return "audio"
    if ext in {"mp4", "mov", "3gp", "webm"}:
        return "video"
    return "document"


@router.get("", response_model=Page[DocumentEntry])
def list_documents(
    kind: Literal["image", "document", "audio", "video"] | None = None,
    q: str | None = Query(None, description="Substring match on contact name or phone"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> Page[DocumentEntry]:
    """List every inbound attachment the chatbot has received.

    Only inbound messages are returned — outbound media is operator-sent
    and already known to the dashboard. We surface both the local copy
    (when ``user_uploads`` saved it) and the original provider URL so the
    UI can fall back gracefully on either.
    """
    base = (
        select(Message)
        .options(selectinload(Message.conversation).selectinload(Conversation.contact))
        .where(Message.direction == MessageDirection.inbound)
        .where(
            or_(
                Message.local_media_path.isnot(None),
                Message.media_url.isnot(None),
            )
        )
    )
    if q:
        like = f"%{q.strip()}%"
        base = base.join(Message.conversation).join(Conversation.contact).where(
            or_(Contact.name.ilike(like), Contact.phone_e164.ilike(like))
        )

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    rows = (
        db.execute(base.order_by(Message.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )

    items: list[DocumentEntry] = []
    for m in rows:
        # Coarse-classify here so we can post-filter; doing the same in SQL
        # would require either a stored kind column or messy LIKE chains.
        m_kind = _classify(m.media_type, m.local_media_path or m.media_url)
        if kind and m_kind != kind:
            continue
        contact = m.conversation.contact if m.conversation else None
        items.append(
            DocumentEntry(
                message_id=m.id,
                conversation_id=m.conversation_id,
                contact_id=contact.id if contact else uuid.UUID(int=0),
                contact_name=contact.name if contact else None,
                contact_phone=contact.phone_e164 if contact else "",
                media_type=m.media_type,
                local_media_path=m.local_media_path,
                media_url=m.media_url,
                body_preview=(m.body or "").strip()[:140],
                created_at=m.created_at,
            )
        )

    return Page[DocumentEntry](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
