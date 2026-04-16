from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.campaign import CampaignRecipientStatus, CampaignStatus

# Fixed set of internal fields a CSV column can map to.
INTERNAL_FIELDS = [
    "name",
    "phone",
    "city",
    "state",
    "property_type",
    "monthly_bill",
    "roof_type",
    "notes",
    "source",
]


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    objective: str | None = None
    template_name: str
    template_params_schema: list[str] = []
    agent_profile_id: uuid.UUID | None = None
    tags: list[str] = []
    source: str | None = None


class CampaignMappingConfirm(BaseModel):
    """Column mapping: provider-csv-column -> internal field name."""

    mapping: dict[str, str]
    template_param_columns: list[str] = []  # order matters, fills templateParams
    dedupe: bool = True


class CampaignSchedule(BaseModel):
    scheduled_at: dt.datetime | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    objective: str | None = None
    status: CampaignStatus
    template_name: str
    template_params_schema: list[str] = []
    tags: list[str] = []
    source: str | None = None
    agent_profile_id: uuid.UUID | None = None
    scheduled_at: dt.datetime | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    created_at: dt.datetime


class CampaignMetrics(BaseModel):
    total: int
    valid: int
    invalid: int
    sent: int
    delivered: int
    read: int
    replied: int
    failed: int
    pending: int


class CampaignRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone_e164: str
    status: CampaignRecipientStatus
    template_params: list = []
    attributes: dict = {}
    sent_at: dt.datetime | None = None
    delivered_at: dt.datetime | None = None
    read_at: dt.datetime | None = None
    replied_at: dt.datetime | None = None
    error: str | None = None


class UploadPreview(BaseModel):
    upload_id: uuid.UUID
    columns: list[str]
    preview_rows: list[dict]
    total_rows: int
    suggested_mapping: dict[str, str]
