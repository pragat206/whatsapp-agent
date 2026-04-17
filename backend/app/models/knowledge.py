from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base, Timestamped, UUIDPk

_EMB_DIM = get_settings().ai_embedding_dimensions


class KnowledgeBase(UUIDPk, Timestamped, Base):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    documents = relationship("KnowledgeDocument", back_populates="kb")
    faqs = relationship("FaqEntry", back_populates="kb")


class KnowledgeDocument(UUIDPk, Timestamped, Base):
    __tablename__ = "knowledge_documents"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)  # text | markdown | pdf | faq
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    kb = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("KnowledgeChunk", back_populates="document")


class KnowledgeChunk(UUIDPk, Timestamped, Base):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id"), nullable=False, index=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(_EMB_DIM), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True)

    document = relationship("KnowledgeDocument", back_populates="chunks")


class FaqEntry(UUIDPk, Timestamped, Base):
    __tablename__ = "faq_entries"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    kb = relationship("KnowledgeBase", back_populates="faqs")
