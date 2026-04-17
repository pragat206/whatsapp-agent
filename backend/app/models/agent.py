from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class AgentProfile(UUIDPk, Timestamped, Base):
    __tablename__ = "agent_profiles"

    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tone: Mapped[str] = mapped_column(String(120), nullable=False, default="friendly, professional")
    response_style: Mapped[str] = mapped_column(String(120), nullable=False, default="concise")
    languages_supported: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    greeting_style: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    escalation_keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    forbidden_claims: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    fallback_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Let me connect you with our team for a quick follow-up.",
    )
    human_handoff_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="A Terra Rex specialist will reach out to you shortly.",
    )
    business_hours_behavior: Mapped[str] = mapped_column(
        String(40), nullable=False, default="respond_always"
    )  # respond_always | defer_outside_hours
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AgentProfileKbLink(UUIDPk, Timestamped, Base):
    __tablename__ = "agent_profile_kb_links"
    __table_args__ = (UniqueConstraint("agent_profile_id", "kb_id", name="uq_agent_kb"),)

    agent_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False, index=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
