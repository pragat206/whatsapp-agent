"""Vector + FAQ retrieval for the AI runner."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import AgentProfileKbLink
from app.models.knowledge import FaqEntry, KnowledgeChunk, KnowledgeDocument
from app.services.kb.embeddings import get_embeddings_client


@dataclass
class RetrievedChunk:
    document_id: uuid.UUID
    text: str
    score: float
    category: str | None
    source_title: str | None


def _kb_ids_for_agent(db: Session, agent_profile_id: uuid.UUID | None) -> list[uuid.UUID]:
    if agent_profile_id is None:
        return []
    rows = db.execute(
        select(AgentProfileKbLink.kb_id).where(
            AgentProfileKbLink.agent_profile_id == agent_profile_id
        )
    ).all()
    return [r[0] for r in rows]


def retrieve(
    db: Session,
    *,
    query: str,
    agent_profile_id: uuid.UUID | None = None,
    top_k: int = 5,
    category: str | None = None,
) -> list[RetrievedChunk]:
    query = (query or "").strip()
    if not query:
        return []

    try:
        emb = get_embeddings_client().embed([query])[0]
    except Exception:  # noqa: BLE001
        return _fallback_fulltext(db, query=query, top_k=top_k, category=category)

    kb_ids = _kb_ids_for_agent(db, agent_profile_id)

    stmt = (
        select(
            KnowledgeChunk,
            KnowledgeDocument.title,
            KnowledgeChunk.embedding.cosine_distance(emb).label("dist"),
        )
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.published.is_(True))
        .order_by("dist")
        .limit(top_k)
    )
    if kb_ids:
        stmt = stmt.where(KnowledgeChunk.kb_id.in_(kb_ids))
    if category:
        stmt = stmt.where(KnowledgeChunk.category == category)

    rows = db.execute(stmt).all()
    results: list[RetrievedChunk] = []
    for chunk, title, dist in rows:
        score = max(0.0, 1.0 - float(dist))
        results.append(
            RetrievedChunk(
                document_id=chunk.document_id,
                text=chunk.text,
                score=score,
                category=chunk.category,
                source_title=title,
            )
        )
    return results


def _fallback_fulltext(
    db: Session, *, query: str, top_k: int, category: str | None
) -> list[RetrievedChunk]:
    # Trigram similarity fallback on chunk text if embeddings are unavailable.
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument.title)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.published.is_(True))
        .where(KnowledgeChunk.text.ilike(f"%{query[:40]}%"))
        .limit(top_k)
    )
    if category:
        stmt = stmt.where(KnowledgeChunk.category == category)
    rows = db.execute(stmt).all()
    return [
        RetrievedChunk(
            document_id=chunk.document_id,
            text=chunk.text,
            score=0.3,
            category=chunk.category,
            source_title=title,
        )
        for chunk, title in rows
    ]


def find_faq(db: Session, *, query: str) -> FaqEntry | None:
    q = query.strip().lower()
    if len(q) < 3:
        return None
    return db.scalar(
        select(FaqEntry)
        .where(FaqEntry.published.is_(True))
        .where(FaqEntry.question.ilike(f"%{q[:60]}%"))
        .limit(1)
    )
