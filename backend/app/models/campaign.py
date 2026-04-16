from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPk


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    mapped = "mapped"
    scheduled = "scheduled"
    sending = "sending"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class CampaignRecipientStatus(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    replied = "replied"
    failed = "failed"
    skipped = "skipped"
    invalid = "invalid"


class Campaign(UUIDPk, Timestamped, Base):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    objective: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        default=CampaignStatus.draft,
        nullable=False,
        index=True,
    )
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=True
    )
    template_name: Mapped[str] = mapped_column(String(120), nullable=False)
    template_params_schema: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    scheduled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    recipients = relationship("CampaignRecipient", back_populates="campaign")


class CampaignUpload(UUIDPk, Timestamped, Base):
    __tablename__ = "campaign_uploads"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    # We do NOT use object storage; file contents are parsed and discarded.
    row_count: Mapped[int] = mapped_column(default=0, nullable=False)
    valid_count: Mapped[int] = mapped_column(default=0, nullable=False)
    invalid_count: Mapped[int] = mapped_column(default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(default=0, nullable=False)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Parsed rows cached for preview + confirm step.
    preview: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class CampaignRecipient(UUIDPk, Timestamped, Base):
    __tablename__ = "campaign_recipients"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    phone_e164: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    template_params: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[CampaignRecipientStatus] = mapped_column(
        Enum(CampaignRecipientStatus, name="campaign_recipient_status"),
        default=CampaignRecipientStatus.pending,
        nullable=False,
        index=True,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(120), index=True)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)

    campaign = relationship("Campaign", back_populates="recipients")


class CampaignRecipientEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "campaign_recipient_events"

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_recipients.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    raw: Mapped[dict | None] = mapped_column(JSON)
