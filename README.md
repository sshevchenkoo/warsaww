*This project has been created as part of the 42 curriculum by tbogus, yhruda, dstefans, yashevch.*

# warsaw, — what now?

## Description

**warsaw, — what now?** is a prompt-based discovery engine for **events and places in Warsaw**.
Type a free-form vibe in English, Polish or Russian and get a ranked list of cards — concerts and
parties alongside castles, museums and parks — each with a one-line pitch in your own language.

```
"a quiet museum about Chopin"   → Frederic Chopin Museum
"techno party this weekend"     → tonight's parties, with dates & venues
"spokojny spacer nad wodą"      → parks by the water, ranked
```

Key features: multilingual prompt search with LLM re-ranking streamed card by card, a catalog kept
fresh by scheduled multi-source ingestion, accounts with email or Google sign-in, profiles with
avatars, friends, saved items and event sharing, plus full logging and monitoring.

### How it works

```
Browser (Next.js, SSE)
   │  free-form prompt
   ▼
Core API (FastAPI)
   ├─ llm        intent extraction (Claude Haiku, structured output)
   ├─ retrieval  hybrid search: SQL filters + pgvector + pg_trgm
   ├─ llm        re-rank top 30 + write blurbs (Claude Sonnet), streamed over SSE
   └─ catalog    PostgreSQL 16 + pgvector
        ▲  normalize → dedup → embed → upsert
   Ingestion: OpenStreetMap + Wikidata · Facebook events (Apify) · Ticketmaster · demo fixtures
```

Everything runs locally with one command (Docker Compose behind an HTTPS nginx gateway). The same
stack can optionally be deployed to DigitalOcean Kubernetes; that is reference only and not needed
to run or grade the project.

## Instructions

### Prerequisites

