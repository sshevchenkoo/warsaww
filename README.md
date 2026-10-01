*This project has been created as part of the 42 curriculum by tbogus, yhruda, dstefans, yashevch.*

# warsaw, — what now?

## Description

A prompt-based discovery engine for **events and places in Warsaw**. Type a
free-form vibe and get a ranked list of cards — concerts and parties alongside
castles, museums and parks — each with a one-line pitch written in your own
language. Users can save discoveries, manage their profile, add friends, and share
events. The catalog is refreshed through scheduled multi-source ingestion.

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

| Feature | What it does | Team member(s) |
|---|---|---|
| Prompt search in any language | Free-form prompt in RU / PL / EN; the intent model normalises it and the blurbs come back in the user's language | tbogus, yhruda |
| Hybrid retrieval | SQL filters (date, price, category) and pgvector similarity in one query | tbogus, yhruda |
| LLM re-ranking, streamed | Claude Sonnet drops irrelevant candidates, reorders the rest and writes a one-line pitch per card, streamed over SSE | tbogus, yhruda |
| Multi-source ingestion | Four source adapters, cross-source deduplication, scheduled runs (the custom module, see [Modules](#modules)) | tbogus, yhruda |
| Accounts | Email + password sign-up with a 6-digit verification code, Google sign-in, sessions; search is gated behind a verified email | yhruda, tbogus, dstefans |
| Profile | Hero with stats, inline edit of name and email (email change confirmed by code), avatar upload with progress and delete | tbogus, yhruda, dstefans |
| Friends and sharing | Friend requests, online status, public profiles, sharing a card with a friend, a "shared with you" inbox | dstefans, yhruda, tbogus |
| Saved items | Save a card with the heart; friends can see each other's saved lists | yhruda, dstefans |
| Shared UI components | Palette and type tokens, reusable components, shared SVG icons and loading spinners | dstefans, tbogus |
| Production platform | Terraform for DigitalOcean DOKS + managed Postgres + ELK droplet; Helm for ELK logging, Prometheus/Grafana/Tempo and TLS | yashevch |
| Local observability stack | The same monitoring and logging on a laptop behind a basic-auth gateway, plus scheduled ingestion | yashevch |

| Upcoming events and item details | Browse upcoming events without an LLM request; open server-rendered detail pages with metadata and image fallbacks | dstefans |
| Privacy and terms | Dedicated Privacy Policy and Terms of Service pages linked from the footer | dstefans |
| Search resilience and quotas | Redis-backed daily quotas, lexical fallback when embeddings fail, and fallback cards when re-ranking fails | yhruda, tbogus |

## Technical stack

| Layer | Tech | Why |
|---|---|---|
| Frontend | Next.js 16 (App Router), Tailwind v4, SSE | Server-rendered item pages for SEO and fast first paint; streaming results without WebSockets |
| Backend | FastAPI, SQLAlchemy 2, Pydantic | Async endpoints with SSE support, typed models end to end, validation from the same types |
| Data | PostgreSQL 16 + pgvector (HNSW), pg_trgm | Filters, vectors and fuzzy text in one database and one query, instead of a separate vector store |
| Rate limits | Redis 7 | Shared counters enforce search quotas and authentication rate limits across API requests |
| Authentication | Authlib, signed-cookie sessions, bcrypt, Resend | Google OIDC and password login share one account model; emailed codes prove ownership |
| LLM | Claude Haiku (intent), Claude Sonnet (re-rank), Anthropic SDK | A fast, cheap model for structured intent; a stronger one only for the final top 30 |
| Embeddings | Voyage `voyage-3.5` (multilingual, 1024-dim) | One multilingual model for both cards and queries, so RU / PL / EN prompts land in the same space |
| Ingestion | httpx adapters, rapidfuzz dedup, k8s CronJobs | Plain HTTP clients per source, fast fuzzy matching, one schedule per source so failures stay isolated |
| Platform | DigitalOcean DOKS, Terraform, managed Postgres, ELK, Prometheus/Grafana/Tempo | Managed Kubernetes and database keep ops small; infrastructure as code makes prod reproducible |

## Database schema

Events and places are one table, `items`, with a `kind` column. Everything a user owns hangs off
`users` with `ON DELETE CASCADE`. Full schema, indexes and Row-Level Security policies:
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

| Table | Holds |
|---|---|
| `items` | Events and places: name, description, category, dates, prices, coordinates, sources, 1024-dim embedding |
| `users` | Accounts: email, name, avatar, Google id or bcrypt password hash, verification code state, pending email, last seen |
| `saved_items` | A user's saved cards |
| `friendships` | Friend requests, directed until accepted |
| `shared_events` | A card sent from one user to another, with an optional message |
| `user_avatars` | Uploaded avatar bytes |
| `intent_logs` | Every parsed prompt with the extracted intent — analytics and a future fine-tuning set |

Key fields and types (PK = primary key; FK = foreign key):

| Table | Key fields and data types |
|---|---|
| `items` | `id uuid` PK; `kind text`; `name text`; `starts_at/ends_at timestamptz`; `price_from/price_to numeric`; `lat/lon float`; `sources/opening_hours jsonb`; `embedding vector(1024)` |
| `users` | `id uuid` PK; unique `email text` and `google_sub text`; `password_hash text`; `email_verified boolean`; `pending_email text`; `last_seen_at timestamptz` |
| `saved_items` | `id uuid` PK; `user_id uuid` FK to users; `item_id uuid` FK to items; unique `(user_id, item_id)` |
| `friendships` | `id uuid` PK; `requester_id/addressee_id uuid` FKs to users; `status text` constrained to pending/accepted |
| `shared_events` | `id uuid` PK; `from_user_id/to_user_id uuid` FKs to users; `item_id uuid` FK to items; `message text` |
| `user_avatars` | `user_id uuid` PK/FK to users; `data bytea`; `content_type text`; `updated_at timestamptz` |
| `intent_logs` | `id uuid` PK; `user_prompt text`; `intent jsonb`; `model text`; `latency_ms integer` |

A user can have many saves, friendships and shares, but at most one uploaded avatar.
An item can appear in many saves and shares. User and item foreign keys cascade on deletion;
`intent_logs` is independent of these relationships.

## Modules

Scored against the ft_transcendence subject v21.1, section IV (Major = 2 points, Minor = 1,
14 required). The chosen inventory totals 7 Major modules × 2 plus 5 Minor modules × 1
= **19 claimed points**, subject to demonstration and evaluator validation.
The SVG icon set and loading spinners are integrated into `main`.
[docs/MODULES.md](docs/MODULES.md) is an earlier 14-point assessment that predates
profile editing, avatar management and SVG icon integration; the table below is the
current module inventory.

| # | Module | Category | Type | Pts | Implemented by | Where |
|---|---|---|---|---|---|---|
| 1 | Framework for both frontend and backend | Web | Major | 2 | dstefans, yhruda, tbogus | Next.js 16 App Router in `frontend/`, FastAPI in `backend/app/` |
| 2 | Use an ORM | Web | Minor | 1 | yhruda, tbogus, dstefans | SQLAlchemy 2 typed models, `backend/app/catalog/models.py` ([ORM.md](docs/ORM.md)) |
| 3 | Server-Side Rendering | Web | Minor | 1 | dstefans | `/item/[id]` is rendered on the server with its own metadata, `frontend/src/app/item/[id]/page.tsx` |
| 4 | Custom design system | Web | Minor | 1 | dstefans, tbogus | Palette/type tokens in `frontend/src/app/globals.css`, 15 component files in `frontend/src/components/`, and shared SVG icons and Spinner in `frontend/src/components/Icon.tsx` |
| 5 | Standard user management | User Management | Major | 2 | tbogus, yhruda, dstefans | Profile edit (`PATCH /me`), avatar upload with a default, friends with online status — `backend/app/api/`, `frontend/src/app/profile/` |
| 6 | OAuth 2.0 remote authentication | User Management | Minor | 1 | yhruda, tbogus | Google OIDC via authlib, `backend/app/auth/oauth.py` |
| 7 | Complete RAG system | AI | Major | 2 | tbogus, yhruda | Voyage embeddings + pgvector/pg_trgm hybrid retrieval, blurbs grounded in the retrieved cards — `backend/app/retrieval/` |
| 8 | Complete LLM system interface | AI | Major | 2 | tbogus, yhruda | Intent extraction (Haiku) and re-rank (Sonnet) streamed over SSE, with error handling and a daily quota — `backend/app/llm/` |
| 9 | File upload and management | User Management | Minor | 1 | yhruda, tbogus | Avatar upload: type and size checks on both sides, upload progress, delete — `backend/app/api/avatars.py` |
| 10 | ELK log management | DevOps | Major | 2 | yashevch | Elasticsearch + Logstash + Kibana, Fluent Bit shipping, ILM retention — `deploy/cloud/ansible/`, `deploy/cloud/platform/` |
| 11 | Prometheus + Grafana monitoring | DevOps | Major | 2 | yashevch | kube-prometheus-stack, exporters, dashboards, alert rules — `deploy/cloud/platform/` |
| 12 | Custom module: multi-source ingestion pipeline | Module of choice | Major | 2 | tbogus, yhruda | `backend/app/ingestion/` ([INGESTION.md](docs/INGESTION.md)) — justified below |
| | **Total** | | | **19** | | |

### Why these modules were chosen

| Module | Reason for choosing it |
|---|---|
| #1 Frontend and backend frameworks | Next.js supports the browser experience and server rendering; FastAPI supports typed APIs and streaming search. |
| #2 ORM | Typed models and shared sessions keep catalog and account persistence consistent. |
| #3 Server-Side Rendering | Item links need useful content and metadata before client-side JavaScript runs. |
| #4 Design system | Shared tokens, icons and components keep search, profiles and social screens consistent. |
| #5 User management | Persistent profiles, saved discoveries and friends make the discovery service useful beyond a single search. |
| #6 OAuth | Google sign-in gives users an alternative to creating another password. |
| #7 RAG | Recommendations must be grounded in actual catalog entries, with real dates and locations. |
| #8 LLM interface | Free-form multilingual requests need intent extraction and readable, contextual result explanations. |
| #9 File management | Users need to upload, replace and remove profile pictures with bounded storage and validated content. |
| #10 ELK | Centralized searchable logs make API and ingestion failures diagnosable across containers. |
| #11 Monitoring | Metrics, dashboards and alerts reveal service health, resource pressure and database problems. |
| #12 Custom ingestion | A current, deduplicated catalog requires several incompatible sources; the detailed justification follows. |

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

## Team information

| Member | Login | Role | Responsibilities |
|---|---|---|---|
| Tomasz | `tbogus` | Product Owner, developer | Define product priorities and maintain the backlog; develop backend search, LLM integration, ingestion, authentication and security |
| Yurii | `yhruda` | Project Manager, developer | Coordinate task distribution, meetings, progress and blockers; develop retrieval, prompts, catalog, authentication and social features |
| Dawid | `dstefans` | Developer | Implement the frontend, shared UI components, SSR and social features; test and document those changes |
| Yaroslav | `yashevch` | Technical Lead, developer | Oversee architecture, technology choices, code quality and technical integration; develop Terraform, Kubernetes, ELK and monitoring infrastructure |

## Project management

- **Planning.** The remaining work was scored against the module list ([docs/MODULES.md](docs/MODULES.md))
  and split into GitHub issues #4–#28, grouped into waves (`wave-0` … `wave-4`). Each wave is a set
  of independent pull requests; each issue carries its estimate, the points it earns or protects,
  and what it depends on.
- **Labels.** `+2 pts` / `+1 pts` / `protects pts` for scoring, `backend` / `frontend` / `infra` for
  ownership, `needs-team-input` where a decision is the whole team's.
- **Code review.** Every change goes through a pull request into `main` with a description of what
  changed, how it was checked and what was not.
- **Communication.** The team coordinated through WhatsApp, meetings and asynchronous
  progress updates. Meetings were used to discuss work and blockers; asynchronous updates
  kept teammates informed between meetings.
- **Task distribution.** Work followed the responsibility areas above and was tracked in
  GitHub issues and pull requests. All four members contributed implementation work;
  ownership of individual features and modules is listed in the corresponding tables.

## Individual contributions

The implementation examples below come from commits merged into this checkout. Commit
hashes identify concrete contributions; review and integration work can be shared across roles.

### Tomasz (`tbogus`)

Built the FastAPI backend and initial catalog/intent scaffold (`0a9824f`), real source
adapters (`768c36e`, `072e799`), Voyage vector search (`4b84257`), and streamed LLM
re-ranking (`854f295`, `9eb4c1b`). Added email verification, profile editing, avatar
removal/upload progress, security tests, the profile UI and the architecture deep dives.
Added the shared SVG icon set and Spinner component (`1cec7fe`).
This work supports modules #1, #2, #4–#9 and #12. To handle account ownership securely
across password and Google sign-in, `cd125d3` invalidates a previously registered
password when Google proves ownership. Database hardening added least-privilege
access and Row-Level Security (`cffd7e3`, `601de02`).

### Yurii (`yhruda`)

Implemented ingestion deduplication (`a2bebd4`), Google OAuth (`af78cd5`), password
authentication (`60170fd`), saved-items APIs (`4734b9b`), Redis search quotas (`4e28e38`),
and lexical/vector retrieval fusion (`7a40cb6`). Added avatar uploads, presence,
integration tests and intent-prompt improvements (`4406d28`, `4193b08`, `2454efb`,
`3aff639`). These contributions support modules #1, #2, #5–#9 and #12. To maintain
vector recall under selective filters, `16799f2` tunes HNSW search and enables
iterative scans. To keep search useful when external AI services are unavailable,
`5ce2bee` adds raw-text, lexical and retrieval-order fallbacks.

### Dawid (`dstefans`)

Built the Next.js streaming-search frontend and visual system (`58b548c`), account
and saved-item screens (`bff85d8`, `c050acb`), upcoming-event browsing (`cd4d5f2`),
and friends/sharing across both the API and UI (`a74860f`). Added verification UX,
online-status indicators, server-rendered item pages, and privacy/terms pages
(`7427c47`, `84faf97`, `717d564`, `fff2210`). This work supports modules #1–#5,
including social SQLAlchemy models, the design system and SSR. To handle repeated
keyboard submissions efficiently, `544b31a` guards the submit handler against
in-flight and unchanged requests while preserving retries. Image placeholders keep
cards readable when remote images are unavailable (`5690fc5`).

### Yaroslav (`yashevch`)

As Technical Lead and infrastructure developer, built the production platform and
its deployment tooling: DigitalOcean Kubernetes and managed Postgres (`263a46d`),
CI/CD and immutable image tags (`fde52fb`, `1d73743`), ELK logging and monitoring,
and the full local observability stack (`ca1116b`). Added protected monitoring UIs
(`01f62e6`), local scheduled ingestion (`13fe9ec`), and deployment guides. His work
implements modules #10 and #11 and provides deployment/scheduling support for #1
and #12. To align container networking with Next.js build-time rewrites, `026690e`
passes the backend URL as a build argument. Cloud log delivery and dashboard access
were configured by allowing the pod subnet through the ELK firewall (`fa4b780`) and
binding Kibana to the container interface (`102ee4e`). Merge commits document integration of
teammates' changes into `main`.

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

## Instructions

### Prerequisites

- Git, a running Docker Engine/Desktop with Compose v2.24+, GNU `make`, and `curl`.
- On Linux, Elasticsearch needs `vm.max_map_count` of at least 262144; setup commands
  are in [local prerequisites](deploy/local/README.md#prerequisites).
- About 4–6 GB of free RAM for the full stack (app + monitoring + ELK).
- Node.js 20.9+ only if you run the frontend outside Docker (`make web`).

### Environment

From the repository root, configure the backend before starting containers.
Copy the template: `cp backend/.env.example backend/.env`. Replace the sample
`ANTHROPIC_API_KEY=sk-ant-...` with a real key, or leave it empty for a keyless demo.
Add the optional variables below as needed. With no API keys, `make stack-init` loads
demo fixtures and pre-verified test users; semantic search and LLM features need their keys:

| Variable | Needed for |
|---|---|
| `ANTHROPIC_API_KEY` | Intent extraction, re-ranking, dedup adjudication |
| `VOYAGE_API_KEY` | Embeddings (semantic search) |
| `SESSION_SECRET` | Signing session cookies and verification codes; at least 32 characters in production |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in |
| `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO` | Verification emails; no mail is sent without `RESEND_API_KEY`; `EMAIL_FROM` must use a verified sender, and `EMAIL_REPLY_TO` is optional |
| `APIFY_TOKEN`, `TICKETMASTER_API_KEY` | The Facebook-events and Ticketmaster ingestion sources |

### Run

From the repo root:

```bash
make infra-auth AUTH_USER=admin AUTH_PASS='replace-with-your-password'   # once: login for Grafana/Kibana/Prometheus
make stack-init   # build + start everything, load 100 demo events and two test users
```

Then open http://localhost:3000 and sign in as `user1@test.com` / `1234`. Grafana is on
http://localhost:3001, Kibana on :5601, Prometheus on :9090.

| Command | What |
|---|---|
| `make stack-seed` | Load fixtures, OpenStreetMap/Wikidata places, and Facebook events (Facebook needs `APIFY_TOKEN`) |
| `make scheduler-up` | Run ingestion on the same schedule as the cloud CronJobs |
| `make stack-down` | Stop everything (data volumes are kept) |
| `make app-up` + `make web` | Lighter setup: API, Postgres and Redis only, frontend on the host |
| `make help` | Every target |

Full local stack guide: [deploy/local/README.md](deploy/local/README.md).
Cloud deployment overview: [deploy/cloud/README.md](deploy/cloud/README.md).

Manual commands and tests: [docs/local-development.md](docs/local-development.md). Production on
DigitalOcean DOKS: [docs/deployment.md](docs/deployment.md) and
[docs/hosting-digitalocean.md](docs/hosting-digitalocean.md).

## Resources

- [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/),
  [Next.js](https://nextjs.org/docs), [Tailwind CSS](https://tailwindcss.com/docs)
- [pgvector](https://github.com/pgvector/pgvector), [PostgreSQL pg_trgm](https://www.postgresql.org/docs/16/pgtrgm.html)
- [Anthropic API](https://docs.anthropic.com/), [Voyage AI embeddings](https://docs.voyageai.com/)
- Data sources: [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API),
  [Wikidata](https://www.wikidata.org/), [Ticketmaster Discovery API](https://developer.ticketmaster.com/),
  [Apify](https://apify.com/)
- [Lucide](https://lucide.dev/) — source of the integrated SVG icon paths (ISC licence)
- [DigitalOcean Kubernetes](https://docs.digitalocean.com/products/kubernetes/),
  [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack),
  [Elastic Stack](https://www.elastic.co/guide/)

### How AI was used

OpenAI Codex was used during development for code refactoring, education and guides.
It assisted with restructuring existing project code, explaining implementation concepts
and preparing guidance for understanding and working on the project.

AI is part of the product: Claude Haiku parses prompts, Claude Sonnet re-ranks and writes the card
blurbs, and Claude Haiku adjudicates ambiguous duplicates during ingestion.

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
| [MODULES](docs/MODULES.md) | Historical module assessment and planning risks; current inventory is in Modules above |
