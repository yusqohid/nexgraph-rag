"""Vector similarity and lexical search over document chunks."""

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


async def search_fts_chunks(
    session: AsyncSession, query_text: str, top_k: int = 10
) -> list[dict[str, Any]]:
    """Return matching chunks ordered by PostgreSQL full-text relevance."""
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")
    if not query_text.strip():
        return []

    result = await session.execute(
        text(
            """
            SELECT id AS chunk_id, document_id, chunk_index, content,
                   ts_rank_cd(fts_vector, websearch_to_tsquery('simple', :query)) AS score
            FROM chunks
            WHERE fts_vector @@ websearch_to_tsquery('simple', :query)
            ORDER BY score DESC, id ASC
            LIMIT :top_k
            """
        ),
        {"query": query_text, "top_k": top_k},
    )
    return [dict(row) for row in result.mappings().all()]
