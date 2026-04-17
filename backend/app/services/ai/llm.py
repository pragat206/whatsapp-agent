"""LLM client abstraction (Anthropic default, OpenAI optional)."""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class LLMClient(Protocol):
    def chat(self, *, system: str, messages: list[dict], max_tokens: int = 600) -> str: ...


class AnthropicClient:
    def __init__(self) -> None:
        s = get_settings()
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY required")
        from anthropic import Anthropic
        self._client = Anthropic(api_key=s.anthropic_api_key)
        self._model = s.ai_model

    def chat(self, *, system: str, messages: list[dict], max_tokens: int = 600) -> str:
        resp = self._client.messages.create(
            model=self._model,
            system=system,
            max_tokens=max_tokens,
            messages=messages,
        )
        out: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                out.append(block.text)
        return "".join(out).strip()


class OpenAIClient:
    def __init__(self) -> None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY required")
        from openai import OpenAI
        self._client = OpenAI(api_key=s.openai_api_key)
        self._model = s.ai_model

    def chat(self, *, system: str, messages: list[dict], max_tokens: int = 600) -> str:
        oa_messages = [{"role": "system", "content": system}] + messages
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=oa_messages,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


@lru_cache
def get_llm() -> LLMClient:
    s = get_settings()
    if s.ai_provider == "anthropic":
        return AnthropicClient()
    return OpenAIClient()
