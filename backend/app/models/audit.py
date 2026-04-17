from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class AuditLog(UUIDPk, Timestamped, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict | None] = mapped_column(JSON)


class RawWebhookEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "raw_webhook_events"

    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500))
