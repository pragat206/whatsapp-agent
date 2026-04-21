"""AiSensy normalizer tests."""
from __future__ import annotations

from app.integrations.aisensy.normalizer import normalize_inbound, normalize_status


def test_normalize_inbound_basic():
    payload = {
        "messageId": "prov-123",
        "from": "+919876543210",
        "senderName": "Rajesh",
        "text": "Hi, I'm interested in solar",
        "timestamp": "2026-04-16T10:30:00Z",
    }
    n = normalize_inbound(payload)
    assert n is not None
    assert n.provider_message_id == "prov-123"
    assert n.from_phone_e164 == "+919876543210"
    assert n.contact_name == "Rajesh"
    assert "interested in solar" in n.text
    assert n.human_intervention is False


def test_normalize_inbound_detects_external_human_intervention():
    payload = {
        "id": "x",
        "waId": "+919876543210",
        "text": "Hi there, this is an agent",
        "eventType": "agent_reply",
    }
    n = normalize_inbound(payload)
    assert n is not None
    assert n.human_intervention is True


def test_normalize_inbound_returns_none_when_no_sender():
    assert normalize_inbound({"text": "hello"}) is None


def test_normalize_inbound_handles_nested_message():
    payload = {
        "eventType": "message",
        "message": {"id": "nested-1", "waId": "+919876543210", "body": "hello"},
    }
    n = normalize_inbound(payload)
    assert n is not None
    assert n.provider_message_id == "nested-1"
    assert n.text == "hello"


def test_normalize_inbound_handles_aisensy_sender_mobile():
    """AiSensy `message.sender.user` topic typically carries `senderMobile`."""
    payload = {
        "messageId": "wamid.abc",
        "senderMobile": "+919876543210",
        "senderName": "Rajesh",
        "messageType": "text",
        "text": "Hi, interested in solar",
        "timestamp": 1713456789,
    }
    n = normalize_inbound(payload)
    assert n is not None
    assert n.from_phone_e164 == "+919876543210"
    assert n.contact_name == "Rajesh"
    assert "solar" in n.text


def test_normalize_inbound_handles_nested_payload_shape():
    """Some AiSensy payloads nest the body under `payload.source`/`payload.text`."""
    payload = {
        "type": "message",
        "payload": {
            "source": "+919876543210",
            "type": "text",
            "text": "hello there",
            "sender": {"name": "Neha", "phone": "+919876543210"},
        },
    }
    n = normalize_inbound(payload)
    assert n is not None
    assert n.from_phone_e164 == "+919876543210"
    assert n.contact_name == "Neha"
    assert n.text == "hello there"


def test_normalize_inbound_handles_sender_object_only():
    payload = {
        "messageId": "m1",
        "sender": {"phone": "+919876543210", "name": "Amit"},
        "text": "yo",
    }
    n = normalize_inbound(payload)
    assert n is not None
    assert n.from_phone_e164 == "+919876543210"
    assert n.contact_name == "Amit"


def test_normalize_status_maps_known_events():
    s = normalize_status({"messageId": "abc", "status": "delivered"})
    assert s is not None
    assert s.status == "delivered"


def test_normalize_status_bad_payload_returns_none():
    assert normalize_status({"no": "id"}) is None
