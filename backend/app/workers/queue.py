"""RQ queue + job enqueue helpers."""
from __future__ import annotations

import uuid

from redis import Redis
from rq import Queue

from app.core.config import get_settings
from app.core.redis import get_redis


def _queue(conn: Redis | None = None) -> Queue:
    s = get_settings()
    return Queue(s.rq_queue_name, connection=conn or get_redis())


def enqueue_ai_reply(conversation_id: uuid.UUID, message_id: uuid.UUID) -> None:
    _queue().enqueue(
        "app.workers.jobs.run_ai_reply",
        str(conversation_id),
        str(message_id),
        job_timeout=60,
        result_ttl=60,
        failure_ttl=3600,
    )


def enqueue_campaign_send(campaign_id: uuid.UUID) -> None:
    _queue().enqueue(
        "app.workers.jobs.run_campaign_send",
        str(campaign_id),
        job_timeout=3600,
        result_ttl=300,
        failure_ttl=86400,
    )


def enqueue_kb_reindex(document_id: uuid.UUID) -> None:
    _queue().enqueue(
        "app.workers.jobs.run_kb_reindex",
        str(document_id),
        job_timeout=600,
        result_ttl=60,
        failure_ttl=3600,
    )
