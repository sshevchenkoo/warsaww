# warsaw, — what now?

A prompt-based discovery engine for **events and places in Warsaw**. Type a
free-form vibe and get a ranked list of cards — concerts and parties alongside
castles, museums and parks — each with a one-line pitch written in your own
language.

```
"a quiet museum about Chopin"   → Frederic Chopin Museum
"techno party this weekend"     → tonight's parties, with dates & venues
"spokojny spacer nad wodą"      → parks by the water, ranked
```

Free-form prompt → structured intent (LLM) → hybrid SQL + vector search →
LLM re-ranking with per-card blurbs, streamed to the browser card-by-card.

> This repository began as the **ft_transcendence** DevOps module — a
> self-hosted k3s platform on Hetzner — and now also hosts the Warsaw-events
> application built on top of that platform.

---

## How it works

```
Browser (Next.js, SSE)
   │  free-form prompt
   ▼
Core API (FastAPI, modular monolith)
   ├─ llm        intent extraction (Claude Haiku, structured outputs)
   ├─ retrieval  hybrid search: SQL filters + pgvector cosine ranking
   ├─ llm        re-rank top-30 + write blurbs (Claude Sonnet), stream via SSE
   └─ catalog    Postgres 16 + pgvector
        ▲
        │  normalize → dedup → embed → upsert
   Ingestion (one adapter per source, k8s CronJobs)
        ├─ places           OpenStreetMap (Overpass) + Wikidata enrichment
        └─ facebook_events   Apify actor

Embeddings: Voyage voyage-3.5 (same model for cards and queries)
Platform:   k3s on Hetzner · ELK logs · Prometheus/Grafana · cert-manager TLS
```

## Features

- **Any-language prompts** (RU / PL / EN) — the intent model normalizes them; blurbs come back in the user's language.
- **Hybrid retrieval** — SQL filters (date, price, category) combined with vector similarity (pgvector HNSW, cosine distance) in one query.
- **LLM re-ranking** — Claude Sonnet drops irrelevant candidates, reorders the rest, and writes a one-line pitch per card; results stream over Server-Sent Events.
- **Pluggable ingestion** — a new source is one adapter class + one registry line + one CronJob; cross-source deduplication folds duplicates instead of showing them twice.
- **Production platform** — Terraform + Ansible provision k3s on Hetzner with ELK logging, Prometheus/Grafana monitoring, and automatic TLS.

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), Tailwind v4, SSE |
| Backend | FastAPI, SQLAlchemy 2, Pydantic |
| Data | PostgreSQL 16 + pgvector (HNSW) |
| LLM | Claude Haiku (intent), Claude Sonnet (re-rank), Anthropic SDK |
| Embeddings | Voyage `voyage-3.5` (multilingual, 1024-dim) |
| Ingestion | httpx adapters, rapidfuzz dedup, k8s CronJobs |
| Platform | Terraform, Ansible, k3s, Hetzner Cloud, ELK, Prometheus/Grafana |

## Repository layout

| Path | What |
|---|---|
| `backend/` | Warsaw-events FastAPI app — API, LLM layer, retrieval, ingestion ([README](backend/README.md)) |
| `frontend/` | Next.js UI, "Pure"-style ([README](frontend/README.md)) |
| `backend/k8s/` | Kubernetes manifests for the app (namespace `warsaw`) ([README](backend/k8s/README.md)) |
| `infrastructure/` | Terraform + Ansible: the Hetzner k3s platform ([docs](docs/infrastructure.md)) |
| `docker_compose/` | The original ft_transcendence Django service (local compose) |
| `k8s/` | Kubernetes manifests for the ft_transcendence Django service |
| `docs/` | Project documentation (see below) |

## Quick start (local)

Set `backend/.env` (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `APIFY_TOKEN`), then
from the repo root:

```bash
make app-up      # build + start API, Postgres/pgvector, Redis on :8000
make app-seed    # load Warsaw places + events into the DB
make web         # start the Next.js frontend on :3000
make app-down    # stop the stack (data kept in the pgdata volume)
```

`make help` lists every target. The equivalent manual commands are in
[docs/local-development.md](docs/local-development.md).

Deploying to the cluster: app manifests in [`backend/k8s/`](backend/k8s/README.md),
the platform itself in [`docs/infrastructure.md`](docs/infrastructure.md).

## Documentation

| Doc | Topic |
|---|---|
| [Architecture](docs/architecture.md) | Components, data flow, design decisions |
| [Data model](docs/data-model.md) | `items` and `intent_logs` schema |
| [Search & LLM](docs/search-and-llm.md) | Intent, embeddings, hybrid search, re-rank, cost |
| [Ingestion](docs/ingestion.md) | Adapters, sources, enrichment, deduplication |
| [Deployment](docs/deployment.md) | Docker image, k8s manifests, CronJobs |
| [Local development](docs/local-development.md) | Running and testing locally |
| [Infrastructure](docs/infrastructure.md) | The Hetzner k3s platform (Terraform/Ansible) |
