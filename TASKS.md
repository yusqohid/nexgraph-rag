# Agent Execution Backlog: NexusGraph RAG Engine (`TASKS.md`)

> **Instruksi untuk Coding Agent:**
> 1. Baca `PRD.md`, `ARCHITECTURE.md`, dan `AGENTS.md` terlebih dahulu sebelum memulai task apa pun.
> 2. Kerjakan task secara berurutan (satu per satu). Jangan melompat ke task berikutnya sebelum **Verification Command (DoD)** pada task saat ini berhasil dijalankan tanpa error.
> 3. Gunakan `uv` untuk manajemen paket dan eksekusi skrip Python (`uv run ...`).
> 4. Perbarui kotak centang `[ ]` menjadi `[x]` di file ini setiap kali satu task selesai diverifikasi.

---

## Ringkasan Progres

### Fase 1: Baseline Vector RAG
- [x] **Task 1.1:** Inisialisasi Proyek Python (`uv`) & Docker Compose (`pgvector` + Redis)
- [x] **Task 1.2:** Setup Koneksi Async Database & Migrasi Skema DDL (Tabel + Indeks)
- [x] **Task 1.3:** Implementasi Hierarchical Text Chunker & Wrapper Embedding API
- [ ] **Task 1.4:** Buat Endpoint `POST /ingest` & Pencarian Baseline Vector RAG

### Fase 2: Hybrid Search & Reranking
- [ ] **Task 2.1:** Implementasi Pencarian Leksikal (PostgreSQL Full-Text Search)
- [ ] **Task 2.2:** Implementasi Algoritma Reciprocal Rank Fusion (RRF) & Cross-Encoder Reranker

### Fase 3: Knowledge Graph Layer (Inti GraphRAG)
- [ ] **Task 3.1:** Buat Skema Pydantic & Modul LLM Extractor untuk Triplet Graf `(S, P, O)`
- [ ] **Task 3.2:** Implementasi Entity Resolution (Deduplikasi Trigram + Cosine Similarity)
- [ ] **Task 3.3:** Integrasi Background Worker (`ARQ`/`Taskiq`) untuk Pipeline Ekstraksi Graf
- [ ] **Task 3.4:** Implementasi 2-Hop Graph Traversal (SQL `WITH RECURSIVE`) & Sintesis Konteks

### Fase 4: Evaluasi & Production Hardening
- [ ] **Task 4.1:** Implementasi Adaptive Query Router & Redis Semantic Cache
- [ ] **Task 4.2:** Buat Golden Dataset Multi-Hop & Skrip Evaluasi Kuantitatif (Ragas)

---

## Spesifikasi Detail Eksekusi per Task

### FASE 1: Baseline Vector RAG

#### Task 1.1 — Inisialisasi Proyek & Infrastruktur Lokal
* **Tujuan:** Menyiapkan struktur direktori proyek, manajemen dependensi dengan `uv`, serta layanan kontainer PostgreSQL (`pgvector/pgvector:pg16`) dan Redis.
* **Target File:**
  * `pyproject.toml`
  * `docker-compose.yml`
  * `.env.example`
  * `app/__init__.py`
  * `app/config.py`
* **Langkah Implementasi:**
  1. Inisialisasi proyek Python 3.12+ dengan `uv` dan tambahkan dependensi utama: `fastapi`, `uvicorn[standard]`, `asyncpg`, `sqlalchemy[asyncio]`, `pgvector`, `pydantic`, `pydantic-settings`, `openai` (atau `google-genai`), `httpx`, `arq`, serta dev-dependencies: `pytest`, `pytest-asyncio`.
  2. Buat `docker-compose.yml` dengan dua service:
     * `db`: Image `pgvector/pgvector:pg16`, port `5432:5432`, environment `POSTGRES_USER=nexus`, `POSTGRES_PASSWORD=nexus_pass`, `POSTGRES_DB=nexus_graphrag`, lengkapi dengan `healthcheck` (`pg_isready`).
     * `redis`: Image `redis:7-alpine`, port `6379:6379`, lengkapi dengan `healthcheck` (`redis-cli ping`).
  3. Buat `app/config.py` menggunakan `pydantic_settings.BaseSettings` untuk memuat `DATABASE_URL`, `REDIS_URL`, `LLM_API_KEY`, `EMBEDDING_MODEL`, dan `EMBEDDING_DIM`.
* **Verification Command (DoD):**
  ```bash
  docker compose up -d && docker compose ps
  uv run python -c "from app.config import settings; print(settings.DATABASE_URL)"
  ```

---

