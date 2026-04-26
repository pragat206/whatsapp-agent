"""Tests for the lead extractor service.

Focus areas:
  * Extractor JSON parsing is robust to fenced/prefixed responses.
  * apply_lead_facts merges (does not overwrite) existing fields.
  * Custom keys land in lead_extracted_attributes; canonical keys land
    on the typed columns.
  * Invalid status strings are ignored.
  * No changes => lead_updated_at is NOT bumped (so the dashboard's
    "recently updated" sort stays meaningful).
"""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services.ai.extractor import _coerce_json, apply_lead_facts


def _contact(**overrides):
    base = dict(
        id="11111111-1111-1111-1111-111111111111",
        phone_e164="+919999999999",
        name=None,
        city=None,
        state=None,
        property_type=None,
        monthly_bill=None,
        roof_type=None,
        source=None,
        notes=None,
        tags=[],
        attributes={},
        unsubscribed=False,
        lead_status=None,
        lead_next_action=None,
        lead_next_action_at=None,
        lead_summary=None,
        lead_score=None,
        lead_extracted_attributes={},
        lead_updated_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_coerce_json_handles_plain_object():
    assert _coerce_json('{"status": "interested"}') == {"status": "interested"}


def test_coerce_json_strips_markdown_fences():
    raw = "```json\n{\"status\": \"hot\", \"score\": 85}\n```"
    assert _coerce_json(raw) == {"status": "hot", "score": 85}


def test_coerce_json_finds_object_inside_prose():
    raw = "Here is the extraction:\n{\"status\": \"qualified\"}\nThanks."
    assert _coerce_json(raw) == {"status": "qualified"}


def test_coerce_json_returns_none_on_garbage():
    assert _coerce_json("not json at all") is None
    assert _coerce_json("") is None
    assert _coerce_json("{ broken") is None


def test_apply_facts_writes_canonical_columns():
    contact = _contact()
    changed = apply_lead_facts(
        contact,
        {
            "attributes": {"name": "Pragat", "city": "Mumbai", "monthly_bill": "5000"},
            "status": "interested",
            "next_action": "send pricing quote",
            "score": 75,
            "summary": "Customer in Mumbai exploring solar.",
        },
    )
    assert contact.name == "Pragat"
    assert contact.city == "Mumbai"
    assert contact.monthly_bill == "5000"
    assert contact.lead_status == "interested"
    assert contact.lead_next_action == "send pricing quote"
    assert contact.lead_score == 75
    assert "Mumbai" in (contact.lead_summary or "")
    assert "name" in changed and "lead_status" in changed
    assert contact.lead_updated_at is not None


def test_apply_facts_preserves_existing_when_attribute_missing():
    """A short reply ('ok') should NOT wipe established facts."""
    contact = _contact(name="Pragat", city="Mumbai", lead_status="interested")
    changed = apply_lead_facts(
        contact,
        {"summary": "Customer acknowledged."},
    )
    assert contact.name == "Pragat"
    assert contact.city == "Mumbai"
    assert contact.lead_status == "interested"
    assert "lead_summary" in changed


def test_apply_facts_routes_custom_keys_into_extracted_attributes():
    contact = _contact()
    apply_lead_facts(
        contact,
        {
            "attributes": {
                "city": "Delhi",                   # canonical
                "preferred_callback_time": "evening",  # custom
                "budget_range": "100k-200k",          # custom
            }
        },
    )
    assert contact.city == "Delhi"
    assert contact.lead_extracted_attributes == {
        "preferred_callback_time": "evening",
        "budget_range": "100k-200k",
    }


def test_apply_facts_ignores_invalid_status():
    contact = _contact(lead_status="interested")
    apply_lead_facts(contact, {"status": "ULTRA_HOT_INVALID"})
    assert contact.lead_status == "interested"  # unchanged


def test_apply_facts_clamps_score_to_0_100():
    contact = _contact()
    apply_lead_facts(contact, {"score": 150})
    assert contact.lead_score == 100
    apply_lead_facts(contact, {"score": -10})
    assert contact.lead_score == 0


def test_apply_facts_no_changes_does_not_bump_updated_at():
    """Idempotent re-extraction with same data shouldn't update the timestamp."""
    contact = _contact(name="Pragat", lead_status="interested")
    initial_updated = contact.lead_updated_at  # None
    changed = apply_lead_facts(
        contact,
        {"attributes": {"name": "Pragat"}, "status": "interested"},
    )
    assert changed == {}
    assert contact.lead_updated_at == initial_updated  # still None


def test_apply_facts_drops_blank_attribute_values():
    contact = _contact(city="Mumbai")
    apply_lead_facts(contact, {"attributes": {"city": "", "name": None, "state": "  "}})
    assert contact.city == "Mumbai"  # not wiped by empty string
    assert contact.name is None
    assert contact.state is None
