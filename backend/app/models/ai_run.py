from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPk


class AiRun(UUIDPk, Timestamped, Base):
    __tablename__ = "ai_runs"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=True
    )
    intent: Mapped[str | None] = mapped_column(String(60))
    used_kb_chunks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)  # sent | skipped_state | skipped_window | escalated | failed
    reason: Mapped[str | None] = mapped_column(String(300))
    latency_ms: Mapped[int | None] = mapped_column()
