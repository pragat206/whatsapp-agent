"""AiSensy messaging adapter.

This is the single boundary between our app and AiSensy. Business logic must
only talk to `AiSensyClient` and never construct provider payloads elsewhere.
"""
from app.integrations.aisensy.client import AiSensyClient  # noqa: F401
from app.integrations.aisensy.normalizer import normalize_inbound, normalize_status  # noqa: F401
from app.integrations.aisensy.schemas import (  # noqa: F401
    CampaignSendPayload,
    SessionSendPayload,
    NormalizedInbound,
    NormalizedStatus,
)
