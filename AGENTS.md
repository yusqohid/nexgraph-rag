# AGENTS.md — Pedoman Operasi Coding Agent (NexusGraph RAG)

Dokumen ini berisi aturan teknis, konvensi arsitektur, dan perintah standar yang **WAJIB** dipatuhi oleh setiap AI Coding Agent yang bekerja di repositori ini.

---

## 1. Sumber Kebenaran (Source of Truth)
Sebelum menulis atau memodifikasi kode apa pun, agen harus memeriksa tiga dokumen referensi berikut secara berurutan:
1. **`PRD.md`**: Memahami batasan fitur, target latensi, dan format sitasi.
2. **`ARCHITECTURE.md`**: Mematuhi struktur direktori, skema DDL PostgreSQL, kontrak Pydantic, dan kueri SQL `WITH RECURSIVE`.
3. **`TASKS.md`**: Mengerjakan *atomic task* sesuai urutan. Jangan melompat ke task berikutnya sebelum *Verification Command (DoD)* pada task aktif lulus 100%.

---

## 2. Perintah Standar & Toolchain (Environment Commands)
Proyek ini menggunakan **`uv`** sebagai *package & runtime manager* tunggal. **DILARANG** menggunakan `pip install`, `poetry`, atau memanggil `python` / `pytest` secara langsung di luar `uv run`.

* **Menambah dependensi produksi:**
  ```bash
  uv add <nama-paket>
  ```
* **Menambah dependensi development/testing:**
  ```bash
  uv add --dev <nama-paket>
  ```
* **Menjalankan infrastruktur lokal (PostgreSQL `pgvector` + Redis):**
  ```bash
  docker compose up -d
  ```
* **Menjalankan server FastAPI (Development):**
  ```bash
  uv run uvicorn app.main:app --reload --port 8000
  ```
* **Menjalankan seluruh rangkaian test:**
  ```bash
  uv run pytest -v
  ```
* **Menjalankan satu file test spesifik:**
  ```bash
  uv run pytest tests/<nama_file>.py -v
  ```

---

## 3. Aturan & Standar Penulisan Kode (Coding Standards)

### A. Full Async I/O (Non-Blocking)
* Seluruh *route handler* FastAPI, pemanggilan database (`asyncpg` / `SQLAlchemy AsyncSession`), koneksi Redis, dan pemanggilan API LLM/Embedding **WAJIB** menggunakan `async def` dan `await`.
* **DILARANG** memanggil *library* sinkron yang memblokir *event loop* (seperti `requests`, `time.sleep`, atau `psycopg2` standar) di dalam alur async. Gunakan `httpx.AsyncClient` dan `asyncio.sleep`.
* Batasi konkurensi pemanggilan API LLM paralel menggunakan `asyncio.Semaphore(5)` untuk mencegah `RateLimitError (HTTP 429)`.

### B. Interaksi Database & Kueri Vektor/Graf
* Jangan menulis ORM abstrak yang berbelit-belit untuk operasi vektor dan graf. Gunakan **`sqlalchemy.text()`** dengan *bound parameters* (`:param_name`) untuk mengeksekusi kueri:
  * Jarak kosinus `pgvector`: `embedding <=> CAST(:query_vec AS vector)`
  * Pencarian Full-Text Search: `ts_rank_cd(fts_vector, websearch_to_tsquery('simple', :query))`
  * Kemiripan Trigram: `similarity(canonical_name, :name)`
  * Penelusuran Graf 2-Hop: `WITH RECURSIVE subgraph AS (...)`
* **Keamanan SQL:** Selalu gunakan *parameter binding*. **DILARANG KERAS** menggabungkan input pengguna ke dalam string SQL menggunakan *f-string* (`f"SELECT ... {user_input}"`).

### C. Pemanggilan LLM & Structured Outputs
* Jangan pernah melakukan *parsing* output LLM menggunakan *regex* manual atau `json.loads()` mentah tanpa skema.
* Selalu paksa output LLM mengikuti kontrak `pydantic.BaseModel` yang didefinisikan di `app/models/schemas.py` menggunakan fitur *Structured Outputs* bawaan SDK (`response_format`).
* Setiap *prompt* ekstraksi graf wajib menyertakan instruksi eksplisit:
  1. Dilarang mengekstrak kata ganti (*"ia"*, *"mereka"*, *"perusahaan tersebut"*) sebagai nama entitas; resolusikan ke nama kanonisnya.
  2. Gunakan format `UPPER_SNAKE_CASE` untuk tipe relasi (`relation_type`).

