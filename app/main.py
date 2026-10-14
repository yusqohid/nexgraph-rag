"""NexusGraph FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.db.session import engine, init_db
from app.llm import close_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await init_db()
        yield
    finally:
        await close_client()
        await engine.dispose()


app = FastAPI(title="NexusGraph RAG Engine", lifespan=lifespan)
app.include_router(router)
