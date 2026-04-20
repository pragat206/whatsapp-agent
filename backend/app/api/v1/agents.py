"""Agent profiles API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, db_dep, require_roles
from app.models.agent import AgentProfile, AgentProfileKbLink
from app.models.knowledge import KnowledgeBase
from app.models.user import Role, User
from app.schemas.agent import (
    AgentProfileCreate,
    AgentProfileOut,
    AgentProfileUpdate,
    AttachKbRequest,
)
from app.schemas.kb import KbOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentProfileOut, status_code=201)
def create_agent(
    body: AgentProfileCreate,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> AgentProfileOut:
    profile = AgentProfile(**body.model_dump())
    db.add(profile)
    db.commit()
    return AgentProfileOut.model_validate(profile)


@router.get("", response_model=list[AgentProfileOut])
def list_agents(
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> list[AgentProfileOut]:
    rows = db.execute(select(AgentProfile).order_by(AgentProfile.name)).scalars().all()
    return [AgentProfileOut.model_validate(r) for r in rows]


def _get(db: Session, agent_id: uuid.UUID) -> AgentProfile:
    p = db.get(AgentProfile, agent_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent profile not found")
    return p


@router.patch("/{agent_id}", response_model=AgentProfileOut)
def update_agent(
    agent_id: uuid.UUID,
    body: AgentProfileUpdate,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> AgentProfileOut:
    profile = _get(db, agent_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("is_default"):
        # Only one default agent at a time.
        for other in db.execute(select(AgentProfile).where(AgentProfile.is_default.is_(True))).scalars().all():
            other.is_default = False
    for k, v in data.items():
        setattr(profile, k, v)
    db.commit()
    return AgentProfileOut.model_validate(profile)


@router.get("/{agent_id}/kbs", response_model=list[KbOut])
def list_agent_kbs(
    agent_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> list[KbOut]:
    _get(db, agent_id)
    rows = (
        db.execute(
            select(KnowledgeBase)
            .join(AgentProfileKbLink, AgentProfileKbLink.kb_id == KnowledgeBase.id)
            .where(AgentProfileKbLink.agent_profile_id == agent_id)
            .order_by(KnowledgeBase.name)
        )
        .scalars()
        .all()
    )
    return [KbOut.model_validate(k) for k in rows]


@router.post("/{agent_id}/kbs", status_code=201)
def attach_kb(
    agent_id: uuid.UUID,
    body: AttachKbRequest,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> dict:
    _get(db, agent_id)
    existing = db.scalar(
        select(AgentProfileKbLink)
        .where(AgentProfileKbLink.agent_profile_id == agent_id)
        .where(AgentProfileKbLink.kb_id == body.kb_id)
    )
    if existing:
        return {"ok": True, "duplicate": True}
    db.add(AgentProfileKbLink(agent_profile_id=agent_id, kb_id=body.kb_id))
    db.commit()
    return {"ok": True}


@router.delete("/{agent_id}/kbs/{kb_id}")
def detach_kb(
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> dict:
    link = db.scalar(
        select(AgentProfileKbLink)
        .where(AgentProfileKbLink.agent_profile_id == agent_id)
        .where(AgentProfileKbLink.kb_id == kb_id)
    )
    if link:
        db.delete(link)
        db.commit()
    return {"ok": True}
