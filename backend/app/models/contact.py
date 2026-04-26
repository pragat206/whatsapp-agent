from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, Integer, String, Text
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

    # ----- Lead tracking -----
    # Drives both (a) the AI runner's "known about this customer" memory
    # block injected into the system prompt and (b) the Leads dashboard tab.
    # All fields default to NULL/empty so existing rows are unaffected.
    lead_status: Mapped[str | None] = mapped_column(String(40), index=True)
    # Examples: new | contacted | interested | qualified | hot | converted | lost | nurturing
    lead_next_action: Mapped[str | None] = mapped_column(String(200))
    # Free-form short string describing what should happen next, e.g.
    # "send pricing quote", "human follow-up", "schedule site visit".
    lead_next_action_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    lead_summary: Mapped[str | None] = mapped_column(Text)
    lead_score: Mapped[int | None] = mapped_column(Integer)  # 0..100
    lead_extracted_attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    lead_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
