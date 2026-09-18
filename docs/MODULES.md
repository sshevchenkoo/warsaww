# MODULES.md — what we can claim, what it is worth, and what is one step away

Scored against the **ft_transcendence subject v21.1**, section IV: 14 points required, Major = 2,
Minor = 1.

The rule that shapes this whole document is the subject's own:

> During evaluation: You will be asked to demonstrate each claimed module. Only fully functional and
> properly implemented modules will be counted toward your final score. **Non-functional or
> incomplete modules = 0 points.**

So a module is listed as claimable here only if every bullet in its subject description is met by
code that exists on `main` today. "Almost" is worth zero, and is therefore in §3 rather than §1.

---

## 1. Claimable today — 14 points

| # | Module | Category | Type | Pts | Evidence |
|---|---|---|---|---|---|
| 1 | Framework for both frontend and backend | Web | Major | 2 | Next.js 16 App Router (`frontend/`) + FastAPI (`backend/app/`) |
| 2 | Use an ORM | Web | Minor | 1 | SQLAlchemy 2 typed models, `backend/app/catalog/models.py` |
| 3 | Server-Side Rendering | Web | Minor | 1 | `/item/[id]` renders server-side with metadata (`ƒ` in the build output) |
| 4 | Custom design system | Web | Minor | 1 | 13 reusable components + palette/typography tokens in `globals.css` |
| 5 | OAuth 2.0 remote authentication | User Management | Minor | 1 | Google OIDC via authlib, `backend/app/auth/oauth.py` |
| 6 | Complete RAG system | AI | Major | 2 | Voyage embeddings + pgvector/pg_trgm hybrid retrieval → grounded blurbs |
| 7 | Complete LLM system interface | AI | Major | 2 | Intent + re-rank, SSE streaming, error handling, rate limiting |
| 8 | ELK log management | DevOps | Major | 2 | Elasticsearch + Logstash + Kibana, Fluent Bit shipping, ILM retention, basic auth |
| 9 | Prometheus + Grafana monitoring | DevOps | Major | 2 | kube-prometheus-stack, 3 exporters, 2 dashboards on the cluster (3 in the local stack), 13 alert rules, password-protected |
| | **Total** | | | **14** | |

**14 is exactly the pass mark, with zero margin.** The subject says it plainly: *"aiming for more than
14 points in total may be a good idea, especially if some modules aren't validated during the
evaluation."* One rejected module and the project fails. §3 is therefore not optional polish — it is
the safety margin.

### Notes on the riskier claims in that table

**#1 excludes the two framework Minors.** The subject lists "frontend framework" and "backend
framework" as separate Minors *and* "both" as a Major. They are alternatives, not additive: claiming
the Major is 2 points, not 2 + 1 + 1.

**#4 (design system) is the weakest of the nine.** The subject asks for "a proper color palette,
typography, and icons (minimum: 10 reusable components)". We have 13 components
(`EventCard`, `UserCard`, `Header`, `Footer`, `ShareButton`, `ItemActions`, `ItemImage`,
`VerifyPanel`, `UserContext`, `Avatar`, `SectionHeading`, `EmptyState`, `CardSkeleton`), a documented
palette that re-skins the app from one token, and a two-face type system (Geist Sans + Geist Mono).
What we do **not** have is an icon set — the UI uses text glyphs (`♡ → ✕`). An evaluator who reads
"icons" strictly can reject this. **Without #4 the total is 13, i.e. a fail.** Adding a small SVG icon
set is a couple of hours and removes the single biggest risk on the board.

**#6 and #7 may be read as one system.** They are separate modules in the subject, and we implement
both, but both run inside `/search`. Demo them as two things:

