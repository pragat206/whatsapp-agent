"""Keyword + pattern based intent detection.

Kept intentionally simple and deterministic. Covers the Terra Rex Energy
starter intents and Hindi-friendly keywords. Not a classifier — just routing
hints that feed into the prompt and escalation logic.
"""
from __future__ import annotations

import re

INTENTS: dict[str, list[str]] = {
    # Require explicit handoff phrases; bare words like "support" or "agent"
    # match too many legitimate enquiries and were short-circuiting every reply
    # straight to the fallback / human-handoff path.
    "speak_to_human": [
        "speak to a human",
        "talk to a human",
        "speak to someone",
        "talk to someone",
        "talk to a person",
        "real person",
        "real agent",
        "human agent",
        "live agent",
        "customer care",
        "customer support",
        "call me back",
        "please call me",
        "connect me to",
    ],
    "unsubscribe":           ["stop", "unsubscribe", "remove me", "don't message", "do not contact"],
    "product_info":          ["product", "panel", "inverter", "battery", "kw", "kwp", "solution"],
    "residential_solar_query": ["home", "house", "residential", "rooftop", "apartment", "villa"],
    "commercial_solar_query":  ["commercial", "factory", "industrial", "business", "office", "company"],
    "pricing_interest":      ["price", "cost", "quote", "quotation", "kitna", "kitne", "budget", "estimate"],
    "subsidy_question":      ["subsidy", "government", "scheme", "pm surya ghar", "rooftop scheme"],
    "financing_question":    ["emi", "loan", "finance", "installment", "installments", "bajaj"],
    "site_visit_request":    ["site visit", "survey", "inspection", "visit karo", "come over"],
    "callback_request":      ["call me", "callback", "call back", "phone call", "give a call"],
    "service_support":       ["service", "not working", "issue", "problem", "support", "kharab", "repair"],
    "warranty_question":     ["warranty", "amc", "maintenance contract", "guarantee"],
    "campaign_reply_positive": ["yes", "interested", "haan", "ha", "sure", "ok"],
    "campaign_reply_negative": ["no", "not interested", "nahi", "nhi"],
}


def detect_intent(text: str) -> str | None:
    t = (text or "").lower()
    if not t:
        return None
    for intent, keywords in INTENTS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", t):
                return intent
    return None