#### Task 1.2 — Koneksi Database Async & Eksekusi DDL
* **Tujuan:** Membuat *async connection pool* dan mengeksekusi skema tabel `documents`, `chunks`, `entities`, dan `entity_relations` beserta indeks HNSW dan GIN.
* **Target File:**
  * `app/db/migrations/001_init.sql`
  * `app/db/session.py`
  * `app/models/domain.py`
  * `tests/test_db.py`
* **Langkah Implementasi:**
  1. Salin skema DDL SQL dari `ARCHITECTURE.md` ke `app/db/migrations/001_init.sql` (pastikan ekstensi `vector` dan `pg_trgm` diaktifkan di baris paling atas).
  2. Buat `app/db/session.py` menggunakan `create_async_engine` dan `async_sessionmaker` dari SQLAlchemy (driver `postgresql+asyncpg://`).
  3. Buat fungsi utilitas `init_db()` di `app/db/session.py` untuk mengeksekusi `001_init.sql` secara idempoten.
  4. Buat `tests/test_db.py` yang menguji koneksi dan memeriksa keberadaan keempat tabel di `information_schema.tables`.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_db.py -v
  ```

---

#### Task 1.3 — Modul Text Chunker & Embedding Service
* **Tujuan:** Memecah dokumen panjang menjadi potongan teks dengan *overlap* yang rapi dan mengubahnya menjadi vektor *float*.
* **Target File:**
  * `app/ingestion/parser.py`
  * `app/ingestion/embedder.py`
  * `tests/test_parser.py`
* **Langkah Implementasi:**
  1. Di `app/ingestion/parser.py`, buat fungsi `chunk_document(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]` yang memotong teks berdasarkan batas paragraf (`\n\n`) atau kalimat (`. `) terdekat agar tidak memutus kata di tengah.
  2. Di `app/ingestion/embedder.py`, buat fungsi async `get_embeddings(texts: list[str]) -> list[list[float]]` yang memanggil API model embedding secara *batch* dan mengembalikan daftar vektor dengan dimensi sesuai `settings.EMBEDDING_DIM`.
  3. Tulis unit test di `tests/test_parser.py` untuk menguji ukuran chunk, overlap, dan penanganan teks kosong.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_parser.py -v
  ```

---

#### Task 1.4 — Endpoint Ingestion & Baseline Vector Retrieval
* **Tujuan:** Menyelesaikan siklus hidup RAG standar (simpan dokumen -> cari via vektor -> jawab dengan sitasi).
* **Target File:**
  * `app/retrieval/vector_search.py`
  * `app/retrieval/synthesizer.py`
  * `app/api/routes.py`
  * `app/main.py`
* **Langkah Implementasi:**
  1. Di `app/retrieval/vector_search.py`, buat fungsi `search_similar_chunks(session, query_vec: list[float], top_k: int = 5)` menggunakan operator jarak kosinus `<=>` di PostgreSQL.
  2. Di `app/retrieval/synthesizer.py`, buat fungsi `synthesize_answer(query: str, contexts: list[dict]) -> dict` yang menginstruksikan LLM menjawab **hanya** berdasarkan konteks yang diberikan dan wajib menyertakan sitasi `[chunk_id]`.
  3. Di `app/api/routes.py`, buat endpoint:
     * `POST /ingest`: Menerima `{ "title": str, "content": str }`, memotong menjadi *chunks*, mengambil *embeddings*, dan menyimpan ke tabel `documents` & `chunks`.
     * `POST /query`: Menerima `{ "query": str, "mode": "vector" }`, menjalankan `search_similar_chunks`, dan mengembalikan jawaban dari `synthesize_answer`.
* **Verification Command (DoD):**
  ```bash
  uv run uvicorn app.main:app --port 8000 &
  curl -X POST http://localhost:8000/ingest -H "Content-Type: application/json" -d '{"title": "Doc A", "content": "Proyek Alpha dipimpin oleh Budi Santoso sejak Januari 2026."}'
  curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "Siapa pemimpin Proyek Alpha?", "mode": "vector"}'
  ```

---

### FASE 2: Hybrid Search & Reranking

#### Task 2.1 — Pencarian Leksikal (Full-Text Search PostgreSQL)
* **Tujuan:** Menambahkan kemampuan pencarian kata kunci eksak menggunakan kolom `fts_vector` (`tsvector`).
* **Target File:**
  * `app/retrieval/vector_search.py`
  * `tests/test_fts.py`