### D. Tipe Data & Validasi (Type Hints)
* Gunakan sintaks *type hinting* Python 3.12+ modern: gunakan `list[str]`, `dict[str, Any]`, dan `str | None` (bukan `List`, `Dict`, atau `Optional` dari modul `typing` lama).
* Gunakan `pydantic` v2 API (`model_validate`, `model_dump`, `ConfigDict` — **jangan** gunakan method v1 yang sudah *deprecated* seperti `.dict()`, `.parse_obj()`, atau `class Config:`).

---

## 4. Pedoman Pengujian (Testing & Mocking Guidelines)
Saat menulis atau menjalankan unit test di direktori `tests/`:
1. **Isolasi Database:** Setiap test yang menyentuh PostgreSQL harus membersihkan datanya kembali (menggunakan *transaction rollback fixture* atau `TRUNCATE TABLE documents, entities CASCADE`) agar test bersifat idempoten dan bisa dijalankan berulang kali.
2. **Efisiensi API LLM pada Unit Test:**
   * Untuk menguji logika algoritma internal (seperti `test_parser.py`, `test_reranker.py`, `test_resolver.py`, dan `WITH RECURSIVE` di `test_graph_rag.py`), gunakan *fixture* vektor deterministik atau *mock* respons LLM agar pengujian berjalan cepat (kurang dari 2 detik) dan tidak menghabiskan kuota token.
   * Pengujian integrasi penuh ke API LLM asli dilakukan pada `test_extractor.py` dan skrip evaluasi `eval/evaluate.py`.

---

## 5. Protokol Kerja Agent (Workflow Loop)
Untuk setiap task di `TASKS.md`, ikuti siklus 5 langkah ini secara disiplin:
1. **Branch:** Buat branch fitur terpisah dari `main` terbaru (`git checkout -b feat/task-X-Y-<slug>`) sebelum menulis kode apa pun. *Satu task = satu branch = satu Pull Request.* **DILARANG** commit langsung ke `main`.
2. **Plan:** Baca spesifikasi task di `TASKS.md` dan cek file terkait yang sudah ada di repositori.
3. **Implement:** Buat atau perbarui file sesuai daftar *Target File* pada task tersebut. Jaga agar kode tetap modular, bersih, dan tidak memuat *dead code*.
4. **Verify:** Jalankan *Verification Command (DoD)* yang tertulis di `TASKS.md`. Jika terjadi error atau *test failure*, baca *traceback*-nya, perbaiki akar masalahnya, dan jalankan ulang verifikasi.
5. **Pull Request:** Setelah verifikasi lulus tanpa error, ubah status task terkait di `TASKS.md` dari `- [ ]` menjadi `- [x]`, push branch (`git push -u origin <branch>`), lalu buka Pull Request ke `main` dengan ringkasan perubahan + bukti DoD. Berhenti dan tunggu review/merge pemilik repo sebelum mengerjakan task berikutnya.

### Konvensi Branch & PR
* Format branch: `feat/task-<fase>.<nomor>-<slug-singkat>` (contoh: `feat/task-1-3-chunker-embedder`).
* Judul PR: `[Task X.Y] <Judul task sesuai TASKS.md>`.
* Deskripsi PR wajib memuat: daftar file yang diubah, *Verification Command (DoD)* yang dijalankan beserta hasilnya, dan catatan review yang relevan bagi pemilik repo.

---

## 6. Larangan Keras (Anti-Patterns / Do Not Do)
* **JANGAN** menambahkan database eksternal baru (seperti Neo4j, Qdrant, atau Milvus) di luar PostgreSQL + Redis yang sudah ditetapkan di `ARCHITECTURE.md`.
* **JANGAN** mengubah dimensi kolom `vector(1536)` di database tanpa menyelaraskannya dengan `EMBEDDING_DIM` di `app/config.py`.
* **JANGAN** menyimpan kredensial atau API key secara *hardcoded* di dalam kode sumber; selalu baca melalui objek `settings` dari `app/config.py`.
* **JANGAN** menelan *exception* secara diam-diam (`except Exception: pass`). Gunakan modul `logging` standar untuk mencatat *error* beserta konteks `document_id` atau `chunk_id`-nya.
