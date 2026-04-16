"""Contacts API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, db_dep
from app.models.contact import Contact
from app.models.user import User
from app.schemas.common import Page
from app.schemas.contact import ContactOut

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=Page[ContactOut])
def list_contacts(
    q: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> Page[ContactOut]:
    stmt = select(Contact).order_by(Contact.created_at.desc())
    if q:
        stmt = stmt.where(
            or_(
                Contact.phone_e164.ilike(f"%{q}%"),
                Contact.name.ilike(f"%{q}%"),
                Contact.city.ilike(f"%{q}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return Page[ContactOut](
        items=[ContactOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{contact_id}", response_model=ContactOut)
def contact_detail(
    contact_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> ContactOut:
    c = db.get(Contact, contact_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "contact not found")
    return ContactOut.model_validate(c)
