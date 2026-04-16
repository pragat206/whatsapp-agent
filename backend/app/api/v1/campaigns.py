"""Campaigns API: create, upload CSV, map, schedule, send, list, metrics."""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, db_dep, require_roles
from app.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignStatus,
    CampaignUpload,
)
from app.models.user import Role, User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignMappingConfirm,
    CampaignMetrics,
    CampaignOut,
    CampaignRecipientOut,
    CampaignSchedule,
    INTERNAL_FIELDS,
    UploadPreview,
)
from app.schemas.common import Page
from app.services.campaign.uploader import confirm_mapping, ingest_upload
from app.utils.audit import audit
from app.workers.queue import enqueue_campaign_send

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/internal-fields")
def internal_fields(_: User = Depends(current_user)) -> dict:
    return {"fields": INTERNAL_FIELDS}


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> CampaignOut:
    c = Campaign(
        name=body.name,
        objective=body.objective,
        template_name=body.template_name,
        template_params_schema=body.template_params_schema,
        tags=body.tags,
        source=body.source,
        agent_profile_id=body.agent_profile_id,
        created_by=user.id,
    )
    db.add(c)
    db.flush()
    audit(
        db,
        action="campaign.created",
        entity_type="campaign",
        entity_id=c.id,
        actor_user_id=user.id,
        details={"name": c.name},
    )
    db.commit()
    return CampaignOut.model_validate(c)


