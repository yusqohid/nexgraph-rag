"""Task 1.2 — verify async connection and the four tables exist."""

import pytest
from sqlalchemy import text

from app.db.session import engine, init_db

EXPECTED_TABLES = {"documents", "chunks", "entities", "entity_relations"}


@pytest.mark.asyncio
async def test_init_db_creates_expected_tables() -> None:
    await init_db()
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(:tables)"
            ),
            {"tables": list(EXPECTED_TABLES)},
        )
        found = {row[0] for row in result.all()}
    assert found == EXPECTED_TABLES
