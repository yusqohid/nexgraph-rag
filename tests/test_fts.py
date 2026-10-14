"""Full-text retrieval against PostgreSQL; all fixture changes roll back."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.retrieval.vector_search import search_fts_chunks

MIGRATION = (
    Path(__file__).resolve().parents[1] / "app/db/migrations/001_init.sql"
).read_text(encoding="utf-8")


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                for statement in MIGRATION.split(";"):
                    if statement.strip():
                        await connection.execute(text(statement))
                # Rollback restores preexisting data as well as removing test rows.
                await connection.execute(text("TRUNCATE TABLE documents CASCADE"))
                async with AsyncSession(bind=connection) as db_session:
                    yield db_session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def insert_chunks(session: AsyncSession, contents: list[str]) -> list[UUID]:
    document_id = uuid4()
    await session.execute(
        text("INSERT INTO documents (id, title) VALUES (:id, :title)"),
        {"id": document_id, "title": "FTS fixture"},
    )
    ids = [uuid4() for _ in contents]
    await session.execute(
        text("INSERT INTO chunks (id, document_id, chunk_index, content) "
             "VALUES (:id, :document_id, :chunk_index, :content)"),
        [
            {"id": chunk_id, "document_id": document_id, "chunk_index": index, "content": content}
            for index, (chunk_id, content) in enumerate(zip(ids, contents, strict=True))
        ],
    )
    return ids


@pytest.mark.asyncio
async def test_specific_error_code_is_ranked_first(session: AsyncSession) -> None:
    ids = await insert_chunks(session, [
        "Server melaporkan ERR-9942-Y saat startup.",
        "Server melaporkan ERR-9942-X saat startup.",
        "Server melaporkan ERR-1111-X saat startup.",
        "Laporan server tanpa kode kesalahan.",
    ])
    results = await search_fts_chunks(session, "ERR-9942-X")
    assert [row["chunk_id"] for row in results] == [ids[1]]
    assert results[0]["score"] > 0
    assert results[0]["content"] == "Server melaporkan ERR-9942-X saat startup."


@pytest.mark.asyncio
async def test_relevance_order_and_top_k(session: AsyncSession) -> None:
    ids = await insert_chunks(session, [
        "nexuskeyword", "nexuskeyword nexuskeyword nexuskeyword", "unrelated",
    ])
    results = await search_fts_chunks(session, "nexuskeyword")
    assert [row["chunk_id"] for row in results] == [ids[1], ids[0]]
    assert results[0]["score"] > results[1]["score"]
    limited = await search_fts_chunks(session, "nexuskeyword", top_k=1)
    assert [row["chunk_id"] for row in limited] == [ids[1]]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   ", "zzmissingwordzz", "!!!"])
async def test_empty_or_unmatched_query_returns_no_chunks(session: AsyncSession, query: str) -> None:
    await insert_chunks(session, ["Dokumen tentang proyek Alpha."])
    assert await search_fts_chunks(session, query) == []


@pytest.mark.asyncio
async def test_query_is_bound_as_data(session: AsyncSession) -> None:
    await insert_chunks(session, ["Dokumen tentang proyek Alpha."])
    assert await search_fts_chunks(session, "'; DROP TABLE chunks; --") == []
    assert (await session.execute(text("SELECT count(*) FROM chunks"))).scalar_one() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("top_k", [0, -1])
async def test_invalid_limit_is_rejected(session: AsyncSession, top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k"):
        await search_fts_chunks(session, "Alpha", top_k=top_k)
