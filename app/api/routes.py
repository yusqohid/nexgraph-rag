"""REST endpoints for document ingestion and vector queries."""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.ingestion.embedder import get_embeddings
from app.ingestion.parser import chunk_document
from app.retrieval.synthesizer import synthesize_answer
from app.retrieval.vector_search import search_similar_chunks

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)


class IngestResponse(BaseModel):
    document_id: UUID
    chunk_ids: list[UUID]
    chunk_count: int
    status: Literal["PENDING"]


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["vector"] = "vector"
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    query: str
    mode: Literal["vector"]
    answer: str
    citations: list[UUID]
    contexts: list[dict[str, str | float | int | UUID]]


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    request: IngestRequest,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    chunks = chunk_document(request.content)
    if not chunks or not request.title.strip():
        raise HTTPException(status_code=422, detail="Document title and content must not be blank")

    try:
        embeddings = await get_embeddings(chunks)
        result = await session.execute(
            text(
                "INSERT INTO documents (title, status) VALUES (:title, 'PENDING') "
                "RETURNING id"
            ),
            {"title": request.title.strip()},
        )
        document_id = result.scalar_one()
        chunk_ids = [uuid4() for _ in chunks]
        await session.execute(
            text(
                """
                INSERT INTO chunks (id, document_id, chunk_index, content, embedding)
                VALUES (:id, :document_id, :chunk_index, :content, CAST(:embedding AS vector))
                """
            ),
            [
                {
                    "id": chunk_ids[index],
                    "document_id": document_id,
                    "chunk_index": index,
                    "content": chunk,
                    "embedding": str(embedding),
                }
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
            ],
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("Document ingestion failed for title %r", request.title)
        if isinstance(exc, SQLAlchemyError):
            raise HTTPException(status_code=503, detail="Document storage failed") from exc
        raise HTTPException(status_code=502, detail="Document embedding or storage failed") from exc

    return IngestResponse(
        document_id=document_id,
        chunk_ids=chunk_ids,
        chunk_count=len(chunk_ids),
        status="PENDING",
    )


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    try:
        query_embedding = (await get_embeddings([request.query], task_type="RETRIEVAL_QUERY"))[0]
        contexts = await search_similar_chunks(session, query_embedding, request.top_k)
        result = await synthesize_answer(request.query, contexts)
    except Exception as exc:
        logger.exception("Vector query failed for query %r", request.query)
        if isinstance(exc, SQLAlchemyError):
            raise HTTPException(status_code=503, detail="Vector search failed") from exc
        raise HTTPException(status_code=502, detail="Query processing failed") from exc

    return QueryResponse(
        query=request.query,
        mode=request.mode,
        answer=result["answer"],
        citations=[UUID(citation) for citation in result["citations"]],
        contexts=[
            {
                "chunk_id": context["chunk_id"],
                "content": context["content"],
                "distance": float(context["distance"]),
                "chunk_index": int(context["chunk_index"]),
            }
            for context in contexts
        ],
    )
