"""Simple PDF text extraction for KB ingest."""
from __future__ import annotations

import io

from pypdf import PdfReader


def extract_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    return "\n\n".join(chunks).strip()
