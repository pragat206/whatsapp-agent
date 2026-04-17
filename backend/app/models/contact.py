from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class Contact(UUIDPk, Timestamped, Base):
    __tablename__ = "contacts"

    # Canonical E.164 phone number — unique identity for WhatsApp contacts.
    phone_e164: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    property_type: Mapped[str | None] = mapped_column(String(60))
    monthly_bill: Mapped[str | None] = mapped_column(String(60))
    roof_type: Mapped[str | None] = mapped_column(String(60))
    source: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(1000))
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unsubscribed: Mapped[bool] = mapped_column(default=False, nullable=False)