* **Langkah Implementasi:**
  1. Tambahkan fungsi async `search_fts_chunks(session, query_text: str, top_k: int = 10)` di `app/retrieval/vector_search.py`.
  2. Gunakan kueri SQL `websearch_to_tsquery('simple', :query)` dan urutkan berdasarkan skor `ts_rank_cd(fts_vector, websearch_to_tsquery('simple', :query)) DESC`.
  3. Buat pengujian di `tests/test_fts.py` yang memastikan pencarian kode spesifik (misal `"ERR-9942-X"`) selalu menempatkan *chunk* yang tepat di peringkat pertama.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_fts.py -v
  ```

---

#### Task 2.2 — Penggabungan RRF & Cross-Encoder Reranker
* **Tujuan:** Menggabungkan hasil Vector Search + Full-Text Search menggunakan rumus *Reciprocal Rank Fusion* (RRF), lalu menyaring ulang dengan *Cross-Encoder*.
* **Target File:**
  * `app/retrieval/reranker.py`
  * `app/api/routes.py`
  * `tests/test_reranker.py`
* **Langkah Implementasi:**
  1. Di `app/retrieval/reranker.py`, buat fungsi murni `reciprocal_rank_fusion(vector_chunks: list, fts_chunks: list, k: int = 60) -> list` yang menghitung skor gabungan:
     `score(c) = 1 / (k + rank_vec(c)) + 1 / (k + rank_fts(c))`
  2. Tambahkan fungsi `rerank_contexts(query: str, candidates: list, top_n: int = 5)` untuk mengurutkan ulang hasil RRF.
  3. Hubungkan logika ini ke endpoint `POST /query` saat `mode="hybrid"` dipilih.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_reranker.py -v
  ```

---

### FASE 3: Knowledge Graph Layer (Inti GraphRAG)

#### Task 3.1 — Ekstraktor Triplet Graf Berbasis Skema Pydantic
* **Tujuan:** Mengubah satu *chunk* teks menjadi struktur JSON ketat berisi daftar `ExtractedEntity` dan `ExtractedRelation`.
* **Target File:**
  * `app/models/schemas.py`
  * `app/ingestion/extractor.py`
  * `tests/test_extractor.py`
* **Langkah Implementasi:**
  1. Salin definisi skema Pydantic `ExtractedEntity`, `ExtractedRelation`, dan `ChunkGraphExtraction` dari `ARCHITECTURE.md` ke `app/models/schemas.py`.
  2. Di `app/ingestion/extractor.py`, buat fungsi async `extract_graph_from_chunk(chunk_text: str) -> ChunkGraphExtraction` yang memanggil LLM dengan *structured output* ketat dan *system prompt* yang melarang ekstraksi kata ganti (*pronouns*).
  3. Buat pengujian di `tests/test_extractor.py` untuk memastikan kalimat *"Budi memimpin Proyek Alpha yang menggunakan database PostgreSQL"* menghasilkan minimal 3 entitas dan 2 relasi valid.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_extractor.py -v
  ```

---

#### Task 3.2 — Modul Entity Resolution (Deduplikasi Node)
* **Tujuan:** Mencegah duplikasi node untuk entitas yang sama (misal `"PT Telkom"` dan `"Telkom"`) saat dimasukkan ke database.
* **Target File:**
  * `app/ingestion/resolver.py`
  * `tests/test_resolver.py`
* **Langkah Implementasi:**
  1. Di `app/ingestion/resolver.py`, buat fungsi `resolve_and_upsert_entity(session, entity: ExtractedEntity, embedding: list[float]) -> UUID`.
  2. Sebelum `INSERT`, jalankan kueri SQL pada tabel `entities` dengan `entity_type` yang sama di mana `similarity(canonical_name, :name) > 0.85` **ATAU** `(1 - (embedding <=> :vec)) > 0.90`.
  3. Jika kandidat ditemukan, gunakan `id` entitas yang sudah ada dan gabungkan deskripsinya jika informasi baru lebih lengkap. Jika tidak ada, lakukan `INSERT` baru dan kembalikan `id`-nya.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_resolver.py -v
  ```

---

#### Task 3.3 — Background Worker untuk Asynchronous Graph Ingestion
* **Tujuan:** Memindahkan proses ekstraksi graf ke *background worker* agar endpoint `POST /ingest` tetap cepat dan non-blocking.
* **Target File:**
  * `app/ingestion/worker.py`
  * `app/api/routes.py`
* **Langkah Implementasi:**
  1. Di `app/ingestion/worker.py`, buat fungsi tugas latar belakang `process_document_graph(document_id: UUID)`:
     * Ubah status dokumen menjadi `PROCESSING`.
     * Ambil seluruh `chunks` milik `document_id`.
     * Jalankan `extract_graph_from_chunk` secara konkuren dengan pembatas `asyncio.Semaphore(5)`.
     * Simpan setiap entitas melalui `resolve_and_upsert_entity` dan simpan relasinya ke tabel `entity_relations` (sertakan `source_chunk_id`).
     * Ubah status dokumen menjadi `COMPLETED` (atau `FAILED` jika terjadi error fatal).
  2. Panggil tugas latar belakang ini dari endpoint `POST /ingest`. Tambahkan endpoint `GET /documents/{id}/status` untuk memantau progres.
