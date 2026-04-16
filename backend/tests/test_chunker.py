from app.services.kb.chunker import chunk_text


def test_empty_returns_empty():
    assert chunk_text("") == []


def test_single_paragraph_single_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_splits_on_paragraphs():
    text = "para one content.\n\npara two content.\n\npara three content."
    chunks = chunk_text(text, max_chars=30, overlap=0)
    assert len(chunks) >= 2


def test_long_paragraph_hard_split():
    text = "x" * 500
    chunks = chunk_text(text, max_chars=100, overlap=10)
    assert len(chunks) >= 4
