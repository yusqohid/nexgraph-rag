# System Architecture: NexusGraph RAG Engine

## 1. Filosofi Desain: Unified PostgreSQL Architecture
Alih-alih mengelola tiga infrastruktur database terpisah (Relational DB + Vector DB + Graph DB) yang meningkatkan kompleksitas operasional dan risiko inkonsistensi data, arsitektur ini menggunakan **PostgreSQL** sebagai fondasi terpadu:
* **Relational & Document Store:** Menyimpan metadata dokumen dan potongan teks (*chunks*).
* **Vector & Lexical Store:** Menggunakan ekstensi `pgvector` (HNSW Index) untuk pencarian semantik dan `tsvector` (GIN Index) untuk pencarian kata kunci eksak (BM25-style).
* **Property Graph Store:** Merepresentasikan *Knowledge Graph* melalui tabel `entities` (Nodes) dan `entity_relations` (Directed Edges) yang ditelusuri menggunakan kueri rekursif SQL (`WITH RECURSIVE`) atau ekstensi `Apache AGE`.

---

## 2. Tech Stack & Komponen
* **Bahasa & Runtime:** Python 3.12+ (dikelola dengan `uv`)
* **Web Framework:** FastAPI (Async REST API)
* **Validasi Data & LLM Structured Output:** Pydantic v2 + Instructor / Native JSON Schema
* **Database Utama:** PostgreSQL 16+ dengan ekstensi `pgvector` dan `pg_trgm`
* **Task Queue & Cache:** Redis + ARQ / Taskiq (Async Background Worker)
* **Reranker:** `sentence-transformers` (`BAAI/bge-reranker-v2-m3` atau API setara)
* **Evaluasi:** Ragas + Pytest

---

## 3. Struktur Direktori Proyek

```text
nexus-graphrag/
├── app/
│   ├── main.py                 # Entrypoint FastAPI
│   ├── config.py               # Konfigurasi environment (Pydantic Settings)
│   ├── db/
│   │   ├── session.py          # Koneksi asyncpg / SQLAlchemy Async
│   │   └── migrations/         # Skrip SQL inisialisasi tabel & indeks
│   ├── models/
│   │   ├── domain.py           # Skema tabel database
│   │   └── schemas.py          # Kontrak Pydantic untuk API & Output LLM
│   ├── ingestion/
│   │   ├── parser.py           # Pemotong dokumen (Chunker)
│   │   ├── embedder.py         # Wrapper API Embedding
│   │   ├── extractor.py        # Prompt & logika ekstraksi Triplet (S, P, O)
│   │   ├── resolver.py         # Logika deduplikasi entitas (Entity Resolution)
│   │   └── worker.py           # Background worker antrean dokumen
│   ├── retrieval/
│   │   ├── vector_search.py    # Pencarian pgvector + Full-Text Search (RRF)
│   │   ├── graph_traversal.py  # Penelusuran N-hop pada tabel entities/relations
│   │   ├── reranker.py         # Cross-encoder filtering
│   │   ├── router.py           # Adaptive Query Router
│   │   ├── cache.py            # Redis Semantic Cache
│   │   └── synthesizer.py      # Perakitan prompt akhir & pemanggilan LLM
│   └── api/
│       └── routes.py           # Endpoint /ingest, /query, /graph-inspect
├── tests/                      # Unit & Integration Tests
├── eval/
│   ├── golden_dataset.json     # Kumpulan soal multi-hop & kunci jawaban
│   └── evaluate.py             # Skrip benchmark Vector RAG vs GraphRAG
├── docker-compose.yml          # PostgreSQL (pgvector) + Redis
└── pyproject.toml
```

---

## 4. Desain Skema Database (DDL)

```sql
-- Ekstensi wajib
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Tabel Dokumen Sumber
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source_path TEXT,
    status VARCHAR(32) DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
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
```

---

## 5. Kontrak Data Ekstraksi LLM (Write Path)

