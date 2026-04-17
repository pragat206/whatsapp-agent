from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class KbCreate(BaseModel):
    name: str
    description: str | None = None


class KbOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None = None
    published: bool


class DocumentCreate(BaseModel):
    title: str
    category: str | None = None
    content: str
    source_kind: str = "text"


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str
    category: str | None = None
    source_kind: str
    published: bool


class FaqCreate(BaseModel):
    question: str
    answer: str
    category: str | None = None


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kb_id: uuid.UUID
    question: str
    answer: str
    category: str | None = None
    published: bool


class KbQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    category: str | None = None


class KbQueryResultItem(BaseModel):
    text: str
    document_id: uuid.UUID
    score: float
    category: str | None = None


class KbQueryResult(BaseModel):
    items: list[KbQueryResultItem]