@router.get("", response_model=Page[CampaignOut])
def list_campaigns(
    status_filter: CampaignStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> Page[CampaignOut]:
    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    if status_filter:
        stmt = stmt.where(Campaign.status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return Page[CampaignOut](
        items=[CampaignOut.model_validate(c) for c in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _get(db: Session, campaign_id: uuid.UUID) -> Campaign:
    c = db.get(Campaign, campaign_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found")
    return c


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> CampaignOut:
    return CampaignOut.model_validate(_get(db, campaign_id))


@router.post("/{campaign_id}/upload", response_model=UploadPreview)
async def upload_file(
    campaign_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> UploadPreview:
    c = _get(db, campaign_id)
    if c.status in (CampaignStatus.sending, CampaignStatus.completed, CampaignStatus.cancelled):
        raise HTTPException(status.HTTP_409_CONFLICT, f"campaign status {c.status.value} does not accept uploads")
    content = await file.read()
    upload = ingest_upload(db, campaign=c, filename=file.filename or "upload.csv", content=content)
    c.status = CampaignStatus.draft
    db.commit()
    return UploadPreview(
        upload_id=upload.id,
        columns=upload.mapping.get("_columns", []),
        preview_rows=upload.preview,
        total_rows=upload.row_count,
        suggested_mapping=upload.mapping.get("_suggested", {}),
    )


@router.post("/{campaign_id}/uploads/{upload_id}/confirm", response_model=CampaignMetrics)
def confirm_upload_mapping(
    campaign_id: uuid.UUID,
    upload_id: uuid.UUID,
    body: CampaignMappingConfirm,
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> CampaignMetrics:
    c = _get(db, campaign_id)
    upload = db.get(CampaignUpload, upload_id)
    if upload is None or upload.campaign_id != c.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "upload not found")
    try:
        upload = confirm_mapping(
            db,
            campaign=c,
            upload=upload,
            mapping=body.mapping,
            template_param_columns=body.template_param_columns,
            dedupe=body.dedupe,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    c.status = CampaignStatus.mapped
    audit(
        db,
        action="campaign.mapping_confirmed",
        entity_type="campaign",
        entity_id=c.id,
        actor_user_id=user.id,
        details={
            "valid": upload.valid_count,
            "invalid": upload.invalid_count,
            "duplicates": upload.duplicate_count,
        },
    )
    db.commit()
    return _metrics(db, c.id, total=upload.row_count, valid=upload.valid_count, invalid=upload.invalid_count)


@router.post("/{campaign_id}/schedule", response_model=CampaignOut)
def schedule(
    campaign_id: uuid.UUID,
    body: CampaignSchedule,
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> CampaignOut:
    c = _get(db, campaign_id)
    c.scheduled_at = body.scheduled_at
    c.status = CampaignStatus.scheduled
    audit(db, action="campaign.scheduled", entity_type="campaign", entity_id=c.id, actor_user_id=user.id)
    db.commit()
    return CampaignOut.model_validate(c)


@router.post("/{campaign_id}/send-now", response_model=CampaignOut)
def send_now(
    campaign_id: uuid.UUID,
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> CampaignOut:
    c = _get(db, campaign_id)
    if c.status not in (CampaignStatus.mapped, CampaignStatus.scheduled, CampaignStatus.paused):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot send from status {c.status.value}")
    c.status = CampaignStatus.sending
    c.started_at = c.started_at or dt.datetime.now(dt.timezone.utc)
    audit(db, action="campaign.send_now", entity_type="campaign", entity_id=c.id, actor_user_id=user.id)
    db.commit()
    enqueue_campaign_send(c.id)
    return CampaignOut.model_validate(c)


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
def pause(
    campaign_id: uuid.UUID,
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> CampaignOut:
    c = _get(db, campaign_id)
    if c.status != CampaignStatus.sending:
        raise HTTPException(status.HTTP_409_CONFLICT, "only sending campaigns can be paused")
    c.status = CampaignStatus.paused
    audit(db, action="campaign.paused", entity_type="campaign", entity_id=c.id, actor_user_id=user.id)
    db.commit()
    return CampaignOut.model_validate(c)


@router.post("/{campaign_id}/cancel", response_model=CampaignOut)
def cancel(
    campaign_id: uuid.UUID,
    db: Session = Depends(db_dep),
    user: User = Depends(require_roles(Role.admin, Role.campaign_manager)),
) -> CampaignOut:
    c = _get(db, campaign_id)
    if c.status in (CampaignStatus.completed, CampaignStatus.cancelled):
        raise HTTPException(status.HTTP_409_CONFLICT, "already finished")
    c.status = CampaignStatus.cancelled
    audit(db, action="campaign.cancelled", entity_type="campaign", entity_id=c.id, actor_user_id=user.id)
    db.commit()
    return CampaignOut.model_validate(c)


@router.get("/{campaign_id}/recipients", response_model=Page[CampaignRecipientOut])
def list_recipients(
    campaign_id: uuid.UUID,
    status_filter: CampaignRecipientStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> Page[CampaignRecipientOut]:
    stmt = select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign_id)
    if status_filter:
        stmt = stmt.where(CampaignRecipient.status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return Page[CampaignRecipientOut](
        items=[CampaignRecipientOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{campaign_id}/metrics", response_model=CampaignMetrics)
def metrics(
    campaign_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> CampaignMetrics:
    return _metrics(db, campaign_id)


def _metrics(
    db: Session,
    campaign_id: uuid.UUID,
    *,
    total: int | None = None,
    valid: int | None = None,
    invalid: int | None = None,
) -> CampaignMetrics:
    counts_by_status: dict[str, int] = {}
    rows = db.execute(
        select(CampaignRecipient.status, func.count())
        .where(CampaignRecipient.campaign_id == campaign_id)
        .group_by(CampaignRecipient.status)
    ).all()
    for s, n in rows:
        counts_by_status[s.value] = n

    sent = counts_by_status.get("sent", 0) + counts_by_status.get("delivered", 0) + counts_by_status.get("read", 0) + counts_by_status.get("replied", 0)
    return CampaignMetrics(
        total=total if total is not None else sum(counts_by_status.values()),
        valid=valid if valid is not None else sum(counts_by_status.values()),
        invalid=invalid if invalid is not None else counts_by_status.get("invalid", 0),
        sent=sent,
        delivered=counts_by_status.get("delivered", 0) + counts_by_status.get("read", 0) + counts_by_status.get("replied", 0),
        read=counts_by_status.get("read", 0) + counts_by_status.get("replied", 0),
        replied=counts_by_status.get("replied", 0),
        failed=counts_by_status.get("failed", 0),
        pending=counts_by_status.get("pending", 0),
    )
