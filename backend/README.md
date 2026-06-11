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
- [ ] Vector search (pending embedding model choice: Voyage vs bge-m3)
- [ ] Re-rank via Opus + SSE streaming
- [ ] First real adapter (places: Overpass API)
- [ ] Deduplication (rapidfuzz + Haiku Batches)
