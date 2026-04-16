"""Prompt assembly for the AI runner."""
from __future__ import annotations

from app.models.agent import AgentProfile
from app.models.conversation import Message, MessageDirection
from app.services.kb.retriever import RetrievedChunk


def build_system_prompt(agent: AgentProfile, business_name: str) -> str:
    langs = ", ".join(agent.languages_supported or ["en"])
    forbid = "\n".join(f"- {c}" for c in (agent.forbidden_claims or [])) or "- none specified"
    escalate = ", ".join(agent.escalation_keywords or [])
    return f"""You are the WhatsApp AI assistant for {business_name}.

Role: {agent.purpose or 'solar sales + support assistant'}
Tone: {agent.tone}
Response style: {agent.response_style} (WhatsApp replies — keep under 4 short lines).
Languages: reply in the user's language; supported: {langs}.

Rules:
- Never invent prices, subsidy amounts, timelines, or warranty terms. If you don't know, say so and offer to connect the user to a specialist.
- Do not make the following claims: {forbid}
- If the user asks to speak to a human, or uses any of these words ({escalate}), answer briefly and offer to connect them to the team.
- Ask at most ONE follow-up question per reply.
- When collecting leads, gather: name, city, property type, monthly electricity bill — but only one at a time, conversationally.
- Keep replies friendly and human, not robotic. No bullet lists unless clarifying steps.

Additional instructions from the admin:
{agent.instructions or '(none)'}
"""


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No knowledge base excerpts matched. Answer from general solar knowledge but do not invent company-specific details."
    lines = ["Relevant knowledge base excerpts:"]
    for i, c in enumerate(chunks, 1):
        src = c.source_title or "KB"
        lines.append(f"[{i}] ({src}) {c.text.strip()[:700]}")
    return "\n".join(lines)


def build_messages(
    *,
    history: list[Message],
    latest_user_text: str,
    kb_context: str,
    max_history: int = 10,
) -> list[dict]:
    recent = history[-max_history:]
    messages: list[dict] = []
    if kb_context:
        messages.append({"role": "user", "content": f"[context]\n{kb_context}"})
        messages.append({"role": "assistant", "content": "Understood. I'll use this context."})
    for m in recent:
        role = "user" if m.direction == MessageDirection.inbound else "assistant"
        content = m.body.strip()
        if content:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": latest_user_text})
    elif messages[-1]["content"] != latest_user_text:
        messages.append({"role": "user", "content": latest_user_text})
    return messages
