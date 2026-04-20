"""Integration diagnostics (AiSensy, etc.) — no secrets exposed."""
from __future__ import annotations

import datetime as dt
import time

from fastapi import APIRouter, Depends, Query, Request
from rq import Queue
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import current_user, db_dep
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.ai_run import AiRun
from app.models.audit import RawWebhookEvent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.user import User
from app.services.ai.llm import get_llm

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _public_base_url(request: Request) -> str | None:
    """Best-effort URL for webhook hints (Railway sets X-Forwarded-*)."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        return None
    proto = (request.headers.get("x-forwarded-proto") or "https").split(",")[0].strip()
    return f"{proto}://{host}"


@router.get("/aisensy")
def aisensy_diagnostics(
    request: Request,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> dict:
    """Explains why the dashboard may show no AiSensy data: this app mirrors webhooks + API sends into Postgres."""
    settings = get_settings()
    api_key_set = bool((settings.aisensy_api_key or "").strip())
    webhook_sig_on = bool((settings.aisensy_webhook_secret or "").strip())

    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)
    inbound_total = db.scalar(
        select(func.count()).select_from(RawWebhookEvent).where(
            RawWebhookEvent.provider == "aisensy",
            RawWebhookEvent.kind == "inbound",
        )
    ) or 0
    inbound_24h = db.scalar(
        select(func.count()).select_from(RawWebhookEvent).where(
            RawWebhookEvent.provider == "aisensy",
            RawWebhookEvent.kind == "inbound",
            RawWebhookEvent.created_at >= since,
        )
    ) or 0
    inbound_normalize_errors = db.scalar(
        select(func.count()).select_from(RawWebhookEvent).where(
            RawWebhookEvent.provider == "aisensy",
            RawWebhookEvent.kind == "inbound",
            RawWebhookEvent.error.isnot(None),
        )
    ) or 0

    contacts_n = db.scalar(select(func.count()).select_from(Contact)) or 0
    convos_n = db.scalar(select(func.count()).select_from(Conversation)) or 0

    base = _public_base_url(request)
    hints: list[str] = []
    if not api_key_set:
        hints.append("AISENSY_API_KEY is missing or empty — outbound sends to AiSensy will fail. Set it in Railway to match your AiSensy project.")
    if webhook_sig_on:
        hints.append(
            "AISENSY_WEBHOOK_SECRET is set — AiSensy must send a matching HMAC or webhooks get 401. If AiSensy has no secret, remove this variable."
        )
    if inbound_total == 0:
        hints.append(
            "No inbound webhook events stored yet. This app does not import AiSensy’s UI; it only records traffic AiSensy POSTs to your webhook URL."
        )
        if base:
            hints.append(
                f"In AiSensy, set the inbound webhook URL to: {base}/api/v1/webhooks/aisensy/inbound "
                f"(and status if offered: {base}/api/v1/webhooks/aisensy/status)."
            )
    elif inbound_24h == 0:
        hints.append(
            "No inbound webhooks in the last 24 hours — either nobody messaged you, or AiSensy is not hitting this deployment."
        )
    if inbound_normalize_errors:
        hints.append(
            f"{inbound_normalize_errors} inbound webhook(s) stored but normalization failed — check backend logs for normalize_failed; payload shape may need an update in integrations/aisensy/normalizer.py."
        )
    if contacts_n == 0 and convos_n == 0 and inbound_total == 0:
        hints.append(
            "Campaign sends also require an RQ worker (Redis queue). If campaigns stay on “sending”, add a worker process — see backend/railway.worker.json."
        )

    return {
        "summary": (
            "This dashboard reads your Postgres database. AiSensy data appears after (1) webhooks deliver inbound messages "
            "or (2) you send campaigns / session messages successfully via this API."
        ),
        "config": {
            "aisensy_api_key_configured": api_key_set,
            "aisensy_base_url": settings.aisensy_base_url,
            "aisensy_campaign_endpoint": settings.aisensy_campaign_endpoint,
            "aisensy_session_endpoint": settings.aisensy_session_endpoint,
            "webhook_signature_enforced": webhook_sig_on,
        },
        "database": {
            "contacts": contacts_n,
            "conversations": convos_n,
            "aisensy_inbound_webhook_events_total": inbound_total,
            "aisensy_inbound_webhook_events_last_24h": inbound_24h,
            "aisensy_inbound_webhook_normalize_errors": inbound_normalize_errors,
        },
        "suggested_webhook_urls": (
            {
                "inbound": f"{base}/api/v1/webhooks/aisensy/inbound",
                "status": f"{base}/api/v1/webhooks/aisensy/status",
            }
            if base
            else None
        ),
        "hints": hints,
    }


@router.get("/system")
def system_diagnostics(
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
    probe_llm: bool = Query(
        False,
        description="If true, sends one minimal chat to your configured LLM (may incur a small API cost).",
    ),
) -> dict:
    """Infra + LLM readiness: DB, Redis, RQ queue depth, AI config, optional live LLM ping."""
    settings = get_settings()
    out: dict = {}

    # --- Database ---
    t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        db_err: str | None = None
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_err = str(exc)[:300]
    out["database"] = {
        "ok": db_ok,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "error": db_err,
    }

    # --- Redis ---
    t1 = time.perf_counter()
    try:
        r = get_redis()
        r.ping()
        redis_ok = True
        redis_err: str | None = None
    except Exception as exc:  # noqa: BLE001
        redis_ok = False
        redis_err = str(exc)[:300]
    out["redis"] = {
        "ok": redis_ok,
        "latency_ms": round((time.perf_counter() - t1) * 1000, 2),
        "error": redis_err,
    }

    # --- RQ job queue (same queue as workers) ---
    queued = None
    queue_err: str | None = None
    try:
        q = Queue(settings.rq_queue_name, connection=get_redis())
        queued = len(q)
    except Exception as exc:  # noqa: BLE001
        queue_err = str(exc)[:300]
    out["worker_queue"] = {
        "queue_name": settings.rq_queue_name,
        "queued_jobs": queued,
        "error": queue_err,
        "hint": (
            "If queued_jobs grows and campaigns/AI never run, start an RQ worker "
            "(see backend/railway.worker.json)."
            if queued is not None and queued > 50
            else None
        ),
    }

    # --- LLM configuration (no keys exposed) ---
    provider = settings.ai_provider
    if provider == "anthropic":
        key_ok = bool((settings.anthropic_api_key or "").strip())
    else:
        key_ok = bool((settings.openai_api_key or "").strip())

    out["llm"] = {
        "provider": provider,
        "model": settings.ai_model,
        "api_key_configured": key_ok,
        "probe": None,
    }

    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)
    ai_sent_24h = db.scalar(
        select(func.count()).select_from(AiRun).where(
            AiRun.outcome == "sent",
            AiRun.created_at >= since,
        )
    ) or 0
    ai_failed_24h = db.scalar(
        select(func.count()).select_from(AiRun).where(
            AiRun.outcome == "failed",
            AiRun.created_at >= since,
        )
    ) or 0
    out["llm"]["ai_runs_last_24h"] = {
        "sent": ai_sent_24h,
        "failed": ai_failed_24h,
    }

    if probe_llm:
        if not key_ok:
            out["llm"]["probe"] = {
                "ok": False,
                "error": f"Set {'ANTHROPIC_API_KEY' if provider == 'anthropic' else 'OPENAI_API_KEY'} for AI_PROVIDER={provider}.",
            }
        else:
            t2 = time.perf_counter()
            try:
                reply = get_llm().chat(
                    system="You are a connectivity check. Reply with one word only.",
                    messages=[{"role": "user", "content": "Say: ok"}],
                    max_tokens=32,
                )
                out["llm"]["probe"] = {
                    "ok": True,
                    "reply_preview": (reply or "")[:200],
                    "latency_ms": round((time.perf_counter() - t2) * 1000, 2),
                }
            except Exception as exc:  # noqa: BLE001
                out["llm"]["probe"] = {
                    "ok": False,
                    "error": str(exc)[:500],
                    "latency_ms": round((time.perf_counter() - t2) * 1000, 2),
                }

    # --- Embeddings (KB) ---
    emb = settings.ai_embedding_provider
    out["embeddings"] = {
        "provider": emb,
        "openai_api_key_configured": bool((settings.openai_api_key or "").strip()),
        "hint": (
            "KB embeddings use OpenAI; set OPENAI_API_KEY if you use the knowledge base."
            if emb == "openai" and not (settings.openai_api_key or "").strip()
            else None
        ),
    }

    out["summary"] = {
        "healthy": bool(
            db_ok
            and redis_ok
            and key_ok
            and (out["llm"].get("probe") is None or out["llm"]["probe"].get("ok") is not False)
        ),
        "notes": [
            "AI replies need: inbound webhook → worker → Redis lock → in_service_window → LLM → AiSensy session send.",
            "Use probe_llm=true to verify the LLM API key without sending WhatsApp traffic.",
        ],
    }

    return out
