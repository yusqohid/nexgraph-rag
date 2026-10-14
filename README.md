# NexusGraph RAG

Mesin RAG dengan PostgreSQL untuk pencarian vektor, teks, dan graf.

## Setup lokal

Prasyarat: Python 3.14 (sesuai `.python-version`), `uv`, Docker dan Docker Compose.

```bash
cp .env.example .env
uv sync
docker compose up -d --wait
uv run python -c "from app.config import settings; print(settings.DATABASE_URL)"
```

Isi `LLM_API_KEY` di `.env` dengan API key Google AI Studio. Aplikasi menggunakan
`google-genai` secara async, dengan `LLM_MODEL=gemini-2.5-flash` dan
`EMBEDDING_MODEL=gemini-embedding-001`. Model dapat diatur di environment;
embedding wajib menghasilkan 1536 dimensi. Kuota mengikuti project Google Anda.
Kredensial PostgreSQL dalam contoh hanya untuk pengembangan lokal.
Jika diubah, sesuaikan juga `DATABASE_URL`. Dimensi embedding dikunci ke 1536
sesuai skema database.

```bash
docker compose ps
docker compose down
```

Data PostgreSQL dan Redis disimpan dalam named volumes dan tetap tersedia setelah
`docker compose down`. Progres implementasi tercatat di `TASKS.md`.

## Baseline Vector RAG

```bash
uv run uvicorn app.main:app --port 8000
```

`POST /ingest` menerima `title` dan `content`, lalu menyimpan chunk dan embedding
dalam satu transaksi. `POST /query` menerima `query` dan `mode="vector"` serta
opsional `top_k` (1–20). Respons mencakup jawaban, sitasi `[chunk_id]`, dan konteks
retrieval. Sitasi yang tidak berasal dari konteks akan ditolak.

Jika mengganti model embedding pada database yang sudah berisi data, lakukan
embedding ulang dokumen agar vektor dokumen dan query memakai model yang sama.