- Git, Docker Engine/Desktop with Compose v2.24+, GNU `make`, `curl`.
- About 4–6 GB of free RAM for the full stack (app + monitoring + ELK).
- On Linux, Elasticsearch needs `vm.max_map_count` ≥ 262144 — see
  [local prerequisites](deploy/local/README.md#prerequisites).
- Node.js 20.9+ only to run the frontend outside Docker (`make web`).

### Environment

Copy `backend/.env.example` to `backend/.env`. The stack starts without keys, but search and the
first-run demo data need `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY`; without them seeding is skipped
with a hint. Every key and how to get it: [docs/api-keys.md](docs/api-keys.md).

| Variable | Needed for |
|---|---|
| `ANTHROPIC_API_KEY` | Intent extraction, re-ranking, dedup adjudication |
| `VOYAGE_API_KEY` | Embeddings (semantic search) |
| `SESSION_SECRET` | Signing session cookies and codes; at least 32 characters in production |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in |
| `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO` | Verification emails (none are sent without `RESEND_API_KEY`) |
| `APIFY_TOKEN`, `TICKETMASTER_API_KEY` | Facebook-events and Ticketmaster ingestion |

### Run

```bash
git clone https://github.com/sshevchenkoo/warsaww.git && cd warsaww
cp backend/.env.example backend/.env    # then fill in ANTHROPIC_API_KEY + VOYAGE_API_KEY
make stack-up      # build + start everything; a fresh DB also gets 100 demo events + test users
make stack-seed    # optional: the real Warsaw catalog (places, Facebook, Ticketmaster)
```

Open **https://localhost**, accept the self-signed certificate once, and sign in as
`user1@test.com` / `1234`.

Every browser-facing endpoint is HTTPS through nginx; the app, API and Grafana containers publish no
host port. The infra UIs share one login (user `admin`, a random password **printed once** by the
first `make stack-up`; change it with `make infra-auth AUTH_USER=.. AUTH_PASS=..`): Grafana
**https://localhost:3001**, Kibana **https://localhost:5601**, Prometheus **https://localhost:9090**.

| Command | What |
|---|---|
| `make scheduler-up` | Run ingestion on the same schedule as the cloud CronJobs |
| `make stack-down` | Stop everything (data volumes are kept) |
| `make app-up` + `make web` | Lighter setup: API, Postgres and Redis only, frontend on the host |
| `make help` | Every target |

More: [local stack guide](deploy/local/README.md), [manual commands and tests](docs/local-development.md),
optional [cloud deployment](deploy/cloud/README.md).

## Team information

| Member | Login | Role | Responsibilities |
|---|---|---|---|
| Tomasz | `tbogus` | Product Owner, developer | Define product priorities and maintain the backlog; develop backend search, LLM integration, ingestion, authentication and security |
| Yurii | `yhruda` | Project Manager, developer | Coordinate task distribution, meetings, progress and blockers; develop retrieval, prompts, catalog, authentication and social features |
| Dawid | `dstefans` | Developer | Implement the frontend, shared UI components, SSR and social features; test and document those changes |
| Yaroslav | `yashevch` | Technical Lead, developer | Oversee architecture, technology choices, code quality and technical integration; develop Terraform, Kubernetes, ELK and monitoring infrastructure |

## Project management

- **Organisation.** Work was scored against the module list ([docs/MODULES.md](docs/MODULES.md)) and
  split into GitHub issues #4–#28, grouped into waves (`wave-0` … `wave-4`) of independent pull
  requests. Each issue carries its estimate, the points it earns or protects, and its dependencies.
  Tasks followed the responsibility areas above.
- **Tools.** GitHub Issues with labels (`+2 pts` / `+1 pts` / `protects pts`, `backend` / `frontend` /
  `infra`, `needs-team-input`) and GitHub pull requests: every change goes into `main` through a PR
  that says what changed, how it was checked and what was not.
- **Communication.** WhatsApp for day-to-day coordination, meetings to discuss work and blockers,
  asynchronous progress updates in between.

## Technical stack

| Layer | Tech | Why |
|---|---|---|
| Frontend | Next.js 16 (App Router), Tailwind v4, SSE | Server-rendered item pages for SEO and fast first paint; streamed results without WebSockets |
| Backend | FastAPI, SQLAlchemy 2, Pydantic | Async endpoints with SSE, typed models end to end, validation from the same types |
| Database | PostgreSQL 16 + pgvector (HNSW), pg_trgm | Filters, vectors and fuzzy text in one database and one query, instead of a separate vector store |
| Rate limits | Redis 7 | Shared counters for search quotas and auth rate limits |
| Authentication | Authlib, signed-cookie sessions, bcrypt, Resend | Google OIDC and password login share one account model; emailed codes prove ownership |
| LLM | Claude Haiku (intent), Claude Sonnet (re-rank), Anthropic SDK | A fast, cheap model for structured intent; a stronger one only for the final top 30 |
| Embeddings | Voyage `voyage-3.5` (multilingual, 1024-dim) | One model for cards and queries, so EN / PL / RU prompts land in the same space |
| Ingestion | httpx adapters, rapidfuzz, k8s CronJobs | Plain HTTP client per source, fast fuzzy matching, one schedule per source so failures stay isolated |
| Platform | Docker Compose, nginx, ELK, Prometheus/Grafana/Tempo; optional DigitalOcean DOKS + Terraform | One-command local stack; infrastructure as code for a reproducible cloud |

## Database schema

Events and places share one table, `items`, with a `kind` column. Everything a user owns hangs off
`users` with `ON DELETE CASCADE`. Indexes and Row-Level Security policies:
[docs/data-model.md](docs/data-model.md).

```
                  ┌──────────────┐
                  │    items     │  catalog: events + places
                  └──────┬───────┘
            item_id      │      item_id
        ┌────────────────┴────────────────┐
        ▼                                 ▼
┌──────────────┐                  ┌──────────────┐
│ saved_items  │                  │shared_events │
└──────┬───────┘                  └──┬────────┬──┘
       │ user_id           from_user_id│        │to_user_id
       ▼                              ▼        ▼
   ┌──────────────────────────────────────────────┐
   │                    users                     │
   └──────┬───────────────────────────────┬───────┘
          │ requester_id / addressee_id   │ user_id (PK)
          ▼                               ▼
   ┌──────────────┐                ┌──────────────┐
   │ friendships  │                │ user_avatars │
   └──────────────┘                └──────────────┘

   intent_logs — standalone, no FKs
```

| Table | Holds | Key fields and types |
|---|---|---|
| `items` | Events and places with dates, prices, location, sources and an embedding | `id uuid` PK; `kind text`; `name text`; `starts_at/ends_at timestamptz`; `price_from/price_to numeric`; `lat/lon float`; `sources/opening_hours jsonb`; `embedding vector(1024)` |
| `users` | Accounts: Google id or bcrypt hash, verification state, pending email, last seen | `id uuid` PK; unique `email`, `google_sub text`; `password_hash text`; `email_verified boolean`; `pending_email text`; `last_seen_at timestamptz` |
| `saved_items` | A user's saved cards | `id uuid` PK; `user_id` FK → users; `item_id` FK → items; unique `(user_id, item_id)` |
| `friendships` | Friend requests, directed until accepted | `id uuid` PK; `requester_id/addressee_id` FKs → users; `status text` ∈ pending/accepted |
| `shared_events` | A card sent from one user to another | `id uuid` PK; `from_user_id/to_user_id` FKs → users; `item_id` FK → items; `message text` |
| `user_avatars` | Uploaded avatar bytes, at most one per user | `user_id uuid` PK/FK → users; `data bytea`; `content_type text`; `updated_at timestamptz` |
| `user_files` | Attachments (PDF tickets, photos) a user pinned to an item | `id uuid` PK; `user_id` FK → users; `item_id` FK → items; `filename text`; `content_type text` (PDF/image, CHECK); `size integer`; `data bytea` (≤ 5 MB, CHECK) |
| `intent_logs` | Every parsed prompt and its intent (analytics) | `id uuid` PK; `user_prompt text`; `intent jsonb`; `model text`; `latency_ms integer` |

## Features list

| Feature | What it does | Team member(s) |
|---|---|---|
| Prompt search in any language | Free-form prompt in EN / PL / RU; the intent model normalises it and the blurbs come back in the user's language | tbogus, yhruda |
| Hybrid retrieval | SQL filters (date, price, category) and pgvector similarity in one query | tbogus, yhruda |
| LLM re-ranking, streamed | Claude Sonnet drops irrelevant candidates, reorders the rest and writes a pitch per card, streamed over SSE | tbogus, yhruda |
| Search resilience and quotas | Redis daily quotas, lexical fallback when embeddings fail, fallback cards when re-ranking fails | yhruda, tbogus |
| Multi-source ingestion | Four source adapters, cross-source deduplication, scheduled runs (custom module) | tbogus, yhruda |
| Upcoming events and item pages | Browse upcoming events without an LLM call; server-rendered detail pages with metadata and image fallbacks | dstefans |
| Accounts | Email + password sign-up with a 6-digit code, Google sign-in, sessions; search needs a verified email | yhruda, tbogus, dstefans |
| Profile | Stats, inline edit of name and email (email change confirmed by code), avatar upload with progress and delete | tbogus, yhruda, dstefans |
| Friends and sharing | Friend requests, online status, public profiles, sharing a card, a "shared with you" inbox | dstefans, yhruda, tbogus |
| Saved items | Save a card with the heart; friends see each other's saved lists | yhruda, dstefans |
| Attachments | Attach a PDF ticket or photo to a saved event/place: upload with progress, thumbnail/PDF preview, delete; files stay private to the owner | tbogus |
| Design system | Palette and type tokens, reusable components, shared SVG icons and spinners | dstefans, tbogus |
| Privacy and terms | Privacy Policy and Terms of Service pages linked from the footer | dstefans |
| HTTPS everywhere | The site and all infra UIs served over HTTPS by nginx; no app/API/Grafana host ports | yashevch |
| Observability | ELK logging and Prometheus/Grafana/Alertmanager monitoring, locally and in the cloud | yashevch |
| Production platform | Terraform for DigitalOcean DOKS + managed Postgres + ELK droplet; Helm for logging, monitoring and TLS | yashevch |

## Modules

Scored against the ft_transcendence subject v21.1, section IV (Major = 2 pts, Minor = 1 pt,
14 required). The table totals 7 Major × 2 + 6 Minor × 1 = **20 points**; the bonus is capped at +5,
so **19 count**, and #13 is a reserve in case another module is not validated.
[docs/MODULES.md](docs/MODULES.md) lists the risks per claim and implemented-but-unclaimed modules
(2FA, GDPR).

| # | Module | Type | Pts | By | How it is implemented | Why we chose it |
|---|---|---|---|---|---|---|
| 1 | Framework for frontend and backend | Major | 2 | dstefans, yhruda, tbogus | Next.js 16 App Router (`frontend/`), FastAPI (`backend/app/`) | Server rendering in the browser app; typed APIs and streamed search on the server |
| 2 | ORM | Minor | 1 | yhruda, tbogus, dstefans | SQLAlchemy 2 typed models, `backend/app/catalog/models.py` ([ORM.md](docs/ORM.md)) | One consistent persistence layer for the catalog and accounts |
| 3 | Server-Side Rendering | Minor | 1 | dstefans | `/item/[id]` rendered on the server with its own metadata | Shared item links need content and metadata before JavaScript runs |
| 4 | Custom design system | Minor | 1 | dstefans, tbogus | Tokens in `globals.css`, 18 component files, shared icons and Spinner in `Icon.tsx` | Search, profile and social screens stay consistent |
| 5 | Standard user management | Major | 2 | tbogus, yhruda, dstefans | Profile edit (`PATCH /me`), avatar with a default, friends with online status | Profiles, saves and friends make the service useful beyond one search |
| 6 | OAuth 2.0 remote authentication | Minor | 1 | yhruda, tbogus | Google OIDC via Authlib, `backend/app/auth/oauth.py` | Sign-in without yet another password |
| 7 | Complete RAG system | Major | 2 | tbogus, yhruda | Voyage embeddings + pgvector/pg_trgm hybrid retrieval; blurbs only describe retrieved cards — `backend/app/retrieval/` | Answers must be grounded in real catalog entries with real dates and places |
| 8 | Complete LLM system interface | Major | 2 | tbogus, yhruda | Haiku intent extraction and Sonnet re-rank streamed over SSE, with error handling and a daily quota — `backend/app/llm/` | Free-form multilingual requests need intent extraction and readable explanations |
| 9 | File upload and management | Minor | 1 | yhruda, tbogus | PDF/image attachments on saved items **and** avatars: type (sniffed from bytes) and size checked both sides, owner-only via RLS, thumbnail/PDF preview, progress, delete — `backend/app/api/files.py`, `avatars.py`, `frontend/src/components/ItemFiles.tsx` | Users attach tickets/photos to saved items and manage an avatar, with validated, bounded files |
| 10 | ELK log management | Major | 2 | yashevch | Elasticsearch + Logstash + Kibana, Fluent Bit shipping, retention — `deploy/local/` (cloud: `deploy/cloud/`) | Searchable logs make API and ingestion failures diagnosable across containers |
| 11 | Prometheus + Grafana monitoring | Major | 2 | yashevch | Prometheus, Grafana, Alertmanager, exporters, dashboards, alert rules — `deploy/local/` (cloud: `deploy/cloud/platform/`) | Metrics and alerts show service health, resource pressure and database problems |
| 12 | Module of choice: multi-source ingestion pipeline | Major | 2 | tbogus, yhruda | `backend/app/ingestion/` ([INGESTION.md](docs/INGESTION.md)) | See below |
| 13 | Health check & status page + backups/DR | Minor | 1 | dstefans, tbogus | `/status` page over `/health` + `/ready`; `make do-db-backup` / `do-db-restore`; [DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) | Service health is visible and data is recoverable |
| | **Total** | | **20** | | | |

How two of them are counted:

- **#1 is one Major.** The subject's separate frontend and backend framework Minors are alternatives
  to it, so #1 is worth 2 points, not 2 + 1 + 1.
- **#7 and #8 are two modules shown separately**, though both run in `/search`: #8 is the prompt →
  Haiku structured output → Sonnet streaming into SSE with its degradation ladder
  ([SEARCH.md](docs/SEARCH.md) §5); #7 is the catalog as the dataset, hybrid retrieval as the context
  step ([ALGORITHMS.md](docs/ALGORITHMS.md) §4), and blurbs limited to retrieved cards.

### Module of choice: multi-source ingestion pipeline (Major)

**Why we chose it.** A "what to do in Warsaw tonight" engine is useless if half the concerts are
missing or one museum shows up three times. No single source covers events and places, so the
catalog is built from four ([INGESTION.md](docs/INGESTION.md) §3): OpenStreetMap enriched with
Wikidata, Facebook events through Apify, the Ticketmaster Discovery API, and keyless demo fixtures.

**Technical challenges it addresses.**

- **Four heterogeneous sources, one contract.** Each source implements `fetch() -> list[RawItem]`;
  normalisation, dedup, embedding and upsert are shared, so a fifth source is one adapter class,
  one registry line and one CronJob (§2, §5).
- **Three-tier cross-source deduplication** (§4.3). Candidates are blocked, then scored with
  rapidfuzz: ≥ 90 is the same entity, < 75 is not, and only the 75–89 band goes to Claude Haiku.
  Without an Anthropic key that band counts as "no match". Dedup runs before embedding, so
  duplicates are never embedded.
- **Failure isolation** (§4.1–4.4). A source that is down aborts only its own run; a malformed
  record is skipped; a failed embedding batch of 16 is logged and the rest still get vectors.
- **The embedding-erasure trap** (§4.5). The upsert refreshes `embedding` only when this run computed
  one; otherwise a run without a Voyage key would set every vector to `NULL` and silently switch
  off semantic search.

**How it adds value.** Every search result comes out of this pipeline: it gives the RAG module (#7)
a real, current, de-duplicated catalog instead of a static seed, and runs unattended (Kubernetes
CronJobs in production, `make scheduler-up` locally).

**Why it deserves Major status.** It is a complete subsystem, not a feature of another module: a
pluggable adapter layer, a staged pipeline with per-stage failure handling, fuzzy and LLM-assisted
entity resolution, batched embedding, idempotent upserts keyed on `(source, source_url)`, and
scheduled execution in two environments, documented end to end in [INGESTION.md](docs/INGESTION.md).

## Individual contributions

Commit hashes point to concrete work merged into `main`; review and integration were shared.

### Tomasz (`tbogus`) — modules #1, #2, #4–#9, #12, #13

- **Built:** the FastAPI backend and initial catalog/intent scaffold (`0a9824f`), real source adapters
  (`768c36e`, `072e799`), Voyage vector search (`4b84257`), streamed LLM re-ranking (`854f295`,
  `9eb4c1b`), email verification, profile editing, avatar removal and upload progress, security
  tests, the profile UI, the shared SVG icons and Spinner (`1cec7fe`), and the architecture deep dives.
- **Challenges:** one account reachable by both password and Google sign-in — a previously
  registered password is invalidated once Google proves ownership (`cd125d3`); database access
  hardened with a least-privilege role and Row-Level Security (`cffd7e3`, `601de02`).

### Yurii (`yhruda`) — modules #1, #2, #5–#9, #12

- **Built:** ingestion deduplication (`a2bebd4`), Google OAuth (`af78cd5`), password authentication
  (`60170fd`), saved-items APIs (`4734b9b`), Redis search quotas (`4e28e38`), lexical/vector
  retrieval fusion (`7a40cb6`), avatar uploads, presence, integration tests and intent-prompt
  improvements (`4406d28`, `4193b08`, `2454efb`, `3aff639`).
- **Challenges:** vector recall dropped under selective filters — tuned HNSW search and enabled
  iterative scans (`16799f2`); search had to stay useful when external AI services fail — added
  raw-text, lexical and retrieval-order fallbacks (`5ce2bee`).

### Dawid (`dstefans`) — modules #1–#5, #13

- **Built:** the Next.js streaming-search frontend and visual system (`58b548c`), account and
  saved-item screens (`bff85d8`, `c050acb`), upcoming-event browsing (`cd4d5f2`), friends and
  sharing across API and UI (`a74860f`), verification UX, online-status indicators, server-rendered
  item pages and privacy/terms pages (`7427c47`, `84faf97`, `717d564`, `fff2210`).
- **Challenges:** repeated keyboard submissions fired duplicate searches — the submit handler now
  ignores in-flight and unchanged requests but still allows retries (`544b31a`); cards broke when
  remote images were unavailable — added image placeholders (`5690fc5`).

### Yaroslav (`yashevch`) — modules #10, #11, deployment for #1 and #12

- **Built:** the production platform and its tooling — DigitalOcean Kubernetes and managed Postgres
  (`263a46d`), container images with immutable SHA tags (`fde52fb`, `1d73743`), ELK logging and
  monitoring, the full local observability stack (`ca1116b`), protected monitoring UIs (`01f62e6`),
  local scheduled ingestion (`13fe9ec`) and the deployment guides; integrated teammates' changes
  into `main`.
- **Challenges:** container networking vs Next.js build-time rewrites — the backend URL is now a
  build argument (`026690e`); cloud logs and dashboards were unreachable — allowed the pod subnet
  through the ELK firewall (`fa4b780`) and bound Kibana to the container interface (`102ee4e`).

## Resources

- [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/),
  [Next.js](https://nextjs.org/docs), [Tailwind CSS](https://tailwindcss.com/docs)
- [pgvector](https://github.com/pgvector/pgvector), [PostgreSQL pg_trgm](https://www.postgresql.org/docs/16/pgtrgm.html)
- [Anthropic API](https://docs.anthropic.com/), [Voyage AI embeddings](https://docs.voyageai.com/)
- Data sources: [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API),
  [Wikidata](https://www.wikidata.org/), [Ticketmaster Discovery API](https://developer.ticketmaster.com/),
  [Apify](https://apify.com/)
- [Lucide](https://lucide.dev/) — source of the SVG icon paths (ISC licence)
- [DigitalOcean Kubernetes](https://docs.digitalocean.com/products/kubernetes/),
  [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack),
  [Elastic Stack](https://www.elastic.co/guide/)

### How AI was used

OpenAI Codex and Claude Code were used as development assistants for repetitive and
time-consuming tasks: refactoring, debugging, writing tests, code review and documentation,
mainly in the backend and the docs. All generated content was reviewed, tested and
understood by the team member who submitted it, and peer-reviewed in a pull request.

**As part of the product:** Claude Haiku parses prompts, Claude Sonnet re-ranks and writes the card
blurbs, and Claude Haiku adjudicates ambiguous duplicates during ingestion.

## Repository layout and documentation

| Path | What |
|---|---|
| `backend/` | FastAPI app — API, LLM layer, retrieval, ingestion |
| `frontend/` | Next.js UI ([docs/frontend.md](docs/frontend.md)) |
| `deploy/local/` | **The stack used to run and evaluate the project** ([guide](deploy/local/README.md)) |
| `deploy/cloud/` | Optional cloud deployment (Terraform, k8s, Ansible, Helm) — not needed to run or grade |
| `docs/` | Reference docs and deep dives, below |

- Reference: [architecture](docs/architecture.md), [data model](docs/data-model.md),
  [auth & profiles](docs/auth.md), [local development](docs/local-development.md),
  [API keys](docs/api-keys.md), [ORM](docs/ORM.md), [deployment](docs/deployment.md),
  [hosting on DigitalOcean](docs/hosting-digitalocean.md), [disaster recovery](docs/DISASTER_RECOVERY.md)
- Deep dives: [ALGORITHMS](docs/ALGORITHMS.md) (intent, embeddings, retrieval, RRF, re-rank, dedup),
  [SEARCH](docs/SEARCH.md) (one `/search` request end to end), [INGESTION](docs/INGESTION.md)
  (adapters, sources, pipeline), [SECURITY](docs/SECURITY.md) (identity, sessions, RLS, rate limits,
  uploads, secrets), [MODULES](docs/MODULES.md) (module inventory and risks)
