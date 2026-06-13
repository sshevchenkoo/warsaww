# Backend — Warsaw Events

The app that finds events and places in Warsaw from a free-form user prompt.
Deeper topics: [architecture](architecture.md), [data model](data-model.md),
[search & LLM](search-and-llm.md), [ingestion](ingestion.md).

## Structure

```
app/
├── main.py        # FastAPI application (CORS, schema on startup)
├── config.py      # settings (env)
├── api/           # HTTP endpoints (/health, /search SSE)
├── llm/           # Claude calls: intent, embeddings, re-rank
├── retrieval/     # hybrid search (SQL + pgvector)
├── catalog/       # DB models, sessions
└── ingestion/     # source parsing (pipeline, dedup, taxonomy, adapters)
```

## Local setup

Full stack in containers (API + Postgres/pgvector + Redis) — closest to prod.
From the repo root, `make app-up` does this; the explicit commands are:

```bash
cd backend
cp .env.example .env            # set ANTHROPIC_API_KEY, VOYAGE_API_KEY, APIFY_TOKEN
docker compose up -d --build    # builds the API image, starts the whole site on :8000
```

Or run the API on the host against containerized data (hot reload for dev):

```bash
docker compose up -d db redis   # just the datastores
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Smoke test:

```bash
curl localhost:8000/health
# /search streams Server-Sent Events: an `intent` event, then a `card`
# event per ranked result, then `done`. Use -N to see them as they arrive.
# prompts work in any language (RU/PL/EN) — the intent model normalizes them
curl -N -X POST localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"prompt": "where to go on a cheap Saturday night"}'
```

## Ingestion

Single image, the source is selected by argument (in k8s — one CronJob per
source). From the repo root, `make app-seed` runs both; the explicit commands:

```bash
python -m app.ingestion.runner --source=places
python -m app.ingestion.runner --source=facebook_events
```

## Deploy

`Dockerfile` builds one image for both the API and the ingestion CronJobs.
Kubernetes manifests and the step-by-step deploy are in
[deployment.md](deployment.md).

## Status

- [x] Skeleton: API, DB models, intent extraction via Claude Haiku (structured outputs), intent logging
- [x] SQL search filters
- [x] Vector search: Voyage voyage-3.5 (1024d), hybrid SQL filters + cosine ranking, verified end-to-end on RU/EN/PL prompts
- [x] Re-rank via Claude Sonnet (claude-sonnet-4-6) + SSE streaming: filters/reorders top-30, writes a per-card blurb in the user's language, streamed card-by-card
- [x] First real adapter (places: Overpass API, ~385 tourist-worthy places — `wikidata` tag as notability filter)
- [x] Wikidata enrichment for places (Wikipedia intro as description + Commons photo; 383/385 covered)
- [x] Upsert by (source, source_url) — re-running a source updates instead of duplicating
- [x] Facebook events adapter via Apify actor (needs APIFY_TOKEN; Warsaw-PL bbox filter, skips canceled/past/online)
- [x] Deduplication: block (event day / place coords) + rapidfuzz token-set match; auto-merge ≥90, Haiku adjudicates the 75–90 band; duplicates fold their source refs into the canonical card's `sources` (unit-tested; folded a real OSM dup live)
- [x] Dockerfile + docker-compose full local stack (API+db+redis)
- [x] k8s manifests: namespace, Postgres/pgvector StatefulSet, Redis, API Deployment+Service+HPA, SSE-ready ingress, CronJob per source
- [ ] Frontend deploy to the cluster (Next standalone image + manifests in the `warsaw` namespace)
