"""AI runner: produces and sends an AI reply for an inbound message.

Invoked by the RQ worker after an inbound message is persisted. Re-checks all
guardrails immediately before sending so a late human takeover still wins.

Order of operations:
  1. Reload conversation and message inside a fresh DB session.
  2. Acquire a per-conversation Redis lock (prevents double-replies).
  3. Recheck state (AI_ACTIVE only) — skip otherwise.
  4. Recheck service window — outside window -> log and skip.
  5. Detect intent; if escalate/unsubscribe -> short circuit.
  6. Retrieve KB, call LLM, write draft message row.
  7. Recheck state one more time before calling AiSensy (takeover race).
  8. Send via AiSensyClient.send_session_message, mark sent or failed.
"""
from __future__ import annotations

import datetime as dt
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import lock
from app.db.session import SessionLocal
from app.integrations.aisensy import AiSensyClient, SessionSendPayload
from app.integrations.aisensy.client import get_aisensy_client
from app.models.agent import AgentProfile
from app.models.ai_run import AiRun
from app.models.conversation import (
    Conversation,
    ConversationState,
    Message,
)
from app.services.ai.intents import detect_intent
from app.services.ai.llm import get_llm
from app.services.ai.prompt import build_context_block, build_messages, build_system_prompt
from app.services.conversation.repo import add_outbound_message, mark_failed, mark_sent
from app.services.kb.retriever import retrieve, find_faq
from app.services.messaging.window import in_service_window
from app.utils.retries import ProviderPermanentError, ProviderTransientError

logger = get_logger("ai.runner")


def _default_agent(db: Session) -> AgentProfile | None:
    """Return the default agent profile; create a minimal one if none exist.

    Without this, fresh deployments that haven't run `scripts/seed.py` would
    silently never reply to inbound messages — a confusing "AI is dummy" state.
    The auto-created profile is safe and uses the business name from settings.
    """
    agent = db.scalar(
        select(AgentProfile).where(AgentProfile.is_default.is_(True)).limit(1)
    ) or db.scalar(select(AgentProfile).order_by(AgentProfile.created_at).limit(1))
    if agent is not None:
        return agent

    settings = get_settings()
    biz = settings.business_name or "our team"
    agent = AgentProfile(
        name=f"{biz} Default Agent",
        purpose=f"Handle customer enquiries and support for {biz} on WhatsApp.",
        tone="warm, helpful, professional",
        response_style="concise, 2-4 short lines, one clarifying question when needed",
        languages_supported=["en"],
        greeting_style=f"Hi! I'm the {biz} assistant. How can I help you today?",
        escalation_keywords=["human", "agent", "call me", "speak to someone"],
        forbidden_claims=[],
        allowed_domains=[],
        fallback_message=f"Let me connect you with someone from {biz} who can help.",
        human_handoff_message=f"A {biz} specialist will reach out to you shortly.",
        business_hours_behavior="respond_always",
        instructions="Be helpful and truthful. Do not invent facts; if unsure, say you'll check and get back.",
        is_default=True,
    )
    db.add(agent)
    try:
        db.flush()
    except Exception:  # noqa: BLE001 — race with another worker creating one
        db.rollback()
        agent = db.scalar(
            select(AgentProfile).where(AgentProfile.is_default.is_(True)).limit(1)
        ) or db.scalar(select(AgentProfile).order_by(AgentProfile.created_at).limit(1))
    return agent


def _escalation_reply(agent: AgentProfile) -> str:
    return (
        agent.human_handoff_message
        or "I'll connect you with a Terra Rex specialist shortly."
    )


def _run_llm(
    *,
    agent: AgentProfile,
    history: list[Message],
    latest_user_text: str,
    kb_chunks,
) -> str:
    settings = get_settings()
    system = build_system_prompt(agent, business_name=settings.business_name)
    kb_ctx = build_context_block(kb_chunks)
    messages = build_messages(
        history=history,
        latest_user_text=latest_user_text,
        kb_context=kb_ctx,
    )
    return get_llm().chat(system=system, messages=messages)