- **LLM interface (#7):** prompt → Haiku structured output; Sonnet streaming token by token into SSE;
  the degradation ladder in [SEARCH.md](SEARCH.md) §5; the per-session daily quota.
- **RAG (#6):** the catalog as the dataset (`items` + 1024-dim vectors); hybrid retrieval as the
  context step ([ALGORITHMS.md](ALGORITHMS.md) §4); blurbs grounded in the retrieved cards, with the
  re-ranker structurally unable to invent one (`items[n-1]`).

---

## 2. What is definitively out

Not "not yet" — these conflict with what the project is, and chasing them would mean building a
different product.

| Category | Why |
|---|---|
| All Gaming modules (game, remote players, multiplayer 3+, second game, 3D, tournament, spectator, game customization) | No game, and none is planned. This also blocks the two modules that depend on one: Game statistics, AI Opponent. |
| Backend as microservices (DevOps, Major) | A deliberate architectural decision in the opposite direction — see [architecture.md](architecture.md): "We deliberately do not run a microservice per source." |
| Blockchain (both) | No blockchain, and the ICP Minor is explicitly incompatible with SSR, which we claim. |
| WAF/ModSecurity + HashiCorp Vault (Cybersecurity, Major) | Ingress is plain nginx; secrets are Kubernetes Secrets. |
| Advanced permissions / roles, Organization system (User Mgmt, Major ×2) | No role model; every account is an equal user. |
| Recommendation system using ML (AI, Major) | Ranking is query-driven, not behaviour-driven. Nothing personalises on saved items. |
| Advanced analytics dashboard (Data, Major) | Grafana would be the artifact, and it is already the evidence for module #9. Claiming the same dashboards twice invites both claims to be rejected. |

---

## 3. One step away — the margin, cheapest first

Each of these is mostly built. The column that matters is the last one.

| Module | Type | Pts | What exists | What is missing |
|---|---|---|---|---|
| **Custom module: ingestion pipeline** | Major | +2 | Four adapters, cross-source dedup (blocking → rapidfuzz → LLM adjudication), embedding, upsert — all documented in [INGESTION.md](INGESTION.md) | **Only the README justification.** The subject requires, in `README.md`: why this module, what technical challenges it addresses, how it adds value, why it deserves Major status. The code is done. This is the cheapest 2 points available. |
| **Standard user management** | Major | +2 | Avatar upload with default fallback, friends with online status, profile page — [SECURITY.md](SECURITY.md) §2 | One bullet: *"Users can update their profile information."* There is no `PATCH /me` — name and email cannot be edited. One endpoint plus a form. |
| **2FA** | Minor | +1 | Email verification by 6-digit code: HMAC-stored, expiry, attempt cap ([SECURITY.md](SECURITY.md) §3) | It runs at registration, not at login, so it is verification rather than a second factor. Reuse the same code path as a step in `/auth/login` for password accounts. |
| **File upload and management** | Minor | +1 | Multi-format accept, client + server validation, decompression-bomb guard, `DELETE /me/avatar` | Two bullets: a real progress indicator (we show `…`), and a delete control in the UI — the endpoint exists but nothing calls it. |
| **Advanced search** | Minor | +1 | Filters already derived from the prompt and applied in SQL ([ALGORITHMS.md](ALGORITHMS.md) §4.4) | The module means *user-facing*: filter controls, a sort option, pagination. The backend is ready; this is UI. |
| **GDPR compliance** | Minor | +1 | Privacy Policy and Terms pages | All four functional bullets: request your data, delete with confirmation, export in a readable format, confirmation emails. Note the Terms page already promises account deletion "from your profile" — which does not exist. That is a live inconsistency, not just a missing module. |
| **Health check + backups + DR** | Minor | +1 | `GET /health` returns a static `ok` with no DB round-trip (`api/routes.py`); both k8s probes point at it | A readiness check that actually queries the DB, a status page, automated backups, and a written disaster-recovery procedure. DO managed Postgres does daily backups + 7-day PITR by default, but nothing in `Makefile`, `docs/` or Terraform names it, and nothing covers restore. |
| **Multiple languages (3+)** | Minor | +1 | The product is already multilingual where it counts: prompts in RU/PL/EN, blurbs returned in the user's language | The **UI chrome** is English-only. Needs an i18n system, three complete translations, and a switcher. |
| **Public API** | Major | +2 | 32 endpoints, rate limiting, auto-generated docs at `/docs` | An API-key auth path (today: session cookies only) and a `PUT` endpoint — the subject names `PUT /api/{something}` explicitly and we have zero PUT/PATCH routes. |
| **User interaction (chat/profile/friends)** | Major | +2 | Profile system ✅, friends system ✅ | A basic chat. There is no chat anywhere in the codebase. Sharing an item with a message is not one. |

### The recommended path to a safe score

| Step | Module | Effort | Running total |
|---|---|---|---|
| 0 | — | — | 14 |
| 1 | Write the custom-module justification in `README.md` | ~1 h | **16** |
| 2 | `PATCH /me` + a name field on the profile page | ~2 h | **18** |
| 3 | An icon set, to de-risk the design system Minor | ~2 h | 18 (protects 1) |
| 4 | Avatar delete button + upload progress | ~1 h | **19** |
| 5 | 2FA at login, reusing the existing code path | ~3 h | **20** |

Roughly a day's work takes the project from "exactly at the line" to six points of margin — enough to
survive two rejected modules.

---

## 4. Where this has to be written down

The subject requires the module list in `README.md`, not here:

> **Modules:** List of all chosen modules (Major and Minor). Justification for each module choice,
> especially for custom "Modules of choice". How each module was implemented.

This file is the working document — the honest inventory with the risks attached. The README gets the
final claimed list once the team agrees on it, and it must include a written justification for every
custom module, or that module scores zero regardless of how good the code is.
