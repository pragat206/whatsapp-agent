"""Simple paragraph-based chunker with overlap."""
from __future__ import annotations

import re

_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}" if buf else p
            continue
        if buf:
            chunks.append(buf)
        if len(p) <= max_chars:
            buf = p
        else:
            # Hard-split long paragraph on sentence boundaries.
            start = 0
            while start < len(p):
                chunks.append(p[start : start + max_chars])
                start += max_chars - overlap
            buf = ""
    if buf:
        chunks.append(buf)
    # Apply overlap between chunks.
    if overlap and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for prev, curr in zip(chunks, chunks[1:]):
            tail = prev[-overlap:]
            overlapped.append(f"{tail}\n{curr}")
        chunks = overlapped
    return chunks
