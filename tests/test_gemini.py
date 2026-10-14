"""Provider contracts tested without consuming Gemini quota."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ingestion import embedder
from app.models.schemas import GroundedAnswer
from app.retrieval import synthesizer


@pytest.mark.asyncio
async def test_embeddings_preserve_inputs_and_normalize(monkeypatch):
    first = [3.0, 4.0] + [0.0] * 1534
    second = [0.0, 2.0] + [0.0] * 1534
    call = AsyncMock(return_value=SimpleNamespace(embeddings=[
        SimpleNamespace(values=first), SimpleNamespace(values=second),
    ]))
    monkeypatch.setattr(embedder, "get_client", lambda: SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=call))
    ))
    vectors = await embedder.get_embeddings(["document A", "document B"], "RETRIEVAL_QUERY")
    assert vectors[0][:2] == [0.6, 0.8]
    assert vectors[1][:2] == [0.0, 1.0]
    config = call.call_args.kwargs["config"]
    assert config.output_dimensionality == 1536
    assert config.task_type == "RETRIEVAL_QUERY"


@pytest.mark.asyncio
async def test_embeddings_reject_missing_vectors(monkeypatch):
    call = AsyncMock(return_value=SimpleNamespace(embeddings=[]))
    monkeypatch.setattr(embedder, "get_client", lambda: SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=call))
    ))
    with pytest.raises(ValueError, match="count"):
        await embedder.get_embeddings(["document"])


@pytest.mark.asyncio
@pytest.mark.parametrize("valid", [True, False])
async def test_synthesis_enforces_source_citations(monkeypatch, valid):
    chunk_id = str(uuid4())
    cited_id = chunk_id if valid else str(uuid4())
    call = AsyncMock(return_value=SimpleNamespace(
        parsed=GroundedAnswer(answer="Budi Santoso.", citations=[cited_id])
    ))
    monkeypatch.setattr(synthesizer, "get_client", lambda: SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=call))
    ))
    contexts = [{"chunk_id": chunk_id, "content": "Budi Santoso memimpin Alpha."}]
    if valid:
        result = await synthesizer.synthesize_answer("Siapa pemimpinnya?", contexts)
        assert result["answer"].endswith(f"[{chunk_id}]")
        assert result["citations"] == [chunk_id]
    else:
        with pytest.raises(ValueError, match="citations"):
            await synthesizer.synthesize_answer("Siapa pemimpinnya?", contexts)
    assert call.call_args.kwargs["config"].response_schema is GroundedAnswer
