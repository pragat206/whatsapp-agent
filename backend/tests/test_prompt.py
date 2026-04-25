"""Verify the assembled system prompt actually contains the operator-configured fields.

Regression guard: previously `greeting_style` was silently dropped, hardcoded
solar rules were placed before `agent.instructions`, and KB excerpts went into
a fake user/assistant turn instead of the system prompt.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.prompt import build_messages, build_system_prompt
from app.services.kb.retriever import RetrievedChunk


def _agent(**overrides):
    base = dict(
        purpose="Onboard new gym members",
        tone="warm, casual, no jargon",
        response_style="2-3 lines, friendly",
        languages_supported=["en", "hi"],
        greeting_style="Namaste! Welcome to FitClub.",
        escalation_keywords=["human", "manager"],
        forbidden_claims=["Free for life", "100% guaranteed weight loss"],
        fallback_message="Let me check with the team and get back to you.",
        human_handoff_message="Connecting you with a FitClub coach now.",
        instructions="Always confirm the user's preferred slot before booking.",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _chunk(text: str, title: str = "PDF Script") -> RetrievedChunk:
    import uuid as _u
    return RetrievedChunk(
        document_id=_u.uuid4(),
        text=text,
        score=0.9,
        category=None,
        source_title=title,
    )


def test_system_prompt_includes_admin_instructions_above_guardrails():
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub")
    instr_idx = sys_prompt.find("Always confirm the user's preferred slot")
    guard_idx = sys_prompt.find("General guardrails")
    assert instr_idx != -1, "admin instructions missing from system prompt"
    assert guard_idx != -1
    assert instr_idx < guard_idx, "admin instructions must appear before generic guardrails"


def test_system_prompt_includes_greeting_on_first_reply():
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub", is_first_reply=True)
    assert "Namaste! Welcome to FitClub." in sys_prompt
    assert "FIRST reply" in sys_prompt


def test_system_prompt_does_not_repeat_greeting_after_first_reply():
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub", is_first_reply=False)
    assert "do NOT repeat" in sys_prompt


def test_system_prompt_includes_handoff_and_fallback_strings():
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub")
    assert "Connecting you with a FitClub coach now." in sys_prompt
    assert "Let me check with the team and get back to you." in sys_prompt


def test_system_prompt_includes_forbidden_claims():
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub")
    assert "100% guaranteed weight loss" in sys_prompt
    assert "Forbidden claims" in sys_prompt


def test_system_prompt_embeds_kb_excerpts_inside_system_block():
    chunks = [
        _chunk("Step 1: ask for the member's goal.\nStep 2: suggest a trial plan.", title="Onboarding Script"),
        _chunk("Refund policy: full refund within 7 days.", title="Policies"),
    ]
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub", kb_chunks=chunks)
    assert "Knowledge base excerpts" in sys_prompt
    assert "Step 1: ask for the member's goal." in sys_prompt
    assert "Refund policy: full refund within 7 days." in sys_prompt
    assert "PREFER these" in sys_prompt


def test_system_prompt_warns_when_no_kb_chunks():
    sys_prompt = build_system_prompt(_agent(), business_name="FitClub", kb_chunks=[])
    assert "no excerpts matched" in sys_prompt


def test_build_messages_no_longer_injects_kb_as_fake_user_turn():
    """Regression: KB used to be smuggled in as a fake user/assistant turn."""
    msgs = build_messages(history=[], latest_user_text="hi")
    assert len(msgs) == 1
    assert msgs[0] == {"role": "user", "content": "hi"}
    # ensure no "[context]" prefix snuck in
    for m in msgs:
        assert "[context]" not in m["content"]


def test_system_prompt_falls_back_to_business_name_when_purpose_blank():
    agent = _agent(purpose="")
    sys_prompt = build_system_prompt(agent, business_name="FitClub")
    assert "FitClub" in sys_prompt


def test_system_prompt_omits_optional_sections_when_unconfigured():
    agent = _agent(
        instructions="",
        greeting_style="",
        forbidden_claims=[],
        human_handoff_message="",
        fallback_message="",
        escalation_keywords=[],
    )
    sys_prompt = build_system_prompt(agent, business_name="FitClub")
    assert "ADMIN INSTRUCTIONS" not in sys_prompt
    assert "Greeting" not in sys_prompt
    assert "Forbidden claims" not in sys_prompt
    assert "Escalation:" not in sys_prompt
    # Persona + guardrails should still be there.
    assert "Persona:" in sys_prompt
    assert "General guardrails" in sys_prompt
