from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class AgentProfileCreate(BaseModel):
    name: str
    purpose: str = ""
    tone: str = "friendly, professional"
    response_style: str = "concise"
    languages_supported: list[str] = ["en", "hi"]
    greeting_style: str = ""
    escalation_keywords: list[str] = []
    forbidden_claims: list[str] = []
    allowed_domains: list[str] = []
    fallback_message: str = ""
    human_handoff_message: str = ""
    business_hours_behavior: str = "respond_always"
    instructions: str = ""


class AgentProfileUpdate(BaseModel):
    purpose: str | None = None
    tone: str | None = None
    response_style: str | None = None
    languages_supported: list[str] | None = None
    greeting_style: str | None = None
    escalation_keywords: list[str] | None = None
    forbidden_claims: list[str] | None = None
    allowed_domains: list[str] | None = None
    fallback_message: str | None = None
    human_handoff_message: str | None = None
    business_hours_behavior: str | None = None
    instructions: str | None = None
    is_default: bool | None = None


class AgentProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    purpose: str
    tone: str
    response_style: str
    languages_supported: list[str]
    greeting_style: str
    escalation_keywords: list[str]
    forbidden_claims: list[str]
    allowed_domains: list[str]
    fallback_message: str
    human_handoff_message: str
    business_hours_behavior: str
    instructions: str
    is_default: bool


class AttachKbRequest(BaseModel):
    kb_id: uuid.UUID
