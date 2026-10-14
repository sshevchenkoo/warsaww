# Local development

The full stack — app, HTTPS gateway, monitoring and ELK — is `make stack-init`; see
[deploy/local/README.md](../deploy/local/README.md). This page is the lighter setup for working
on the code: the backend API (with Postgres/pgvector + Redis) and the Next.js frontend on the host.

## Make shortcuts (from the repo root)

```bash
make app-up      # build + start API, Postgres/pgvector, Redis on :8000
make app-seed    # load Warsaw places + Facebook events into the DB
make web         # start the Next.js frontend on :3000
make dev         # app-up + web in the background
make app-logs    # follow the API logs
make app-down    # stop the stack (data kept in the pgdata volume)
```

The manual equivalents are below.

## Backend

Full stack in containers — closest to production:

```bash
cd backend
cp .env.example .env            # keys: see api-keys.md
docker compose up -d --build    # API + Postgres/pgvector + Redis on :8000
```

Or run the API on the host against containerized datastores (hot reload):

```bash
docker compose up -d db redis
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Load data — one source per run (`places`, `facebook_events`, `ticketmaster`, `fixtures`; see
[INGESTION.md](INGESTION.md)) — then smoke-test the SSE endpoint:

```bash
python -m app.ingestion.runner --source=places
curl localhost:8000/health
curl -N -X POST localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"prompt": "where to go on a cheap Saturday night"}'
```

`/search` streams Server-Sent Events: an `intent` event, then a `card` event per
ranked result, then `done`. With `REQUIRE_VERIFIED_EMAIL_TO_SEARCH=true` (the default) it
answers 401 without a verified session — set it to `false` in `backend/.env` for curl tests.

## Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev                     # http://localhost:3000
```

The browser calls the API with relative URLs (`/search`, `/auth`, `/me`, …). Next.js rewrites
(`frontend/next.config.ts`) proxy them to `BACKEND_INTERNAL_URL` (default
`http://localhost:8000`), so the session cookie stays first-party to `:3000`.

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
├── main.py        # FastAPI app, schema bootstrap (_create_schema), RLS policies
├── config.py      # settings from env
├── api/           # routes: search, auth, saved, social, avatars
├── auth/          # OAuth, passwords, email codes, current_user
├── llm/           # intent (Haiku), embeddings (Voyage), rerank (Sonnet)
├── retrieval/     # hybrid search (SQL + pgvector + pg_trgm)
├── catalog/       # SQLAlchemy models, DB session
├── ingestion/     # pipeline, dedup, taxonomy, adapters/, runner
└── ratelimit.py   # Redis search quota + auth rate limit
```

`backend/Dockerfile` builds one image for both the API and the ingestion CronJobs — see
[deployment.md](deployment.md).
