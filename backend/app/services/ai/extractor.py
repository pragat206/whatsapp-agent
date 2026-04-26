"""Post-reply lead extraction.

After every successful AI reply, the runner calls `extract_lead_facts` with
the latest conversation history. The LLM returns a JSON envelope describing:

  * `attributes`  — new structured facts the user shared (city, name,
                    monthly_bill, property_type, custom keys…). These get
                    merged into Contact's structured fields and the
                    `lead_extracted_attributes` JSON.
  * `status`      — one of: new | contacted | interested | qualified |
                    hot | converted | lost | nurturing
  * `next_action` — short imperative phrase (e.g. "send pricing quote",
                    "human follow-up", "schedule site visit", "none").
  * `score`       — 0..100 lead-quality score.
  * `summary`     — 2-3 sentence cumulative summary of the conversation.

The extractor is wrapped at the call site in try/except so any failure
(timeout, malformed JSON, provider 5xx) is logged but does NOT block the
user-facing reply, which has already been delivered.

Field changes are *merged*, not overwritten — a missing key in the
extractor output preserves the previous value. This means short turns
("ok", "thanks") don't wipe established facts.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.services.ai.llm import get_llm

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.conversation import Message


logger = get_logger("ai.extractor")


_VALID_STATUSES = {
    "new",
    "contacted",
    "interested",
    "qualified",
    "hot",
    "converted",
    "lost",
    "nurturing",
}


# Canonical contact columns we know how to copy from extractor output.
# Free-form keys land in `lead_extracted_attributes` instead of overwriting
# the typed columns, so business-specific fields are preserved without DDL.
_CANONICAL_COLUMNS = {
    "name",
    "city",
    "state",
    "property_type",
    "monthly_bill",
    "roof_type",
    "source",
    "notes",
}


_EXTRACTOR_SYSTEM = """You are a CRM extraction agent. Read the conversation and \
return ONE JSON object describing what the customer has revealed and what \
should happen next. Output ONLY the JSON object with no surrounding text, \
no markdown fences, no commentary.

Schema (all keys optional, omit a key when unknown):
{
  "attributes": {
    "name": "string",
    "city": "string",
    "state": "string",
    "property_type": "string",
    "monthly_bill": "string",
    "roof_type": "string",
    "<custom_key>": "string|number"
  },
  "status": "new|contacted|interested|qualified|hot|converted|lost|nurturing",
  "next_action": "short imperative phrase, e.g. 'send pricing quote', 'human follow-up', 'none'",
  "score": 0,
  "summary": "2-3 sentence cumulative description of who this person is, what they want, and where the conversation stands"
}

Rules:
- Never invent facts. Only include attributes the user has actually stated.
- If nothing new was said, omit `attributes` entirely (don't return null).
- Always include `status`, `summary`, and `score`.
- For `next_action`, choose the smallest concrete action: e.g. 'send pricing quote', 'book site visit', 'human follow-up', 'wait for reply', 'none'.
"""


def _format_history(messages: list[Message], limit: int = 30) -> str:
    """Render the last N messages as a plain transcript the LLM can read."""
    recent = messages[-limit:]
    lines: list[str] = []
    for m in recent:
        direction = getattr(m.direction, "value", m.direction)
        speaker = "Customer" if direction == "inbound" else "Agent"
        body = (m.body or "").strip()
        if body:
            lines.append(f"{speaker}: {body}")
    return "\n".join(lines)


def _coerce_json(raw: str) -> dict[str, Any] | None:
    """Best-effort parse — strip code fences / leading prose if the model added them."""
    if not raw:
        return None
    text = raw.strip()
    # Strip ```json ... ``` fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    # Find the first {...} block and parse it.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def extract_lead_facts(
    *,
    contact: Contact,
    history: list[Message],
    business_name: str,
) -> dict[str, Any] | None:
    """Run the extractor LLM call. Returns the parsed dict or None on failure.

    Caller is responsible for catching exceptions raised by the LLM client.
    This function only handles JSON-shape issues.
    """
    transcript = _format_history(history)
    if not transcript:
        return None

    user_prompt = (
        f"Business context: {business_name}\n"
        f"Customer phone: {contact.phone_e164}\n"
        f"Existing record (so you only return CHANGES or new info):\n"
        f"  name: {contact.name or '-'}\n"
        f"  city: {contact.city or '-'}\n"
        f"  state: {contact.state or '-'}\n"
        f"  property_type: {contact.property_type or '-'}\n"
        f"  monthly_bill: {contact.monthly_bill or '-'}\n"
        f"  roof_type: {contact.roof_type or '-'}\n"
        f"  current_status: {contact.lead_status or '-'}\n"
        f"  current_summary: {contact.lead_summary or '-'}\n"
        f"\nConversation transcript:\n{transcript}\n\n"
        "Return the JSON object only."
    )

    raw = get_llm().chat(
        system=_EXTRACTOR_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=500,
    )
    parsed = _coerce_json(raw or "")
    if parsed is None:
        logger.warning(
            "lead_extractor_unparsable_response",
            contact_id=str(contact.id),
            raw_preview=(raw or "")[:300],
        )
        return None
    return parsed


def apply_lead_facts(contact: Contact, facts: dict[str, Any]) -> dict[str, Any]:
    """Merge extractor output into the contact row in-place.

    Returns a small dict describing which fields changed, for logging.
    Caller must commit the session.
    """
    changed: dict[str, Any] = {}
    now = dt.datetime.now(dt.timezone.utc)

    attrs = facts.get("attributes")
    if isinstance(attrs, dict):
        # Canonical columns get copied to typed fields; everything else lands
        # in lead_extracted_attributes so we don't lose custom business keys.
        custom_attrs = dict(contact.lead_extracted_attributes or {})
        for key, value in attrs.items():
            if value in (None, "", []):
                continue
            value_str = str(value).strip()[:200] if isinstance(value, (int, float)) else str(value).strip()
            if not value_str:
                continue
            if key in _CANONICAL_COLUMNS:
                current = getattr(contact, key, None)
                if current != value_str:
                    setattr(contact, key, value_str[:200])
                    changed[key] = value_str
            else:
                if custom_attrs.get(key) != value_str:
                    custom_attrs[key] = value_str
                    changed[f"attr.{key}"] = value_str
        if custom_attrs != (contact.lead_extracted_attributes or {}):
            contact.lead_extracted_attributes = custom_attrs

    status = facts.get("status")
    if isinstance(status, str) and status.strip().lower() in _VALID_STATUSES:
        new_status = status.strip().lower()
        if contact.lead_status != new_status:
            contact.lead_status = new_status
            changed["lead_status"] = new_status

    next_action = facts.get("next_action")
    if isinstance(next_action, str) and next_action.strip():
        cleaned = next_action.strip()[:200]
        if contact.lead_next_action != cleaned:
            contact.lead_next_action = cleaned
            changed["lead_next_action"] = cleaned

    score = facts.get("score")
    if isinstance(score, (int, float)):
        clamped = max(0, min(100, int(score)))
        if contact.lead_score != clamped:
            contact.lead_score = clamped
            changed["lead_score"] = clamped

    summary = facts.get("summary")
    if isinstance(summary, str) and summary.strip():
        cleaned = summary.strip()[:1500]
        if contact.lead_summary != cleaned:
            contact.lead_summary = cleaned
            changed["lead_summary"] = "<updated>"

    if changed:
        contact.lead_updated_at = now

    return changed
