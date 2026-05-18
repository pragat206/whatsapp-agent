"""Best-effort storage of customer-shared media into ``user_uploads/``.

When an inbound WhatsApp message carries a ``media_url`` (electricity
bill PDF, Aadhaar photo, roof photo, voice note), this module fetches
the file from the AiSensy / WhatsApp CDN and writes it to a per-contact
folder inside ``settings.user_uploads_dir``.

Design notes:
- Synchronous fetch on the inbound path is acceptable because the AI
  reply is already enqueued onto RQ in a separate step; the webhook
  handler is not in the user's reply latency loop.
- Every failure here is swallowed and logged. Saving customer media is
  a convenience for the operator; failing it must NEVER prevent the
  message from being persisted or the AI reply from running.
- The phone number lands directly in the path (it's already E.164 and
  normalized by ``app.utils.phone``), but we still re-sanitize and
  reject any traversal characters defensively.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("media.storage")

# Phone numbers are E.164: "+" followed by digits. Anything else is
# rejected to keep path traversal impossible. Files keep an explicit
# extension whitelist so a hostile CDN cannot trick us into writing an
# executable on disk.
_PHONE_RE = re.compile(r"^\+?[0-9]{6,20}$")
_EXT_WHITELIST = {
    "jpg", "jpeg", "png", "webp", "gif",
    "pdf", "doc", "docx", "xls", "xlsx", "txt", "csv",
    "mp3", "ogg", "oga", "m4a", "wav", "amr",
    "mp4", "mov", "3gp", "webm",
}
_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "application/pdf": "pdf",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/amr": "amr",
    "video/mp4": "mp4",
    "video/3gpp": "3gp",
    "video/quicktime": "mov",
}


def _resolve_root() -> Path:
    settings = get_settings()
    root = Path(settings.user_uploads_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_phone_segment(phone_e164: str) -> str | None:
    p = (phone_e164 or "").strip()
    return p if _PHONE_RE.match(p) else None


def _pick_extension(media_url: str, media_type: str | None, content_type: str | None) -> str:
    # Prefer the URL extension when it's in the whitelist.
    try:
        path = urlparse(media_url).path or ""
        url_ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    except Exception:  # noqa: BLE001
        url_ext = ""
    if url_ext in _EXT_WHITELIST:
        return url_ext
    if content_type:
        ext = _MIME_TO_EXT.get(content_type.split(";", 1)[0].strip().lower())
        if ext:
            return ext
    if media_type:
        mt = media_type.lower().strip()
        if mt in _MIME_TO_EXT:
            return _MIME_TO_EXT[mt]
        if mt in _EXT_WHITELIST:
            return mt
        # Common WhatsApp `messageType` values: image, document, audio, video
        return {
            "image": "jpg",
            "document": "pdf",
            "audio": "ogg",
            "voice": "ogg",
            "video": "mp4",
        }.get(mt, "bin")
    return "bin"


def save_inbound_media(
    *,
    phone_e164: str,
    message_id: uuid.UUID | str,
    media_url: str | None,
    media_type: str | None,
) -> str | None:
    """Download ``media_url`` and store it under ``user_uploads/<phone>/``.

    Returns the relative path (string) on success, ``None`` on any
    failure (including when uploads are disabled or the URL is missing).
    """
    if not media_url:
        return None
    settings = get_settings()
    if not settings.user_uploads_enabled:
        return None

    phone_seg = _safe_phone_segment(phone_e164)
    if phone_seg is None:
        logger.warning(
            "user_upload_rejected_phone",
            phone_e164_preview=str(phone_e164)[:40],
        )
        return None

    root = _resolve_root()
    contact_dir = root / phone_seg
    try:
        contact_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("user_upload_mkdir_failed", error=str(exc)[:200])
        return None

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            with client.stream("GET", media_url) as resp:
                if resp.status_code >= 400:
                    logger.warning(
                        "user_upload_download_http_error",
                        status_code=resp.status_code,
                        media_url_preview=media_url[:200],
                    )
                    return None
                content_type = resp.headers.get("content-type")
                ext = _pick_extension(media_url, media_type, content_type)
                filename = f"{message_id}__{(media_type or 'file').lower()}.{ext}"
                # Strip any path separators that might have slipped in via
                # media_type.
                filename = filename.replace("/", "_").replace("\\", "_")
                dest = contact_dir / filename
                # Resolve to ensure dest stays inside contact_dir (defense in
                # depth — symlink shenanigans).
                if not str(dest.resolve()).startswith(str(contact_dir.resolve())):
                    logger.warning(
                        "user_upload_path_escape_blocked",
                        filename=filename,
                    )
                    return None

                max_bytes = settings.user_uploads_max_bytes
                bytes_written = 0
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                        bytes_written += len(chunk)
                        if bytes_written > max_bytes:
                            fh.close()
                            try:
                                os.unlink(dest)
                            except OSError:
                                pass
                            logger.warning(
                                "user_upload_too_large",
                                bytes_written=bytes_written,
                                max_bytes=max_bytes,
                                media_url_preview=media_url[:200],
                            )
                            return None
                        fh.write(chunk)

        rel = dest.relative_to(root)
        logger.info(
            "user_upload_saved",
            phone_e164=phone_seg,
            path=str(rel),
            bytes_written=bytes_written,
            content_type=content_type,
        )
        return str(rel)
    except Exception as exc:  # noqa: BLE001 — best-effort: never bubble up
        logger.warning(
            "user_upload_download_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
            media_url_preview=str(media_url)[:200],
        )
        return None