```python
from pydantic import BaseModel, Field
from typing import Literal

EntityType = Literal["PERSON", "ORGANIZATION", "PROJECT", "TECHNOLOGY", "RISK", "CONCEPT"]

class ExtractedEntity(BaseModel):
    name: str = Field(description="Nama entitas yang dinormalisasi, hindari kata ganti.")
    entity_type: EntityType
    description: str = Field(description="Penjelasan singkat peran entitas di dalam teks ini.")

class ExtractedRelation(BaseModel):
    source_entity: str = Field(description="Nama entitas asal, harus ada di daftar entities.")
    target_entity: str = Field(description="Nama entitas tujuan, harus ada di daftar entities.")
    relation_type: str = Field(description="Kata kerja aktif UPPER_SNAKE_CASE, misal: MANAGES, USES, DELAYS.")
    evidence: str = Field(description="Kutipan singkat atau penjelasan mengapa kedua entitas ini berhubungan.")

class ChunkGraphExtraction(BaseModel):
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]
```

### Algoritma Entity Resolution (Deduplikasi saat Insert):
Ketika entitas baru `E_new` akan disimpan ke tabel `entities`:
1. Cari di tabel `entities` dengan `entity_type` yang sama di mana kemiripan trigram nama `similarity(canonical_name, E_new.name) > 0.85` **ATAU** jarak kosinus vektor deskripsi `(1 - (embedding <=> E_new.embedding)) > 0.90`.
2. Jika ditemukan kandidat yang cocok, gunakan `id` entitas lama dan gabungkan deskripsinya. Jika tidak ada, buat baris `entities` baru.

---

## 6. Algoritma Hybrid & Graph Retrieval (Read Path)

### Langkah 1: Pencarian Entry-Point Nodes
1. Ubah pertanyaan pengguna menjadi vektor `q_vec`.
2. Cari Top-5 entitas di tabel `entities` yang paling mirip secara semantik dengan `q_vec`. Ini adalah himpunan node awal `V_0`.

### Langkah 2: 2-Hop Breadth-First Traversal via SQL

```sql
WITH RECURSIVE subgraph AS (
    -- Hop 1: Relasi langsung dari/ke Entry-Point Nodes
    SELECT 
        r.source_entity_id,
        r.target_entity_id,
        r.relation_type,
        r.evidence_text,
        r.source_chunk_id,
        1 AS hop_depth
    FROM entity_relations r
    WHERE r.source_entity_id = ANY(:entry_node_ids)
       OR r.target_entity_id = ANY(:entry_node_ids)

    UNION

    -- Hop 2: Relasi dari tetangga yang ditemukan di Hop 1
    SELECT 
        r.source_entity_id,
        r.target_entity_id,
        r.relation_type,
        r.evidence_text,
        r.source_chunk_id,
        sg.hop_depth + 1
    FROM entity_relations r
    INNER JOIN subgraph sg 
        ON r.source_entity_id = sg.target_entity_id 
        OR r.target_entity_id = sg.source_entity_id
    WHERE sg.hop_depth < 2
)
SELECT DISTINCT * FROM subgraph LIMIT 50;
```

### Langkah 3: Penggabungan Konteks (Reciprocal Rank Fusion)
1. **Bukti Teks Langsung:** Top-10 `chunks` dari gabungan pencarian vektor + Full-Text Search menggunakan rumus RRF:
   `RRF_Score(c) = 1 / (60 + rank_vector(c)) + 1 / (60 + rank_fts(c))`
2. **Bukti Jalur Graf (Subgraph Context):** Daftar relasi dari hasil `WITH RECURSIVE` di atas diformat menjadi daftar fakta terstruktur beserta `chunks` asalnya (`source_chunk_id`).

### Langkah 4: Cross-Encoder Reranking & Synthesis
Seluruh kandidat teks dan fakta graf dinilai ulang terhadap kueri pengguna menggunakan *Cross-Encoder*. Top-8 konteks tertinggi dimasukkan ke dalam *System Prompt* LLM untuk menghasilkan jawaban akhir beserta sitasi `[chunk_id]`.
