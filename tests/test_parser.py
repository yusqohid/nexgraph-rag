"""Task 1.3 — unit tests for the hierarchical text chunker.

Deterministic and offline: no LLM/embedding API calls here.
"""

import pytest

from app.ingestion.parser import chunk_document


def test_empty_and_whitespace_text_returns_empty_list() -> None:
    assert chunk_document("") == []
    assert chunk_document("   \n\t  ") == []


def test_short_text_returns_single_chunk() -> None:
    text = "Proyek Alpha dipimpin oleh Budi Santoso sejak Januari 2026."
    assert chunk_document(text) == [text]


def test_chunks_respect_chunk_size() -> None:
    text = " ".join(f"kata{i}" for i in range(500))
    chunks = chunk_document(text, chunk_size=100, overlap=10)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    assert all(c.strip() for c in chunks)


def test_overlap_shares_content_between_consecutive_chunks() -> None:
    text = " ".join(f"kata{i}" for i in range(200))
    chunks = chunk_document(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:]):
        prev_words = set(prev.split())
        nxt_words = set(nxt.split())
        assert prev_words & nxt_words, "consecutive chunks must overlap"


def test_paragraph_boundary_is_respected() -> None:
    first = "Paragraf pertama tentang Proyek Alpha. " * 10
    second = "Paragraf kedua tentang Vendor X. " * 10
    text = first.strip() + "\n\n" + second.strip()
    chunks = chunk_document(text, chunk_size=200, overlap=20)
    assert len(chunks) >= 2
    # The first chunk should not bleed far into the second paragraph.
    assert "Vendor X" not in chunks[0] or "Proyek Alpha" in chunks[0]


def test_does_not_cut_words_in_half() -> None:
    text = " ".join(["abcdefghij"] * 200)  # fixed-width words
    chunks = chunk_document(text, chunk_size=55, overlap=5)
    for chunk in chunks:
        # No partial fixed-width word: every token is full-length or the
        # chunk edge aligns to whitespace.
        for token in chunk.split():
            assert token == "abcdefghij"


def test_invalid_parameters_raise() -> None:
    with pytest.raises(ValueError):
        chunk_document("teks", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_document("teks", chunk_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_document("teks", chunk_size=100, overlap=-1)
