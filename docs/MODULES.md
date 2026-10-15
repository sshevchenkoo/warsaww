# MODULES.md — what we claim, what it is worth, and what is held in reserve

Scored against the **ft_transcendence subject v21.1**, section IV: 14 points required, Major = 2,
Minor = 1, bonus capped at +5.

The rule that shapes this whole document is the subject's own:

> During evaluation: You will be asked to demonstrate each claimed module. Only fully functional and
> properly implemented modules will be counted toward your final score. **Non-functional or
> incomplete modules = 0 points.**

So a module is listed as claimed here only if every bullet in its subject description is met by
code that exists on `main` today. The claimed list is the one in [README.md](../README.md#modules);
this file is the working inventory behind it, with the risks attached.

---

## 1. Claimed — 20 points (19 count)

| # | Module | Category | Type | Pts | Evidence |
|---|---|---|---|---|---|
| 1 | Framework for both frontend and backend | Web | Major | 2 | Next.js 16 App Router (`frontend/`) + FastAPI (`backend/app/`) |
| 2 | Use an ORM | Web | Minor | 1 | SQLAlchemy 2 typed models, `backend/app/catalog/models.py` ([ORM.md](ORM.md)) |
| 3 | Server-Side Rendering | Web | Minor | 1 | `/item/[id]` renders server-side with metadata (`ƒ` in the build output) |
| 4 | Custom design system | Web | Minor | 1 | Palette/typography tokens in `globals.css`, 18 files in `frontend/src/components/`, SVG icon set + Spinner in `Icon.tsx` |
| 5 | Standard user management | User Management | Major | 2 | `PATCH /me` (name, email with code confirmation), avatar with default fallback, friends with online status, profile page |
| 6 | OAuth 2.0 remote authentication | User Management | Minor | 1 | Google OIDC via authlib, `backend/app/auth/oauth.py` |
| 7 | Complete RAG system | AI | Major | 2 | Voyage embeddings + pgvector/pg_trgm hybrid retrieval → grounded blurbs, `backend/app/retrieval/` |
| 8 | Complete LLM system interface | AI | Major | 2 | Intent + re-rank, SSE streaming, error handling, daily quota, `backend/app/llm/` |
| 9 | File upload and management | Web | Minor | 1 | PDF + image attachments on saved items (`/me/files`) and the avatar: client + server validation (type sniffed from bytes), owner-only access + RLS, thumbnail/PDF preview, upload progress, delete |
| 10 | ELK log management | DevOps | Major | 2 | Elasticsearch + Logstash + Kibana, Fluent Bit shipping, ILM retention + SLM snapshot archive, basic auth — demonstrated via `deploy/local/` |
| 11 | Prometheus + Grafana monitoring | DevOps | Major | 2 | Prometheus + Grafana + Alertmanager, 3 exporters, dashboards, alert rules, password-protected — demonstrated via `deploy/local/` |
| 12 | Custom module: multi-source ingestion pipeline | Module of choice | Major | 2 | `backend/app/ingestion/` ([INGESTION.md](INGESTION.md)); justification in the README |
| 13 | Health check & status page + backups/DR | DevOps | Minor | 1 | `/status` page over `/health` + `/ready`; nightly automated `pg_dump` (`db-backup` service) + `make stack-db-backup` / `stack-db-restore`; [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) |
| | **Total** | | | **20** | |

**7 Major × 2 + 6 Minor × 1 = 20 points.** The cap is 14 + 5 = 19, so one point is surplus:
the project still passes with any single Minor rejected, or with one Major rejected (18).

### Notes on the riskier claims in that table

**#1 excludes the two framework Minors.** The subject lists "frontend framework" and "backend
framework" as separate Minors *and* "both" as a Major. They are alternatives, not additive: claiming
the Major is 2 points, not 2 + 1 + 1.

**#4 (design system) no longer lacks icons.** The subject asks for "a proper color palette,
typography, and icons (minimum: 10 reusable components)". The UI used text glyphs (`♡ → ✕`) until
the shared SVG icon set in `Icon.tsx` replaced them; that was the biggest risk on the earlier
14-point board and it is closed.

**#7 and #8 may be read as one system.** They are separate modules in the subject, and we implement
both, but both run inside `/search`. Demo them as two things:

- **LLM interface (#8):** prompt → Haiku structured output; Sonnet streaming token by token into SSE;
  the degradation ladder in [SEARCH.md](SEARCH.md) §5; the per-session daily quota.
- **RAG (#7):** the catalog as the dataset (`items` + 1024-dim vectors); hybrid retrieval as the
  context step ([ALGORITHMS.md](ALGORITHMS.md) §4); blurbs grounded in the retrieved cards, with the
  re-ranker structurally unable to invent one (`items[n-1]`).

**#7, #8 and #12 need API keys to demo.** Without `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` search
and seeding stop at the `make stack-init` preflight. Check the keys before the evaluation, not during it.

---

## 2. Implemented, not claimed — the reserve

These are on `main` and look complete against the subject, but are left out of the README because
the 19-point cap is already reached. If a claimed module is rejected, one of these can replace it —
**walk through every subject bullet before claiming it.**

| Module | Type | Pts | What exists | Check before claiming |
|---|---|---|---|---|
| **2FA** | Minor | +1 | Opt-in two-factor sign-in for password accounts: toggle on the profile, a code emailed at login, `POST /auth/login/2fa` to finish (#58). Same HMAC-stored, expiring, attempt-capped code path as email verification ([SECURITY.md](SECURITY.md) §3) | Without `RESEND_API_KEY` the code is only logged, so the demo needs a working mail sender |
| **GDPR compliance** | Minor | +1 | `GET /me/export` (JSON download), `DELETE /me` confirmed by typing the email (and password), an "Account deleted" email, Privacy Policy and Terms that match (#49, #59) | "Confirmation emails" also has to cover data changes, not only deletion; the email-change code covers that, but say so in the demo |

---

## 3. What is definitively out

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
| Advanced analytics dashboard (Data, Major) | Grafana would be the artifact, and it is already the evidence for module #11. Claiming the same dashboards twice invites both claims to be rejected. |

---

## 4. Still one step away

Not needed for the score; listed so nobody rediscovers them from scratch.

| Module | Type | Pts | What exists | What is missing |
|---|---|---|---|---|
| **Advanced search** | Minor | +1 | Filters already derived from the prompt and applied in SQL ([ALGORITHMS.md](ALGORITHMS.md) §4.4) | The module means *user-facing*: filter controls, a sort option, pagination. The backend is ready; this is UI. |
| **Multiple languages (3+)** | Minor | +1 | Prompts in RU/PL/EN, blurbs returned in the user's language | The **UI chrome** is English-only. Needs an i18n system, three complete translations, and a switcher. |
| **Public API** | Major | +2 | 37 routes, rate limiting, auto-generated docs at `/docs`, `PATCH /me` | An API-key auth path (today: session cookies only) and a `PUT` endpoint — the subject names `PUT /api/{something}` explicitly. |
| **User interaction (chat/profile/friends)** | Major | +2 | Profile system ✅, friends system ✅ | A basic chat. There is no chat anywhere in the codebase. Sharing an item with a message is not one. |

---

## 5. Where this has to be written down

The subject requires the module list in `README.md`, not here:

> **Modules:** List of all chosen modules (Major and Minor). Justification for each module choice,
> especially for custom "Modules of choice". How each module was implemented.

The README holds the claimed list and the custom-module justification; this file is the inventory
behind it. When a module moves between §1 and §2, update both.