def handle_inbound(conversation_id: uuid.UUID, message_id: uuid.UUID) -> None:
    """Entry point called by the RQ worker."""
    db: Session = SessionLocal()
    started = time.monotonic()
    try:
        conversation = db.get(Conversation, conversation_id)
        message = db.get(Message, message_id)
        if conversation is None or message is None:
            return

        # (1) Pre-lock state check — quick exit if AI clearly should not run.
        if conversation.state != ConversationState.AI_ACTIVE:
            _record_ai_run(
                db,
                conversation_id=conversation_id,
                message_id=message_id,
                outcome="skipped_state",
                reason=f"state={conversation.state.value}",
            )
            db.commit()
            return

        lock_key = f"conv-lock:{conversation_id}"
        with lock(lock_key, ttl_ms=25_000, wait_ms=2_000) as acquired:
            if not acquired:
                logger.info("ai_lock_busy", conversation_id=str(conversation_id))
                return

            # Re-fetch to defeat stale state.
            db.refresh(conversation)

            if conversation.state != ConversationState.AI_ACTIVE:
                _record_ai_run(
                    db,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    outcome="skipped_state",
                    reason=f"state={conversation.state.value}",
                )
                db.commit()
                return

            if not in_service_window(conversation):
                _record_ai_run(
                    db,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    outcome="skipped_window",
                    reason="outside 24h window",
                )
                db.commit()
                return

            agent = _default_agent(db)
            if agent is None:
                _record_ai_run(
                    db,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    outcome="failed",
                    reason="no default agent profile configured",
                )
                db.commit()
                return

            user_text = (message.body or "").strip()
            intent = detect_intent(user_text)

            # Hard routing: unsubscribe / escalate short-circuit the LLM call.
            if intent == "unsubscribe":
                reply = (
                    "Got it — you won't receive further marketing messages. "
                    "If you need support, just reply here."
                )
                conversation.contact.unsubscribed = True  # type: ignore[union-attr]
            elif intent == "speak_to_human":
                reply = _escalation_reply(agent)
                conversation.state = ConversationState.AI_PAUSED
            else:
                faq = find_faq(db, query=user_text)
                if faq and len(user_text.split()) <= 8:
                    reply = faq.answer
                    kb_chunks = []
                else:
                    history = list(conversation.messages or [])
                    kb_chunks = retrieve(
                        db,
                        query=user_text,
                        agent_profile_id=agent.id,
                        top_k=4,
                    )
                    try:
                        reply = _run_llm(
                            agent=agent,
                            history=history,
                            latest_user_text=user_text,
                            kb_chunks=kb_chunks,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("llm_failed", error=str(exc))
                        reply = agent.fallback_message or (
                            "Let me connect you with a Terra Rex specialist who can help."
                        )

            if not reply.strip():
                reply = agent.fallback_message

            outbound = add_outbound_message(
                db,
                conversation=conversation,
                body=reply,
                sender_kind="ai",
            )

            # (7) One last state check before actually sending.
            db.flush()
            db.refresh(conversation)
            if conversation.state != ConversationState.AI_ACTIVE:
                mark_failed(db, outbound, error="skipped_due_to_takeover")
                _record_ai_run(
                    db,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    outcome="skipped_state",
                    reason="takeover after draft",
                )
                db.commit()
                return

            # Send.
            client: AiSensyClient = get_aisensy_client()
            try:
                resp = client.send_session_message(
                    SessionSendPayload(
                        destination=conversation.contact.phone_e164,
                        body=reply,
                    )
                )
            except (ProviderTransientError, ProviderPermanentError) as exc:
                mark_failed(db, outbound, error=str(exc))
                _record_ai_run(
                    db,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    outcome="failed",
                    reason=str(exc),
                    response=reply,
                )
                db.commit()
                return

            # AiSensy may return 2xx without a messageId. Only treat as failure
            # if the response carries an explicit error signal.
            err_hint = _response_error(resp)
            if err_hint is not None:
                mark_failed(db, outbound, error=err_hint)
                _record_ai_run(
                    db,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    outcome="failed",
                    reason=err_hint,
                    response=reply,
                )
                db.commit()
                return

            provider_id = _extract_provider_id(resp)
            mark_sent(db, outbound, provider_message_id=provider_id, payload=resp)

            _record_ai_run(
                db,
                conversation_id=conversation_id,
                message_id=message_id,
                outcome="sent",
                response=reply,
                intent=intent,
                latency_ms=int((time.monotonic() - started) * 1000),
                agent_profile_id=agent.id,
            )
            db.commit()
    finally:
        db.close()


def _extract_provider_id(resp: dict) -> str | None:
    if not isinstance(resp, dict):
        return None
    for key in ("messageId", "id", "message_id", "providerMessageId"):
        if resp.get(key):
            return str(resp[key])
    data = resp.get("data")
    if isinstance(data, dict):
        for key in ("messageId", "id"):
            if data.get(key):
                return str(data[key])
    return None


def _response_error(resp) -> str | None:
    """Return a short error string if AiSensy response explicitly signals failure."""
    if not isinstance(resp, dict):
        return None
    if resp.get("success") is False:
        return str(resp.get("message") or resp.get("error") or "success=false")[:300]
    status_val = str(resp.get("status") or "").lower()
    if status_val in {"error", "failed", "failure"}:
        return str(resp.get("message") or resp.get("error") or f"status={status_val}")[:300]
    err = resp.get("error") or resp.get("errors")
    if err:
        if isinstance(err, (list, tuple)):
            return ", ".join(str(x) for x in err)[:300]
        return str(err)[:300]
    code = resp.get("code")
    if isinstance(code, int) and code >= 400:
        return f"code={code} {resp.get('message') or ''}"[:300]
    return None


def _record_ai_run(
    db: Session,
    *,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    outcome: str,
    reason: str | None = None,
    response: str = "",
    intent: str | None = None,
    latency_ms: int | None = None,
    agent_profile_id: uuid.UUID | None = None,
) -> None:
    db.add(
        AiRun(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_profile_id=agent_profile_id,
            intent=intent,
            used_kb_chunks=[],
            prompt="",
            response=response,
            outcome=outcome,
            reason=reason,
            latency_ms=latency_ms,
        )
    )
