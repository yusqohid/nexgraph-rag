"""Asynchronous Google Gemini embedding wrapper."""
import logging
import math
from typing import Literal
from google.genai import types
from app.config import settings
from app.llm import get_client, request_semaphore

logger = logging.getLogger(__name__)
_BATCH_SIZE = 100


async def get_embeddings(
    texts: list[str],
    task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Return one normalized 1536-dimensional vector per input."""
    if not texts:
        return []
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), _BATCH_SIZE):
        batch = texts[offset : offset + _BATCH_SIZE]
        try:
            async with request_semaphore:
                response = await get_client().aio.models.embed_content(
                    model=settings.EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        output_dimensionality=settings.EMBEDDING_DIM, task_type=task_type,
                    ),
                )
            embeddings = response.embeddings or []
            if len(embeddings) != len(batch):
                raise ValueError("Embedding response count differs from input count")
            for embedding in embeddings:
                vector = embedding.values or []
                if len(vector) != settings.EMBEDDING_DIM:
                    raise ValueError("Embedding dimension differs from EMBEDDING_DIM")
                if not all(math.isfinite(value) for value in vector):
                    raise ValueError("Embedding contains non-finite values")
                norm = math.sqrt(sum(value * value for value in vector))
                if norm == 0:
                    raise ValueError("Embedding has zero norm")
                vectors.append([value / norm for value in vector])
        except Exception:
            logger.exception("Gemini embedding failed for batch at index %d", offset)
            raise
    return vectors
