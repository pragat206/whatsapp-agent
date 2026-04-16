"""RQ job entrypoints.

These are thin wrappers around service-level functions. RQ expects importable
callables, so all imports inside jobs are tolerant to worker startup order.
"""
from __future__ import annotations

import uuid

from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("worker")


def run_ai_reply(conversation_id: str, message_id: str) -> None:
    from app.services.ai.runner import handle_inbound
    try:
        handle_inbound(uuid.UUID(conversation_id), uuid.UUID(message_id))
    except Exception:  # noqa: BLE001
        logger.exception("ai_reply_job_failed", conv=conversation_id, msg=message_id)
        raise


def run_campaign_send(campaign_id: str) -> None:
    from app.services.campaign.sender import send_campaign
    try:
        send_campaign(uuid.UUID(campaign_id))
    except Exception:  # noqa: BLE001
        logger.exception("campaign_send_job_failed", campaign=campaign_id)
        raise


def run_kb_reindex(document_id: str) -> None:
    from app.db.session import SessionLocal
    from app.services.kb.indexer import reindex_document
    db = SessionLocal()
    try:
        reindex_document(db, uuid.UUID(document_id))
    finally:
        db.close()
