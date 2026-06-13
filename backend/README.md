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

```bash
docker compose up -d            # Postgres + pgvector and Redis
cp .env.example .env            # set ANTHROPIC_API_KEY
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Smoke test:

```bash
curl localhost:8000/health
curl -X POST localhost:8000/search \
  -H 'content-type: application/json' \
  -d '{"prompt": "куда сходить в субботу вечером недорого"}'
```

## Ingestion

Single image, the source is selected by argument (in k8s — one CronJob per source):

```bash
python -m app.ingestion.runner --source=places
```

## Status

- [x] Skeleton: API, DB models, intent extraction via Claude Haiku (structured outputs), intent logging
- [x] SQL search filters
- [x] Vector search: Voyage voyage-3.5 (1024d), hybrid SQL filters + cosine ranking, verified end-to-end on RU/EN/PL prompts
- [ ] Re-rank via Opus + SSE streaming
- [x] First real adapter (places: Overpass API, ~385 tourist-worthy places — `wikidata` tag as notability filter)
- [x] Wikidata enrichment for places (Wikipedia intro as description + Commons photo; 383/385 covered)
- [x] Upsert by (source, source_url) — re-running a source updates instead of duplicating
- [x] Facebook events adapter via Apify actor (needs APIFY_TOKEN; Warsaw-PL bbox filter, skips canceled/past/online)
- [ ] Deduplication (rapidfuzz + Haiku Batches)
