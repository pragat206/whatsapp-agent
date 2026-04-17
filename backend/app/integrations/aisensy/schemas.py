"""Data contracts for the AiSensy adapter.

These are the only types business code should pass in/out of the adapter.
Keeping them here keeps provider-specific shapes out of the rest of the app.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class CampaignMedia(BaseModel):
    url: str
    filename: str | None = None


class CampaignSendPayload(BaseModel):
    """Payload for a templated (business-initiated) campaign message."""

    campaign_name: str
    destination: str               # E.164 phone
    user_name: str | None = None   # contact name
    source: str | None = None
    media: CampaignMedia | None = None
    template_params: list[str] = []
    tags: list[str] = []
    attributes: dict[str, Any] = {}


class SessionSendPayload(BaseModel):
    """Payload for a free-form (session-window) reply."""

    destination: str
    body: str
    media_url: str | None = None
    media_type: str | None = None


class NormalizedInbound(BaseModel):
    """Internal shape produced by the AiSensy webhook normalizer."""

    model_config = ConfigDict(extra="ignore")

    provider_message_id: str
    from_phone_e164: str
    contact_name: str | None = None
    text: str = ""
    media_url: str | None = None
    media_type: str | None = None
    received_at: dt.datetime
    # True when the provider signals a human has responded from the AiSensy
    # inbox or WhatsApp mobile — we treat this as an external takeover event.
    human_intervention: bool = False
    # Free-form provider metadata (campaign references, reply-to, etc.)
    metadata: dict[str, Any] = {}


class NormalizedStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider_message_id: str
    status: str                 # sent | delivered | read | failed
    error: str | None = None
    at: dt.datetime
    raw: dict[str, Any] = {}
