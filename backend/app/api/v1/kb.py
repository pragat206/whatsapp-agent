"""Knowledge Base API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sqlalchemy import delete as sa_delete

from app.api.deps import current_user, db_dep, require_roles
from app.core.config import get_settings
from app.models.knowledge import FaqEntry, KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.models.user import Role, User
from app.schemas.common import IdResponse
from app.schemas.kb import (
    DocumentCreate,
    DocumentOut,
    FaqCreate,
    FaqOut,
    KbCreate,
    KbOut,
    KbQueryRequest,
    KbQueryResult,
    KbQueryResultItem,
)
from app.services.kb.retriever import retrieve
from app.utils.pdf import extract_text
from app.workers.queue import enqueue_kb_reindex

router = APIRouter(prefix="/kb", tags=["kb"])


@router.post("", response_model=KbOut, status_code=201)
def create_kb(
    body: KbCreate,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> KbOut:
    kb = KnowledgeBase(name=body.name, description=body.description)
    db.add(kb)
    db.commit()
    return KbOut.model_validate(kb)


@router.get("", response_model=list[KbOut])
def list_kbs(
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> list[KbOut]:
    rows = db.execute(select(KnowledgeBase).order_by(KnowledgeBase.name)).scalars().all()
    return [KbOut.model_validate(k) for k in rows]


def _get_kb(db: Session, kb_id: uuid.UUID) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "kb not found")
    return kb


@router.post("/{kb_id}/documents", response_model=DocumentOut, status_code=201)
def add_document(
    kb_id: uuid.UUID,
    body: DocumentCreate,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> DocumentOut:
    _get_kb(db, kb_id)
    doc = KnowledgeDocument(
        kb_id=kb_id,
        title=body.title,
        category=body.category,
        source_kind=body.source_kind,
        content=body.content,
    )
    db.add(doc)
    db.commit()
    enqueue_kb_reindex(doc.id)
    return DocumentOut.model_validate(doc)


@router.post("/{kb_id}/documents/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    kb_id: uuid.UUID,
    title: str,
    category: str | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> DocumentOut:
    _get_kb(db, kb_id)
    content = await file.read()
    fname = (file.filename or "").lower()
    if fname.endswith(".pdf"):
        text = extract_text(content)
        kind = "pdf"
    else:
        text = content.decode("utf-8", errors="ignore")
        kind = "markdown" if fname.endswith(".md") else "text"
    doc = KnowledgeDocument(
        kb_id=kb_id,
        title=title,
        category=category,
        source_kind=kind,
        content=text,
    )
    db.add(doc)
    db.commit()
    enqueue_kb_reindex(doc.id)
    return DocumentOut.model_validate(doc)


@router.get("/{kb_id}/documents", response_model=list[DocumentOut])
def list_documents(
    kb_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> list[DocumentOut]:
    rows = (
        db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.kb_id == kb_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [DocumentOut.model_validate(d) for d in rows]


@router.post("/documents/{document_id}/publish", response_model=DocumentOut)
def publish_document(
    document_id: uuid.UUID,
    published: bool = True,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> DocumentOut:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    doc.published = published
    db.commit()
    return DocumentOut.model_validate(doc)


@router.post("/{kb_id}/faqs", response_model=FaqOut, status_code=201)
def add_faq(
    kb_id: uuid.UUID,
    body: FaqCreate,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> FaqOut:
    _get_kb(db, kb_id)
    faq = FaqEntry(
        kb_id=kb_id,
        question=body.question,
        answer=body.answer,
        category=body.category,
    )
    db.add(faq)
    db.commit()
    return FaqOut.model_validate(faq)


@router.get("/{kb_id}/faqs", response_model=list[FaqOut])
def list_faqs(
    kb_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> list[FaqOut]:
    rows = (
        db.execute(
            select(FaqEntry)
            .where(FaqEntry.kb_id == kb_id)
            .order_by(FaqEntry.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [FaqOut.model_validate(f) for f in rows]


@router.post("/test-query", response_model=KbQueryResult)
def test_query(
    body: KbQueryRequest,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> KbQueryResult:
    chunks = retrieve(
        db,
        query=body.query,
        top_k=body.top_k,
        category=body.category,
    )
    hint: str | None = None
    if not chunks:
        settings = get_settings()
        openai_configured = bool((settings.openai_api_key or "").strip())
        n_published_docs = (
            db.scalar(
                select(func.count())
                .select_from(KnowledgeDocument)
                .where(KnowledgeDocument.published.is_(True))
            )
            or 0
        )
        n_chunks = (
            db.scalar(
                select(func.count())
                .select_from(KnowledgeChunk)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(KnowledgeDocument.published.is_(True))
            )
            or 0
        )
        if n_published_docs == 0:
            hint = (
                "No published documents found. Add content, ensure “published” is on, then click Reindex."
            )
        elif n_chunks == 0:
            # Zero chunks means reindex never completed or worker never ran — not necessarily missing OPENAI_API_KEY.
            if not openai_configured:
                hint = (
                    "No search chunks yet. Set OPENAI_API_KEY on the backend (required to build embeddings), "
                    "then click Reindex on your knowledge base."
                )
            else:
                hint = (
                    "No search chunks yet for your published documents. Click Reindex on that knowledge base. "
                    "Indexing runs in a background RQ worker (same Redis + worker process as campaign jobs). "
                    "If you already clicked Reindex, ensure the worker service is running and check worker logs for errors."
                )
        else:
            hint = "No chunk matched this query — try words that appear in your document text."
            if not openai_configured:
                hint += " For semantic search, set OPENAI_API_KEY and reindex."

    return KbQueryResult(
        items=[
            KbQueryResultItem(
                text=c.text,
                document_id=c.document_id,
                score=c.score,
                category=c.category,
            )
            for c in chunks
        ],
        hint=hint,
    )


@router.post("/{kb_id}/reindex", response_model=IdResponse)
def reindex_all(
    kb_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> IdResponse:
    for doc_id, in db.execute(
        select(KnowledgeDocument.id).where(KnowledgeDocument.kb_id == kb_id)
    ).all():
        enqueue_kb_reindex(doc_id)
    return IdResponse(id=kb_id)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> dict:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    db.execute(sa_delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.delete("/faqs/{faq_id}")
def delete_faq(
    faq_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> dict:
    faq = db.get(FaqEntry, faq_id)
    if faq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "faq not found")
    db.delete(faq)
    db.commit()
    return {"ok": True}


@router.delete("/{kb_id}")
def delete_kb(
    kb_id: uuid.UUID,
    db: Session = Depends(db_dep),
    _: User = Depends(require_roles(Role.admin)),
) -> dict:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "kb not found")
    db.execute(sa_delete(KnowledgeChunk).where(KnowledgeChunk.kb_id == kb_id))
    db.execute(sa_delete(KnowledgeDocument).where(KnowledgeDocument.kb_id == kb_id))
    db.execute(sa_delete(FaqEntry).where(FaqEntry.kb_id == kb_id))
    db.delete(kb)
    db.commit()
    return {"ok": True}
