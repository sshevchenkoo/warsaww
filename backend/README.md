# Backend — Warsaw Events

Backend for the app that finds events and places in Warsaw from a free-form user prompt.
Full documentation: Notion → ft_transcendence → **Backend**.

## Structure

```
app/
├── main.py        # FastAPI application
├── config.py      # settings (env)
├── api/           # HTTP endpoints
├── llm/           # Claude calls: intent, re-rank
├── retrieval/     # hybrid search (SQL + pgvector)
├── catalog/       # DB models, sessions
└── ingestion/     # source parsing (adapters, pipeline)
```

## Local setup

Full stack in containers (API + Postgres/pgvector + Redis) — closest to prod:

```bash
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
curl -N -X POST localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"prompt": "куда сходить в субботу вечером недорого"}'
```

## Ingestion

Single image, the source is selected by argument (in k8s — one CronJob per source):

```bash
python -m app.ingestion.runner --source=places
python -m app.ingestion.runner --source=facebook_events
```

## Deploy

`Dockerfile` builds one image for both the API and the ingestion CronJobs.
Kubernetes manifests and step-by-step deploy live in [`k8s/`](k8s/README.md).

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
