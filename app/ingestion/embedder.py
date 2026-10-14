"""Async embedding API wrapper (Task 1.3)."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 128

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Lazily build the async OpenAI client."""
    global _client
    if _client is None:
        api_key = settings.LLM_API_KEY.get_secret_value()
        if not api_key:
            raise RuntimeError(
                "LLM_API_KEY is not set; cannot call the embedding API."
            )
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts, returning one vector per input text.

    The returned vectors must each have ``settings.EMBEDDING_DIM``
    dimensions. Raises on API failure or dimension mismatch.
    """
    if not texts:
        return []

    client = _get_client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        try:
            response = await client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=batch,
            )
        except Exception as exc:
            logger.error(
                "Embedding request failed for batch starting at index %d (%d texts): %s",
                i,
                len(batch),
                exc,
            )
            raise
        # Responses may arrive unordered; restore input order via index.
        ordered = sorted(response.data, key=lambda d: d.index)
        for item in ordered:
            vectors.append(list(item.embedding))

    for vec in vectors:
        if len(vec) != settings.EMBEDDING_DIM:
            logger.error(
                "Embedding dimension mismatch: got %d, expected %d",
                len(vec),
                settings.EMBEDDING_DIM,
            )
            raise ValueError(
                f"Embedding dim {len(vec)} != settings.EMBEDDING_DIM "
                f"{settings.EMBEDDING_DIM}"
            )
    return vectors
