"""Async database engine/session utilities (Task 1.2)."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Execute the idempotent initial DDL migration."""
    migration_path = Path(__file__).resolve().parent / "migrations" / "001_init.sql"
    sql = migration_path.read_text(encoding="utf-8")
    # asyncpg prepared statements accept only one command each,
    # so split the migration file into individual statements.
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    logger.info("Database schema initialized from %s", migration_path.name)
