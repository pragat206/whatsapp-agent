"""Prompt assembly for the AI runner.

The system prompt is structured so the operator-configured fields
(`instructions`, `greeting_style`, `tone`, `purpose`, `forbidden_claims`,
`fallback_message`, `human_handoff_message`) take priority over generic
guardrails. Knowledge-base excerpts are embedded directly in the system
prompt so the model treats them as authoritative reference rather than
conversation history.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.kb.retriever import RetrievedChunk

if TYPE_CHECKING:
    from app.models.agent import AgentProfile
    from app.models.conversation import Message


# Per-chunk truncation. Bumped from 700 -> 1400 so structured scripts
# survive intact when the operator uploads a PDF script.
_KB_CHUNK_CHAR_LIMIT = 1400


def build_system_prompt(
    agent: AgentProfile,
    business_name: str,
    *,
    kb_chunks: list[RetrievedChunk] | None = None,
    is_first_reply: bool = False,
    customer_memory: str | None = None,
) -> str:
    """Assemble the system prompt for one LLM call.

    Order is deliberate: operator instructions, customer memory, and KB
    excerpts come BEFORE the generic guardrails. LLMs weight earlier
    content more heavily, so this keeps custom persona / business-specific
    behavior from being overridden by the boilerplate.

    `customer_memory` is the per-contact "Known about this customer" block
    — name, city, monthly_bill, lead_summary, etc. — assembled from the
    Contact row by the runner. Injecting it here is what stops the AI
    from re-asking for facts the user has already shared.
    """
    sections: list[str] = []

    # 1. Identity
    purpose = (agent.purpose or "").strip() or f"WhatsApp assistant for {business_name}"
    sections.append(
        f"You are the WhatsApp assistant for {business_name}.\n"
        f"Role: {purpose}"
    )

    # 2. Per-customer memory — placed early so the model treats these facts
    # as ground truth before any KB lookup or guardrail kicks in.
    if customer_memory:
        sections.append(
            "Known about this customer (DO NOT re-ask for any of this — "
            "use it directly when relevant):\n"
            f"{customer_memory}"
        )

    # 2. Operator instructions — top priority.
    instructions = (agent.instructions or "").strip()
    if instructions:
        sections.append(
            "ADMIN INSTRUCTIONS (highest priority — follow these exactly):\n"
            f"{instructions}"
        )

    # 3. Knowledge base excerpts — embedded in system prompt so the model
    # treats them as authoritative, not as conversation history.
    kb_section = _format_kb_section(kb_chunks or [])
    if kb_section:
        sections.append(kb_section)

    # 4. Persona configuration from the Agent tab.
    persona_lines = [
        f"Tone: {agent.tone}" if agent.tone else None,
        f"Response style: {agent.response_style}" if agent.response_style else None,
    ]
    languages = agent.languages_supported or ["en"]
    persona_lines.append(f"Languages: reply in the user's language; supported: {', '.join(languages)}.")
    sections.append("Persona:\n" + "\n".join(f"- {line}" for line in persona_lines if line))

    # 5. Greeting — explicitly told to use it on the first reply only.
    greeting = (agent.greeting_style or "").strip()
    if greeting:
        if is_first_reply:
            sections.append(
                "Greeting (use this on the FIRST reply of a new conversation, then drop it):\n"
                f"{greeting}"
            )
        else:
            sections.append(
                "Greeting style for reference (do NOT repeat it — this is not the first reply):\n"
                f"{greeting}"
            )

    # 6. Escalation behavior — give the model the exact strings to use.
    escalate_keywords = ", ".join(agent.escalation_keywords or [])
    handoff = (agent.human_handoff_message or "").strip()
    fallback = (agent.fallback_message or "").strip()
    escalation_lines = []
    if escalate_keywords:
        escalation_lines.append(
            f"If the user asks for a human or uses any of [{escalate_keywords}], "
            "answer briefly and offer to connect them."
        )
    if handoff:
        escalation_lines.append(f"When connecting to a human, say: \"{handoff}\"")
    if fallback:
        escalation_lines.append(f"If you cannot answer, say: \"{fallback}\"")
    if escalation_lines:
        sections.append("Escalation:\n" + "\n".join(f"- {l}" for l in escalation_lines))

    # 7. Forbidden claims (operator-configured) — listed only if any.
    forbidden = [c for c in (agent.forbidden_claims or []) if c]
    if forbidden:
        sections.append(
            "Forbidden claims (never make these):\n"
            + "\n".join(f"- {c}" for c in forbidden)
        )

    # 8. Generic guardrails — last, so they don't override the above.
    sections.append(
        "General guardrails:\n"
        "- WhatsApp replies: keep under 4 short lines unless the user explicitly asks for detail.\n"
        "- Ask at most ONE follow-up question per reply.\n"
        "- If a fact is not in the admin instructions or knowledge base above, say you'll check rather than guess.\n"
        "- Stay in character as defined under Persona."
    )

    return "\n\n".join(sections)


def _format_kb_section(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return (
            "Knowledge base: no excerpts matched this query. "
            "Answer only from the admin instructions above; do not invent "
            "company-specific facts (prices, timelines, terms)."
        )
    lines = [
        "Knowledge base excerpts (PREFER these over your general knowledge — quote or paraphrase when answering):",
    ]
    for i, c in enumerate(chunks, 1):
        src = c.source_title or "KB"
        text = c.text.strip()[:_KB_CHUNK_CHAR_LIMIT]
        lines.append(f"[{i}] ({src})\n{text}")
    return "\n".join(lines)


# Kept as a thin shim so existing imports keep working; new code should
# pass kb_chunks directly to build_system_prompt.
def build_context_block(chunks: list[RetrievedChunk]) -> str:
    return _format_kb_section(chunks)


def build_messages(
    *,
    history: list[Message],
    latest_user_text: str,
    max_history: int = 10,
) -> list[dict]:
    """Build the message array for the LLM.

    KB context is no longer injected here — it now lives in the system
    prompt where the model treats it as authoritative reference. This
    function only handles real conversation history + the latest turn.
    """
    recent = history[-max_history:]
    messages: list[dict] = []
    for m in recent:
        # `direction` is a str-Enum (`inbound` / `outbound`); compare on the
        # string value so this module avoids importing app.models at runtime.
        direction_value = getattr(m.direction, "value", m.direction)
        role = "user" if direction_value == "inbound" else "assistant"
        content = m.body.strip()
        if content:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": latest_user_text})
    elif messages[-1]["content"] != latest_user_text:
        messages.append({"role": "user", "content": latest_user_text})
    return messages
