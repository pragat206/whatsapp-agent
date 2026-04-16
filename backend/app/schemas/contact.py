from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone_e164: str
    name: str | None = None
    city: str | None = None
    state: str | None = None
    property_type: str | None = None
    monthly_bill: str | None = None
    roof_type: str | None = None
    source: str | None = None
    notes: str | None = None
    tags: list[str] = []
    attributes: dict = {}
    unsubscribed: bool = False
    created_at: dt.datetime
