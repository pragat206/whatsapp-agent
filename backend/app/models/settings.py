from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class Setting(UUIDPk, Timestamped, Base):
    """Key/value settings table for runtime-configurable business rules."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(String(500))
