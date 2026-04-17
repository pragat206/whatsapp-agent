"""Create/update KB chunks + embeddings for a document."""
from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.kb.chunker import chunk_text
from app.services.kb.embeddings import get_embeddings_client


def reindex_document(db: Session, document_id: uuid.UUID) -> int:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        return 0

    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))

    texts = chunk_text(doc.content)
    if not texts:
        db.commit()
        return 0

    embeddings = get_embeddings_client().embed(texts)

    for idx, (text, emb) in enumerate(zip(texts, embeddings)):
        db.add(
            KnowledgeChunk(
                document_id=doc.id,
                kb_id=doc.kb_id,
                ordinal=idx,
                text=text,
                embedding=emb,
                category=doc.category,
            )
        )
    db.commit()
    return len(texts)
