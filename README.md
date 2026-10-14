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

Isi `LLM_API_KEY` di `.env` sebelum menggunakan API LLM/embedding pada task
berikutnya. Kredensial PostgreSQL dalam contoh hanya untuk pengembangan lokal.
Jika diubah, sesuaikan juga `DATABASE_URL`. Dimensi embedding dikunci ke 1536
sesuai skema database.

```bash
docker compose ps
docker compose down
```

Data PostgreSQL dan Redis disimpan dalam named volumes dan tetap tersedia setelah
`docker compose down`. Progres implementasi tercatat di `TASKS.md`.
