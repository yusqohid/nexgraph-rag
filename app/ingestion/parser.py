"""Hierarchical text chunker (Task 1.3).

Splits long documents into overlapping chunks, preferring paragraph
(``\\n\\n``) or sentence (``. ``) boundaries nearest to ``chunk_size``
so words are never cut mid-token.
"""

from __future__ import annotations


def chunk_document(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split ``text`` into overlapping chunks.

    Args:
        text: Source document text.
        chunk_size: Maximum characters per chunk (must be > 0).
        overlap: Characters of overlap between consecutive chunks
            (must be >= 0 and < ``chunk_size``).

    Returns:
        List of non-empty, stripped chunk strings. Empty or
        whitespace-only input yields ``[]``.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    if not text or not text.strip():
        return []

    n = len(text)
    chunks: list[str] = []
    start = 0

    while start < n:
        end = min(start + chunk_size, n)
        if end >= n:
            tail = text[start:].strip()
            if tail:
                chunks.append(tail)
            break

        cut = _find_cut(text, start, end)
        raw = text[start:cut].strip()
        if raw:
            chunks.append(raw)

        # Overlap backwards from the cut point, then snap to a word
        # boundary so a chunk never starts mid-word. Snap *back* to the
        # previous separator (more overlap) when landing inside a word.
        if cut - start <= overlap:
            next_start = cut
        elif overlap == 0:
            next_start = cut
        else:
            candidate = cut - overlap
            if candidate <= start:
                next_start = cut
            elif text[candidate] in (" ", "\n"):
                ns = candidate + 1
                while ns < cut and text[ns] in (" ", "\n"):
                    ns += 1
                next_start = ns if ns < cut else cut
            else:
                sep = max(
                    text.rfind(" ", start, candidate),
                    text.rfind("\n", start, candidate),
                )
                next_start = sep + 1 if sep + 1 > start else cut
        if next_start <= start or next_start > cut:
            next_start = cut
        start = next_start

    return chunks


def _find_cut(text: str, start: int, end: int) -> int:
    """Find the nearest paragraph/sentence/word boundary at or before ``end``."""
    # Only look back a bounded window so chunks stay near chunk_size.
    window_start = max(start, end - 256)
    window = text[window_start:end]

    candidates: list[int] = []
    para = window.rfind("\n\n")
    if para != -1:
        candidates.append(window_start + para)
    sent = window.rfind(". ")
    if sent != -1:
        # Include the closing period in the current chunk.
        candidates.append(window_start + sent + 1)
    newline = window.rfind("\n")
    if newline != -1:
        candidates.append(window_start + newline)
    space = window.rfind(" ")
    if space != -1:
        candidates.append(window_start + space)

    if not candidates:
        return end

    cut = max(candidates)
    # Guard against degenerate tiny chunks.
    if cut <= start:
        return end
    return cut