* **Verification Command (DoD):**
  ```bash
  curl -X POST http://localhost:8000/ingest -H "Content-Type: application/json" -d '{"title": "Doc B", "content": "Budi Santoso sedang diperiksa terkait pelanggaran kepatuhan pada Vendor X."}'
  ```

---

#### Task 3.4 — Penelusuran Graf 2-Hop (`WITH RECURSIVE`) & Sintesis Multi-Hop
* **Tujuan:** Mengambil jalur relasi hingga 2 *hop* dari entitas yang ditanyakan pengguna dan menggabungkannya dengan konteks teks.
* **Target File:**
  * `app/retrieval/graph_traversal.py`
  * `app/retrieval/synthesizer.py`
  * `app/api/routes.py`
  * `tests/test_graph_rag.py`
* **Langkah Implementasi:**
  1. Di `app/retrieval/graph_traversal.py`, buat fungsi `traverse_subgraph(session, query_vec: list[float], max_hops: int = 2)`:
     * Cari Top-5 entitas awal (`V_0`) di tabel `entities` menggunakan kemiripan vektor `embedding <=> :query_vec`.
     * Jalankan kueri SQL `WITH RECURSIVE subgraph AS (...)` sesuai spesifikasi `ARCHITECTURE.md` untuk menarik jalur relasi hingga 2 *hop* beserta nama entitas asal/tujuan dan `source_chunk_id`.
  2. Format hasil *subgraph* menjadi daftar fakta relasional:
     `[Entitas A] --(RELASI)--> [Entitas B] | Bukti: "..." (Sumber: [chunk_id])`
  3. Pada endpoint `POST /query` dengan `mode="graph"`, gabungkan konteks *subgraph* ini dengan hasil *Hybrid Search*, lalu kirim ke `synthesize_answer`.
* **Verification Command (DoD):**
  ```bash
  uv run pytest tests/test_graph_rag.py -v
  ```

---

### FASE 4: Evaluasi & Production Hardening

#### Task 4.1 — Adaptive Query Router & Redis Semantic Cache
* **Tujuan:** Menghemat biaya dan latensi dengan menyimpan jawaban di Redis serta mengarahkan pertanyaan sederhana ke jalur `hybrid` dan pertanyaan relasional ke jalur `graph`.
* **Target File:**
  * `app/retrieval/router.py`
  * `app/retrieval/cache.py`
  * `app/api/routes.py`
* **Langkah Implementasi:**
  1. Di `app/retrieval/cache.py`, simpan dan periksa cache kueri di Redis sebelum menjalankan pipeline retrieval.
  2. Di `app/retrieval/router.py`, buat fungsi `route_query(query: str) -> Literal["hybrid", "graph"]` yang menganalisis apakah kueri membutuhkan penalaran hubungan lintas entitas. Gunakan router ini jika pengguna mengirim `mode="auto"`.
* **Verification Command (DoD):**
  ```bash
  curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "Apakah Proyek Alpha memiliki risiko kepatuhan?", "mode": "auto"}'
  ```

---

#### Task 4.2 — Benchmark Otomatis Vector RAG vs GraphRAG
* **Tujuan:** Membuktikan secara kuantitatif peningkatan akurasi GraphRAG dibandingkan Vector RAG biasa menggunakan 20 soal pengujian terstruktur sesuai spesifikasi `PRD.md`.
* **Target File:**
  * `eval/golden_dataset.json`
  * `eval/evaluate.py`
* **Langkah Implementasi:**
  1. Buat `eval/golden_dataset.json` berisi korpus dokumen uji yang saling terhubung dan **20 pertanyaan evaluasi** yang terdiri dari:
     * **10 pertanyaan `single_hop`** (fakta langsung/kata kunci eksak dalam satu dokumen).
     * **10 pertanyaan `multi_hop`** (membutuhkan penyambungan relasi entitas lintas minimal 2 dokumen berbeda).
     * Setiap item wajib menyertakan `question`, `query_type` (`single_hop` | `multi_hop`), `ground_truth_answer`, dan `expected_chunk_ids`.
  2. Buat skrip `eval/evaluate.py` yang menjalankan kueri untuk ke-20 soal tersebut menggunakan tiga mode (`vector`, `hybrid`, `graph`), menghitung metrik **Context Recall**, **Faithfulness**, serta rata-rata latensi (ms) yang dikelompokkan berdasarkan `query_type`, lalu mencetak tabel laporan perbandingan dalam format Markdown di terminal.
* **Verification Command (DoD):**
  ```bash
  uv run python -c "import json; data = json.load(open('eval/golden_dataset.json')); assert len(data['questions']) == 20"
  uv run python eval/evaluate.py
  ```
