-- NexusGraph RAG Engine: Initial schema (idempotent)
-- Task 1.2 — DDL source: ARCHITECTURE.md Section 4

-- Ekstensi wajib
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Tabel Dokumen Sumber
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source_path TEXT,
    status VARCHAR(32) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabel Chunks (Menyimpan Teks, Vektor, dan Full-Text Index)
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    fts_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING gin (fts_vector);

-- 3. Tabel Graph Nodes (Entitas)
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    embedding vector(1536),
    UNIQUE (canonical_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entities_embedding ON entities USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm ON entities USING gin (canonical_name gin_trgm_ops);

-- 4. Tabel Graph Edges (Relasi Antar-Entitas)
CREATE TABLE IF NOT EXISTS entity_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(128) NOT NULL,
    evidence_text TEXT NOT NULL,
    source_chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    weight FLOAT DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON entity_relations(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON entity_relations(target_entity_id);
