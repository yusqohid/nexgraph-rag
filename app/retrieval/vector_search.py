"""Vector similarity search over document chunks."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def search_similar_chunks(
    session: AsyncSession, query_vec: list[float], top_k: int = 5
) -> list[dict[str, Any]]:
    """Return the nearest chunks ordered by cosine distance."""
    if not query_vec:
        raise ValueError("query_vec must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")

    result = await session.execute(
        text(
            """
            SELECT id AS chunk_id, document_id, chunk_index, content,
                   embedding <=> CAST(:query_vec AS vector) AS distance
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
            """
        ),
        {"query_vec": str(query_vec), "top_k": top_k},
    )
    return [dict(row) for row in result.mappings().all()]
