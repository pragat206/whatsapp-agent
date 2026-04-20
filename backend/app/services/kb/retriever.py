"""Vector + FAQ retrieval for the AI runner."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
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
        .where(KnowledgeChunk.embedding.isnot(None))
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
    # No vector hits: chunks may be missing embeddings (reindex needed) or semantic miss — try substring fallback.
    if not results:
        return _fallback_fulltext(db, query=query, top_k=top_k, category=category)
    return results


def _fallback_fulltext(
    db: Session, *, query: str, top_k: int, category: str | None
) -> list[RetrievedChunk]:
    # Substring fallback: used when embeddings are unavailable OR vector search returned nothing.
    # Match any word (3+ chars) from the query so short tests still find content.
    q = (query or "").strip()
    terms = [w for w in q.replace(",", " ").split() if len(w) >= 3][:8]
    if not terms:
        needle = q[:40] if q else ""
        if not needle:
            return []
        pattern = f"%{needle}%"
    else:
        ors = [KnowledgeChunk.text.ilike(f"%{t}%") for t in terms]
        stmt_base = (
            select(KnowledgeChunk, KnowledgeDocument.title)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(KnowledgeDocument.published.is_(True))
            .where(or_(*ors))
        )
        if category:
            stmt_base = stmt_base.where(KnowledgeChunk.category == category)
        stmt_base = stmt_base.limit(top_k)
        rows = db.execute(stmt_base).all()
        return [
            RetrievedChunk(
                document_id=chunk.document_id,
                text=chunk.text,
                score=0.35,
                category=chunk.category,
                source_title=title,
            )
            for chunk, title in rows
        ]

    stmt = (
        select(KnowledgeChunk, KnowledgeDocument.title)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.published.is_(True))
        .where(KnowledgeChunk.text.ilike(pattern))
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
