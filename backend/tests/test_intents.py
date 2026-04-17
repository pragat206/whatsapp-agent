from app.services.ai.intents import detect_intent


def test_detects_speak_to_human():
    assert detect_intent("can I talk to a human please") == "speak_to_human"


def test_detects_pricing_hindi_keyword():
    assert detect_intent("3kW ka price kitna hoga") == "pricing_interest"


def test_detects_subsidy():
    assert detect_intent("is there a subsidy available") == "subsidy_question"


def test_unknown_returns_none():
    assert detect_intent("random gibberish message") is None
