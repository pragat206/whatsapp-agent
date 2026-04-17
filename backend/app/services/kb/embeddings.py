"""Embeddings client. Keeps the app provider-agnostic.

We use OpenAI for embeddings by default (it's cheap and reliable), even when
the main LLM is Anthropic. This is configurable via env.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("kb.embeddings")


class EmbeddingsClient:
    def __init__(self) -> None:
        s = get_settings()
        self.provider = s.ai_embedding_provider
        self.model = s.ai_embedding_model
        self.dim = s.ai_embedding_dimensions
        if self.provider == "openai":
            if not s.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY required for embeddings")
            from openai import OpenAI
            self._client = OpenAI(api_key=s.openai_api_key)
        else:
            raise RuntimeError(f"Unsupported embedding provider: {self.provider}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in resp.data]


@lru_cache
def get_embeddings_client() -> EmbeddingsClient:
    return EmbeddingsClient()
