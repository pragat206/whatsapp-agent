"""Safety tests for app.services.media.storage.save_inbound_media.

The function never raises and never writes outside the configured root —
those are the only invariants downstream code (webhook_processor) depends
on. We verify each one explicitly so a future refactor cannot silently
break them.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest

from app.services.media import storage


class _FakeStream:
    def __init__(self, body: bytes, status_code: int = 200, content_type: str = "image/jpeg"):
        self._body = body
        self.status_code = status_code
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_bytes(self, chunk_size: int = 65536):
        yield self._body


class _FakeClient:
    def __init__(self, stream: _FakeStream):
        self._stream = stream

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream(self, method: str, url: str):  # noqa: ARG002
        return self._stream


def _patch(monkeypatch, *, stream: _FakeStream, root: Path):
    monkeypatch.setattr(storage, "_resolve_root", lambda: root)
    monkeypatch.setattr(httpx, "Client", lambda **_kw: _FakeClient(stream))


def test_save_inbound_media_writes_under_phone_folder(monkeypatch, tmp_path):
    _patch(monkeypatch, stream=_FakeStream(b"\xff\xd8\xff" + b"x" * 50), root=tmp_path)
    msg_id = uuid.uuid4()
    rel = storage.save_inbound_media(
        phone_e164="+919900000000",
        message_id=msg_id,
        media_url="https://cdn.example/media/x.jpg",
        media_type="image",
    )
    assert rel is not None
    full = tmp_path / rel
    assert full.exists()
    assert "+919900000000" in str(full)
    assert full.read_bytes().startswith(b"\xff\xd8\xff")


def test_save_inbound_media_rejects_bad_phone(monkeypatch, tmp_path):
    _patch(monkeypatch, stream=_FakeStream(b"data"), root=tmp_path)
    rel = storage.save_inbound_media(
        phone_e164="../evil",
        message_id=uuid.uuid4(),
        media_url="https://cdn.example/x.jpg",
        media_type="image",
    )
    assert rel is None
    # Nothing should have been written.
    assert list(tmp_path.iterdir()) == []


def test_save_inbound_media_no_url_returns_none(monkeypatch, tmp_path):
    _patch(monkeypatch, stream=_FakeStream(b""), root=tmp_path)
    assert storage.save_inbound_media(
        phone_e164="+919900000000",
        message_id=uuid.uuid4(),
        media_url=None,
        media_type="image",
    ) is None


def test_save_inbound_media_swallows_network_errors(monkeypatch, tmp_path):
    class _Boom:
        def __enter__(self):
            raise httpx.ConnectError("DNS fail")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(storage, "_resolve_root", lambda: tmp_path)
    monkeypatch.setattr(httpx, "Client", lambda **_kw: _Boom())
    # Must not raise.
    rel = storage.save_inbound_media(
        phone_e164="+919900000000",
        message_id=uuid.uuid4(),
        media_url="https://cdn.example/x.jpg",
        media_type="image",
    )
    assert rel is None


def test_save_inbound_media_enforces_size_limit(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "user_uploads_max_bytes", 100)
    _patch(monkeypatch, stream=_FakeStream(b"x" * 5000), root=tmp_path)
    rel = storage.save_inbound_media(
        phone_e164="+919900000000",
        message_id=uuid.uuid4(),
        media_url="https://cdn.example/big.jpg",
        media_type="image",
    )
    assert rel is None  # Oversized download is rejected.


def test_save_inbound_media_picks_extension_from_url(monkeypatch, tmp_path):
    _patch(
        monkeypatch,
        stream=_FakeStream(b"%PDF-1.4\n" + b"a" * 50, content_type="application/pdf"),
        root=tmp_path,
    )
    rel = storage.save_inbound_media(
        phone_e164="+919900000000",
        message_id=uuid.uuid4(),
        media_url="https://cdn.example/bill.pdf",
        media_type="document",
    )
    assert rel is not None
    assert rel.endswith(".pdf")


def test_save_inbound_media_disabled_returns_none(monkeypatch, tmp_path):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "user_uploads_enabled", False)
    _patch(monkeypatch, stream=_FakeStream(b"data"), root=tmp_path)
    rel = storage.save_inbound_media(
        phone_e164="+919900000000",
        message_id=uuid.uuid4(),
        media_url="https://cdn.example/x.jpg",
        media_type="image",
    )
    assert rel is None
