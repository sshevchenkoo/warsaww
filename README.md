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
        ├─ places            OpenStreetMap (Overpass) + Wikidata enrichment
        ├─ facebook_events   Apify actor
        └─ ticketmaster      Ticketmaster Discovery API

Embeddings: Voyage voyage-3.5 (same model for cards and queries)
Platform:   DigitalOcean DOKS · managed Postgres · ELK logs · Prometheus/Grafana · cert-manager TLS
```

## Features

- **Any-language prompts** (RU / PL / EN) — the intent model normalizes them; blurbs come back in the user's language.
- **Hybrid retrieval** — SQL filters (date, price, category) combined with vector similarity (pgvector HNSW, cosine distance) in one query.
- **LLM re-ranking** — Claude Sonnet drops irrelevant candidates, reorders the rest, and writes a one-line pitch per card; results stream over Server-Sent Events.
- **Pluggable ingestion** — a new source is one adapter class + one registry line + one CronJob; cross-source deduplication folds duplicates instead of showing them twice.
- **Production platform** — Terraform provisions DigitalOcean DOKS + managed Postgres + an ELK droplet; Helm installs ELK logging, Prometheus/Grafana/Tempo monitoring, and automatic TLS (cert-manager).

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), Tailwind v4, SSE |
| Backend | FastAPI, SQLAlchemy 2, Pydantic |
| Data | PostgreSQL 16 + pgvector (HNSW) |
| LLM | Claude Haiku (intent), Claude Sonnet (re-rank), Anthropic SDK |
| Embeddings | Voyage `voyage-3.5` (multilingual, 1024-dim) |
| Ingestion | httpx adapters, rapidfuzz dedup, k8s CronJobs |
| Platform | DigitalOcean DOKS, Terraform, managed Postgres, ELK, Prometheus/Grafana/Tempo |

## Modules

Scored against the ft_transcendence subject v21.1, section IV (Major = 2 points, Minor = 1,
14 required). The working inventory, with the risks attached and the modules we ruled out, is
[docs/MODULES.md](docs/MODULES.md).

| # | Module | Category | Type | Pts | Implemented by | Where |
|---|---|---|---|---|---|---|
| 1 | Framework for both frontend and backend | Web | Major | 2 | stefandawid, yagruda, tbogus | Next.js 16 App Router in `frontend/`, FastAPI in `backend/app/` |
| 2 | Use an ORM | Web | Minor | 1 | yagruda, tbogus | SQLAlchemy 2 typed models, `backend/app/catalog/models.py` ([ORM.md](docs/ORM.md)) |
| 3 | Server-Side Rendering | Web | Minor | 1 | stefandawid | `/item/[id]` is rendered on the server with its own metadata, `frontend/src/app/item/[id]/page.tsx` |
| 4 | Custom design system | Web | Minor | 1 | stefandawid | Palette and type tokens in `frontend/src/app/globals.css`, an SVG icon set in `frontend/src/components/Icon.tsx`, 15 reusable components in `frontend/src/components/` |
| 5 | Standard user management | User Management | Major | 2 | tbogus, yagruda | Profile edit (`PATCH /me`), avatar upload with a default, friends with online status — `backend/app/api/`, `frontend/src/app/profile/` |
| 6 | OAuth 2.0 remote authentication | User Management | Minor | 1 | tbogus | Google OIDC via authlib, `backend/app/auth/oauth.py` |
| 7 | Complete RAG system | AI | Major | 2 | tbogus, yagruda | Voyage embeddings + pgvector/pg_trgm hybrid retrieval, blurbs grounded in the retrieved cards — `backend/app/retrieval/` |
| 8 | Complete LLM system interface | AI | Major | 2 | tbogus, yagruda | Intent extraction (Haiku) and re-rank (Sonnet) streamed over SSE, with error handling and a daily quota — `backend/app/llm/` |
| 9 | File upload and management | User Management | Minor | 1 | yagruda, tbogus | Avatar upload: type and size checks on both sides, upload progress, delete — `backend/app/api/avatars.py` |
| 10 | ELK log management | DevOps | Major | 2 | sshevchenkoo | Elasticsearch + Logstash + Kibana, Fluent Bit shipping, ILM retention — `deploy/cloud/ansible/`, `deploy/cloud/platform/` |
| 11 | Prometheus + Grafana monitoring | DevOps | Major | 2 | sshevchenkoo | kube-prometheus-stack, exporters, dashboards, alert rules — `deploy/cloud/platform/` |
| 12 | Custom module: multi-source ingestion pipeline | Module of choice | Major | 2 | tbogus, yagruda | `backend/app/ingestion/` ([INGESTION.md](docs/INGESTION.md)) — justified below |
| | **Total** | | | **19** | | |

Two notes on how these are counted:

- **#1 is the Major on its own.** The subject lists "frontend framework" and "backend framework" as
  separate Minors and "both" as a Major. They are alternatives, so #1 is worth 2 points, not 2 + 1 + 1.
- **#7 and #8 are two modules, demonstrated separately**, even though both run inside `/search`.
  The LLM interface (#8) is the prompt → Haiku structured output → Sonnet streaming into SSE, with
  the degradation ladder in [SEARCH.md](docs/SEARCH.md) §5. The RAG system (#7) is the catalog as
  the dataset, hybrid retrieval as the context step ([ALGORITHMS.md](docs/ALGORITHMS.md) §4), and
  blurbs that can only describe cards the retrieval returned.

### Custom module: multi-source ingestion pipeline (Major, 2 pts)

**Why we chose it.** The product is only as good as its catalog: a search engine for "what to do in
Warsaw tonight" is useless if half the concerts are missing or the same museum shows up three
times. No single source covers both events and places, so the catalog is built from four
([INGESTION.md](docs/INGESTION.md) §3): OpenStreetMap enriched with Wikidata for places, Facebook
events through Apify, the Ticketmaster Discovery API, and a keyless fixture set for demos. Keeping
those sources in sync, without duplicates and without breaking search, is the module.

**Technical challenges it addresses.**

- **Four heterogeneous sources behind one contract.** Every source implements a single method,
  `fetch() -> list[RawItem]` (§2). Normalisation, deduplication, embedding and upsert are shared,
  so adding a fifth source is one adapter class, one registry line and one CronJob (§5).
- **Cross-source deduplication in three tiers** (§4.3). Candidates are blocked first, then scored
  with rapidfuzz: 90 and above is the same entity, below 75 is not. Only the ambiguous 75–89 band
  goes to Claude Haiku for a yes/no decision, so the LLM is paid for a handful of pairs, not the
  whole catalog. Without an Anthropic key the band counts as "not a match" and ingestion still runs.
  Dedup runs before embedding, so nobody pays to embed a duplicate.
- **Failure isolation at every level** (§4.1–4.4). A source that is down aborts only its own run
  (each source is its own CronJob); a malformed record is skipped without losing the other 99;
  a failed embedding batch of 16 is logged and the rest still get vectors.
- **The embedding-erasure trap** (§4.5). The upsert's `ON CONFLICT DO UPDATE` refreshes the
  `embedding` column only when this run actually computed one. Without that split, one run without
  a Voyage key would overwrite every stored vector with `NULL` and silently switch off semantic
  search for the whole catalog.

**How it adds value.** Every search result the user sees comes out of this pipeline. It is what
lets the RAG module (#7) retrieve from a real, current, de-duplicated catalog instead of a static
seed file, and it keeps running unattended: in production each source is a Kubernetes CronJob, and
locally `make scheduler-up` runs the same schedule.

**Why it deserves Major status.** It is a complete subsystem with its own architecture, not a
feature of another module: a pluggable adapter layer, a staged pipeline with per-stage failure
handling, fuzzy and LLM-assisted entity resolution, batched embedding, idempotent upserts keyed on
`(source, source_url)`, and scheduled execution in two environments. It is documented end to end
in [INGESTION.md](docs/INGESTION.md), including the cost of a run (§6) and how to add a source (§5).

## Repository layout

| Path | What |
|---|---|
| `backend/` | Warsaw-events FastAPI app — API, LLM layer, retrieval, ingestion ([docs](docs/backend.md)) |
| `frontend/` | Next.js UI, "Pure"-style ([docs](docs/frontend.md)) |
| `deploy/cloud/k8s/` | Kubernetes manifests for the app, namespace `warsaw` ([deploy docs](docs/deployment.md)) |
| `deploy/cloud/terraform/` | Terraform for DigitalOcean prod (DOKS + managed Postgres + ELK) |
| `deploy/cloud/ansible/` | Ansible role that provisions the ELK droplet |
| `deploy/cloud/platform/` | DOKS Helm values + manifests (monitoring, ingress, cert-manager) |
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

Full local stack (app + observability, one command): [deploy/local/README.md](deploy/local/README.md).
Cloud deployment (DigitalOcean DOKS): overview in [deploy/cloud/README.md](deploy/cloud/README.md),
app manifests in [docs/deployment.md](docs/deployment.md), full platform runbook in
[docs/hosting-digitalocean.md](docs/hosting-digitalocean.md).

## Documentation

| Doc | Topic |
|---|---|
| [Backend](docs/backend.md) | App structure, local setup, status |
| [Frontend](docs/frontend.md) | UI, SSE client, re-skinning |
| [Architecture](docs/architecture.md) | Components, data flow, design decisions |
| [Data model](docs/data-model.md) | `items`, `intent_logs`, `users`, `saved_items` schema |
| [Search & LLM](docs/search-and-llm.md) | Intent, embeddings, hybrid search, re-rank, cost |
| [Auth & profiles](docs/auth.md) | Google sign-in, sessions, saved items |
| [Ingestion](docs/ingestion-overview.md) | Adapters, sources, enrichment, deduplication |
| [Deployment](docs/deployment.md) | Docker image, k8s manifests, CronJobs |
| [Local development](docs/local-development.md) | Running and testing locally |
| [Hosting (DigitalOcean)](docs/hosting-digitalocean.md) | Prod on DOKS — Terraform, Helm, ELK |
| [Deploy — local stack](deploy/local/README.md) | Full local stack (app + Grafana/Prometheus/Tempo + ELK) in one command |
| [Deploy — cloud](deploy/cloud/README.md) | Cloud deployment overview (DOKS + managed Postgres + ELK droplet) |

### Deep dives

Long-form companions to the reference docs above — how each part actually works, what it was chosen
over, and how it fails.

| Doc | Topic |
|---|---|
| [ALGORITHMS](docs/ALGORITHMS.md) | Every algorithm in the search path: intent, embeddings, the two retrieval legs and RRF, re-ranking, dedup |
| [SEARCH](docs/SEARCH.md) | One `/search` request end to end — ordering, connection lifecycle, the degradation ladder |
| [INGESTION](docs/INGESTION.md) | The adapter contract, the four sources, the pipeline stages, adding a fifth |
| [SECURITY](docs/SECURITY.md) | Identity, sessions, RLS, rate limits, uploads, secrets — and what none of it covers |
| [MODULES](docs/MODULES.md) | Subject module scoring: what we can claim today, what is one step away |
