# Local development

Two services run locally: the backend API (with Postgres/pgvector + Redis) and
the Next.js frontend.

## Make shortcuts (from the repo root)

```bash
make app-up      # build + start API, Postgres/pgvector, Redis on :8000
make app-seed    # load Warsaw places + events into the DB
make web         # start the Next.js frontend on :3000
make app-logs    # follow the API logs
make app-down    # stop the stack (data kept in the pgdata volume)
```

The manual equivalents are below.

## Backend

Full stack in containers — closest to production:

```bash
cd backend
cp .env.example .env            # ANTHROPIC_API_KEY, VOYAGE_API_KEY, APIFY_TOKEN
docker compose up -d --build    # API + Postgres/pgvector + Redis on :8000
```

Or run the API on the host against containerized datastores (hot reload):

```bash
docker compose up -d db redis
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Load some data, then smoke-test the SSE endpoint:

```bash
python -m app.ingestion.runner --source=places
curl localhost:8000/health
curl -N -X POST localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"prompt": "where to go on a cheap Saturday night"}'
```

`/search` streams Server-Sent Events: an `intent` event, then a `card` event per
ranked result, then `done`.

## Frontend

```bash
cd frontend
cp .env.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:3000
```

The backend enables CORS (`*` for local dev), so the browser on `:3000` can call
the API on `:8000`.

## Tests & lint

```bash
# backend
cd backend && .venv/bin/ruff check app/ && .venv/bin/python -m pytest tests/ -q
# frontend
cd frontend && npm run lint && npm run build
```

## Folder map

```
backend/app/
├── main.py        # FastAPI app (CORS, schema on startup)
├── config.py      # settings from env
├── api/routes.py  # /health, /search (SSE)
├── llm/           # intent (Haiku), embeddings (Voyage), rerank (Sonnet)
├── retrieval/     # hybrid search (SQL + pgvector)
├── catalog/       # SQLAlchemy models, DB session
└── ingestion/     # pipeline, dedup, taxonomy, adapters/, runner
```
