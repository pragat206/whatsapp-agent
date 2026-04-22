"""Integration diagnostics (AiSensy, etc.) — no secrets exposed."""
from __future__ import annotations

import datetime as dt
import time

from fastapi import APIRouter, Depends, Query, Request
from rq import Queue
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from app.api.deps import current_user, db_dep
from app.core.config import get_settings
from app.core.redis import get_redis
from app.integrations.aisensy import (
    CampaignSendPayload,
    SessionSendPayload,
    normalize_inbound,
)
from app.integrations.aisensy.client import get_aisensy_client
from app.models.ai_run import AiRun
from app.models.audit import RawWebhookEvent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.user import User
from app.services.ai.llm import get_llm
from app.utils.phone import safe_normalize
from app.utils.retries import ProviderPermanentError, ProviderTransientError

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _public_base_url(request: Request) -> str | None:
    """Best-effort URL for webhook hints (Railway sets X-Forwarded-*)."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        return None
    proto = (request.headers.get("x-forwarded-proto") or "https").split(",")[0].strip()
    return f"{proto}://{host}"


class TestSessionSendBody(BaseModel):
    phone: str = Field(..., description="Recipient phone in any reasonable format")
    body: str = Field("Test message from WhatsApp Agent.", description="Message body")


class TestCampaignSendBody(BaseModel):
    phone: str
    template_name: str
    template_params: list[str] = Field(default_factory=list)
    user_name: str = ""


@router.post("/aisensy/test-send-session")
def aisensy_test_send_session(
    body: TestSessionSendBody,
    _: User = Depends(current_user),
) -> dict:
    """Send a real session (free-form) message to a phone via AiSensy.

    Use this to verify the outbound API + key work end-to-end. The recipient
    must have messaged you in the last 24h or AiSensy will reject the send.
    Returns the raw AiSensy response so you can see exactly what came back.
    """
    phone = safe_normalize(body.phone)
    if not phone:
        return {"ok": False, "error": "invalid phone number"}
    payload = SessionSendPayload(destination=phone, body=body.body)
    try:
        resp = get_aisensy_client().send_session_message(payload)
    except ProviderPermanentError as exc:
        return {"ok": False, "error_type": "permanent", "error": str(exc)}
    except ProviderTransientError as exc:
        return {"ok": False, "error_type": "transient", "error": str(exc)}
    return {"ok": True, "raw_response": resp}


@router.post("/aisensy/test-send-campaign")
def aisensy_test_send_campaign(
    body: TestCampaignSendBody,
    _: User = Depends(current_user),
) -> dict:
    """Send one campaign-template message via AiSensy to verify template send.

    The template must already be approved on AiSensy under the same name.
    """
    phone = safe_normalize(body.phone)
    if not phone:
        return {"ok": False, "error": "invalid phone number"}
    settings = get_settings()
    payload = CampaignSendPayload(
        campaign_name=body.template_name,
        destination=phone,
        user_name=body.user_name,
        source=settings.aisensy_source,
        template_params=list(body.template_params),
        tags=[],
        attributes={},
    )
    try:
        resp = get_aisensy_client().send_campaign(payload)
    except ProviderPermanentError as exc:
        return {"ok": False, "error_type": "permanent", "error": str(exc)}
    except ProviderTransientError as exc:
        return {"ok": False, "error_type": "transient", "error": str(exc)}
    return {"ok": True, "raw_response": resp}


@router.post("/aisensy/probe-auth")
def aisensy_probe_auth(
    _: User = Depends(current_user),
) -> dict:
    """Probe which AiSensy credential + auth style the direct-apis endpoint accepts.

    Sends deliberately malformed requests to `/direct-apis/t1/messages` with
    every combination of (configured credential, auth header style):
      * Authorization: Bearer <token>
      * X-AiSensy-Project-API-Pwd: <token>

    An accepted combination will respond with a validation error about the
    message body (missing `to`, etc.) rather than "Invalid Token" or 401.
    That is how you identify which env var + `AISENSY_AUTH_METHOD` value to
    pin.

    No WhatsApp message is sent because the request body is empty.
    """
    import httpx
    settings = get_settings()
    credentials: dict[str, str] = {}
    if (settings.aisensy_api_token or "").strip():
        credentials["AISENSY_API_TOKEN"] = settings.aisensy_api_token.strip()
    if (settings.aisensy_api_key or "").strip():
        credentials["AISENSY_API_KEY"] = settings.aisensy_api_key.strip()
    if not credentials:
        return {"ok": False, "error": "neither AISENSY_API_TOKEN nor AISENSY_API_KEY is set"}

    styles: list[tuple[str, str]] = [
        ("bearer", "Authorization"),
        ("project_pwd", "X-AiSensy-Project-API-Pwd"),
    ]

    session_path = settings.aisensy_session_endpoint
    if "{project_id}" in session_path:
        project_id = (settings.aisensy_project_id or "").strip()
        if not project_id:
            return {
                "ok": False,
                "error": (
                    "AISENSY_SESSION_ENDPOINT contains {project_id} but "
                    "AISENSY_PROJECT_ID is not set. Copy the project id from "
                    "AiSensy dashboard > Project API Keys tab."
                ),
            }
        session_path = session_path.replace("{project_id}", project_id)
    url = f"{settings.aisensy_base_url}{session_path}"
    results = []
    with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as c:
        for env_name, token in credentials.items():
            for style_label, header_name in styles:
                header_value = f"Bearer {token}" if style_label == "bearer" else token
                try:
                    r = c.post(url, json={}, headers={header_name: header_value})
                    body = r.text[:300]
                    status = r.status_code
                    body_lc = body.lower()
                    verdict = (
                        "invalid_token"
                        if status == 401 or (status == 422 and "invalid token" in body_lc)
                        else "accepted_but_bad_request" if status in (400, 422) else
                        "ok" if status < 400 else f"other_{status}"
                    )
                except Exception as exc:  # noqa: BLE001
                    status = None
                    body = f"{type(exc).__name__}: {exc}"[:300]
                    verdict = "network_error"
                results.append({
                    "env_var": env_name,
                    "auth_style": style_label,
                    "status_code": status,
                    "response_preview": body,
                    "verdict": verdict,
                })
    accepted = [r for r in results if r["verdict"] in ("accepted_but_bad_request", "ok")]
    conclusion: str
    if accepted:
        w = accepted[0]
        conclusion = (
            f"Accepted: {w['env_var']} + auth_style={w['auth_style']}. "
            f"Set AISENSY_API_TOKEN to this value (if not already) and "
            f"AISENSY_AUTH_METHOD={w['auth_style']} to pin the style."
        )
    else:
        conclusion = (
            "No combination was accepted by /direct-apis/. Likely causes: "
            "(1) the token is for campaign API only — generate the project/"
            "direct-apis token in AiSensy dashboard → Manage → API Key; "
            "(2) trailing whitespace/newlines in the Railway env values; "
            "(3) the AiSensy plan does not include direct-apis."
        )
    return {
        "ok": True,
        "probed_endpoint": url,
        "results": results,
        "conclusion": conclusion,
    }


@router.post("/aisensy/test-normalize")
def aisensy_test_normalize(
    payload: dict,
    _: User = Depends(current_user),
) -> dict:
    """Dry-run the AiSensy inbound normalizer against any payload.

    Use this to debug a webhook shape without sending a real WhatsApp message.
    Returns the parsed NormalizedInbound fields or the reason parsing failed.
    """
    try:
        n = normalize_inbound(payload)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if n is None:
        return {
            "ok": False,
            "error": "normalizer returned None (no sender phone extractable)",
            "input_keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
        }
    return {
        "ok": True,
        "normalized": {
            "provider_message_id": n.provider_message_id,
            "from_phone_e164": n.from_phone_e164,
            "contact_name": n.contact_name,
            "text": n.text,
            "media_url": n.media_url,
            "media_type": n.media_type,
            "received_at": n.received_at.isoformat() if n.received_at else None,
            "human_intervention": n.human_intervention,
        },
    }


@router.get("/aisensy/recent-events")
def aisensy_recent_events(
    limit: int = Query(10, ge=1, le=50),
    kind: str | None = Query(None, description="inbound | status"),
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> dict:
    """Return the last N raw AiSensy webhook payloads.

    Critical for diagnosing "inbound webhooks arriving but no conversations":
    the real payload shape is visible here and the normalizer field paths can
    be adjusted to match.
    """
    stmt = (
        select(RawWebhookEvent)
        .where(RawWebhookEvent.provider == "aisensy")
        .order_by(RawWebhookEvent.created_at.desc())
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(RawWebhookEvent.kind == kind)
    rows = db.execute(stmt).scalars().all()
    return {
        "count": len(rows),
        "events": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "processed": r.processed,
                "error": r.error,
                "dedupe_key": r.dedupe_key,
                "payload": r.payload,
            }
            for r in rows
        ],
    }


@router.get("/aisensy")
def aisensy_diagnostics(
    request: Request,
    db: Session = Depends(db_dep),
    _: User = Depends(current_user),
) -> dict:
    """Explains why the dashboard may show no AiSensy data: this app mirrors webhooks + API sends into Postgres."""
    settings = get_settings()
    api_key_set = bool((settings.aisensy_api_key or "").strip())
    api_token_set = bool((settings.aisensy_api_token or "").strip())
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
    if "{project_id}" in settings.aisensy_session_endpoint and not (settings.aisensy_project_id or "").strip():
        hints.append(
            "AISENSY_SESSION_ENDPOINT uses Project API v1 ({project_id} placeholder) "
            "but AISENSY_PROJECT_ID is empty. All session sends (AI + human replies) "
            "will fail until you set AISENSY_PROJECT_ID to the project id shown in "
            "AiSensy dashboard > Project API Keys."
        )
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
    # Webhooks arriving but no conversation rows = topic/field mismatch, not
    # normalizer error (normalizer returned None silently because no phone
    # could be extracted). Tell the user exactly where to look.
    if inbound_total > 0 and convos_n == 0:
        hints.append(
            "Inbound webhook events are stored but no conversations were created. "
            "This usually means AiSensy's payload fields (phone, text) did not match "
            f"any path the normalizer knows. Inspect the raw payload via "
            f"GET /api/v1/integrations/aisensy/recent-events?kind=inbound and extend "
            "backend/app/integrations/aisensy/normalizer.py if needed."
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
            "aisensy_api_token_configured": api_token_set,
            "aisensy_bearer_source": "AISENSY_API_TOKEN" if api_token_set else ("AISENSY_API_KEY" if api_key_set else None),
            "aisensy_base_url": settings.aisensy_base_url,
            "aisensy_campaign_endpoint": settings.aisensy_campaign_endpoint,
            "aisensy_session_endpoint": settings.aisensy_session_endpoint,
            "aisensy_session_endpoint_needs_project_id": "{project_id}" in settings.aisensy_session_endpoint,
            "aisensy_project_id_configured": bool((settings.aisensy_project_id or "").strip()),
            "aisensy_auth_method": settings.aisensy_auth_method,
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
