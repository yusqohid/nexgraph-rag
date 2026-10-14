"""Domain table contracts mirroring 001_init.sql (Task 1.2).

Read-path queries use ``sqlalchemy.text()`` with bound parameters per AGENTS.md.
These dataclasses document column shapes for ingestion/retrieval code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Document:
    id: UUID
    title: str
    source_path: str | None
    status: str
    created_at: datetime


@dataclass(frozen=True)
class Chunk:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float] | None


@dataclass(frozen=True)
class Entity:
    id: UUID
    canonical_name: str
    entity_type: str
    description: str
    embedding: list[float] | None


@dataclass(frozen=True)
class EntityRelation:
    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    evidence_text: str
    source_chunk_id: UUID
    weight: float
