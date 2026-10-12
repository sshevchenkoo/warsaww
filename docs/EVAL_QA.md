# Evaluation Q&A — likely evaluator questions, with answers

Prep sheet for the ft_transcendence evaluation. Each answer is short enough to say out loud, followed
by **Show:** — what to open or run while saying it. ★ = asked at almost every evaluation.

`STACK` = `docker compose -f deploy/local/docker-compose.yml`. Deep dives behind the answers:
[SECURITY.md](SECURITY.md), [SEARCH.md](SEARCH.md), [ALGORITHMS.md](ALGORITHMS.md),
[INGESTION.md](INGESTION.md), [ORM.md](ORM.md), [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).

---

## A. Setup and general rules

### 1. ★ Start it from a clean clone with one command. What does `make stack-init` do?
`make stack-init` runs `stack-up` and then seeds data. `stack-up`:
1. generates the infra login on first run (`admin` + random password, printed once) into the
   gitignored `.htpasswd` and `secrets.env`;
2. generates a self-signed TLS cert (`make local-tls`, openssl, CN=localhost) if there isn't one;
3. `docker compose up -d --build` for the whole stack.

Then `stack-init` loads the 100 `[TEST]` demo events (`--source=fixtures`, no API key needed) and two
pre-verified users, `user1@test.com` / `user2@test.com` (password `1234`).

**Show:** `Makefile` targets `stack-up`, `stack-init`; then `$STACK ps`.

### 2. Which containers run, and why is each one needed?
17 services in one Compose project, one private network:
- **App:** `nginx` (HTTPS front), `web` (Next.js), `api` (FastAPI), `db` (Postgres 16 + pgvector),
  `redis` (rate limits).
- **Metrics:** `prometheus`, `alertmanager`, `grafana`, `postgres-exporter`, `node-exporter`.
- **Traces:** `otel-collector`, `tempo`.
- **Logs:** `fluent-bit`, `logstash`, `elasticsearch`, `kibana`.
- **Scheduler:** `ofelia` (opt-in, runs ingestion on a cron like the cloud CronJobs).

**Show:** the table in `deploy/local/README.md`.

### 3. ★ Where are the secrets? Prove nothing is in git.
API keys live in `backend/.env` (gitignored, `.env.example` is committed as a template). The infra
login is in `deploy/local/.htpasswd` + `secrets.env`, both generated and gitignored. The API refuses
to boot in production mode with the default or a short (<32 chars) session secret, or with a `*`
CORS origin (`backend/app/config.py`).

**Show:** `git ls-files | grep -E '(^|/)\.env$|secrets\.env|\.htpasswd|\.dump$'` prints nothing.

### 4. ★ Is everything HTTPS? Where does the cert come from?
Yes. nginx terminates TLS on 443 with a self-signed cert from `make local-tls`. Port 80 only does
`return 301 https://…`. Grafana, Kibana, Prometheus and Alertmanager are also served only through
nginx over HTTPS (3001/5601/9090/9093). The `web`, `api`, `db` and `redis` containers publish **no
host port**, so the browser can't reach anything over plain HTTP. Hops inside the Docker network are
plain HTTP, which the subject allows.

**Show:** `deploy/local/nginx/nginx.conf`; `curl -I http://localhost` → 301.

### 5. ★ Any console errors or warnings?
There should be none on any page. Check with DevTools open on every page (EVAL_CHECKLIST §2) the day
before.

**Show:** DevTools → Console while clicking through home, search, item, profile, people, status.

### 6. Privacy Policy and Terms — do they describe the real app?
Yes. Both are linked from the footer (`/privacy`, `/terms`) and were updated with the GDPR work: they
describe what data we keep (account, saves, friendships, shares), data export and account deletion.

**Show:** footer → both pages.

### 7. ★ Two users at the same time
Firefox normal window as `user1`, private window as `user2`. Sessions are separate signed cookies, so
both work in parallel. Good demo: user1 sends a friend request, user2 accepts, both see each other
online.

### 8. ★ Where is input validated?
On **both** sides.
- **Frontend:** `type="email"`, `required`, `minLength={8}` on the sign-up form; the avatar picker
  accepts only `image/png,jpeg,webp,gif`.
- **Backend:** Pydantic models are the real boundary. `EmailStr`, password `min_length=8` /
  `max_length=72`, search prompt 1–2000 chars, name ≤ 100, user search `q` 2–100 chars. A bad
  request gets a 422 with details.

**Show:** DevTools → Network: send a short password (or remove `minLength` in the inspector) → API
answers 4xx.

> If asked "why is the test password `1234` then?": the seed script writes the users straight to the
> DB for testing. They never go through `/auth/register`, which would reject it.

### 9. How are passwords stored?
bcrypt with a per-hash salt (`bcrypt.gensalt()`). The salt makes identical passwords produce
different hashes and kills rainbow tables. bcrypt is deliberately slow, so brute force is expensive.
It reads only the first 72 bytes, so longer passwords are **rejected** rather than silently
truncated. Login returns the same message for an unknown email and a wrong password, so it can't be
used to check which emails are registered.

**Show:** `backend/app/auth/passwords.py`.

### 10. SQL injection, XSS, CSRF?
- **SQLi:** every query goes through SQLAlchemy with bound parameters. The one place that
  interpolates (`SET LOCAL hnsw.iterative_scan`) checks the value against a whitelist first. User
  search escapes `%` and `_` in LIKE patterns.
- **XSS:** React escapes all text. There is no `dangerouslySetInnerHTML` on content.
- **CSRF:** the session cookie is `SameSite=Lax`, and state-changing endpoints are POST/PATCH/DELETE
  with JSON bodies. There is no CSRF token; say so if asked (SECURITY.md §11).
- **Extra layer:** Postgres Row-Level Security on `friendships`, `shared_events`, `saved_items`.

---

## B. Team, README, process

### 11. ★ What did you personally build? (Tomasz / `tbogus`)
Product Owner + developer. I built:
- the FastAPI backend scaffold and catalog/intent;
- the real source adapters, Voyage vector search, and the streamed LLM re-ranking (SSE);
- email verification by code, profile editing, avatar remove + upload progress;
- security work: the OAuth pre-hijacking fix (`cd125d3`), least-privilege DB role and RLS
  (`cffd7e3`, `601de02`), and security tests;
- the SVG icon set + Spinner, and the architecture deep-dive docs.

That covers modules #1, #2, #4–#9, #12.

*(Each teammate should prepare their own version from README → "Individual contributions".)*

### 12. Roles
- Tomasz: Product Owner (priorities, backlog).
- Yurii: Project Manager (task split, meetings, blockers).
- Yaroslav: Technical Lead (architecture, code quality, infra).
- Dawid: developer (frontend, design system, SSR).

All four wrote code.

### 13. How did you organise the work?
GitHub issues #4–#28, grouped into waves (`wave-0`…`wave-4`) of independent PRs. Labels: points
(`+2 pts`, `+1 pts`, `protects pts`), ownership (`backend`/`frontend`/`infra`), and
`needs-team-input`. Every change went through a PR into `main` with a description of what changed
and how it was tested. Communication happened on WhatsApp, in meetings, and through async updates.

### 14. ★ How did you use AI, and how did you check its output?
Two different things:
- **In development:** AI coding assistants (README names OpenAI Codex) for refactoring, explaining
  concepts and writing guides.
- **In the product:** Claude Haiku (intent + dedup adjudication) and Claude Sonnet (re-rank +
  blurbs).

Every change still went through a PR, review and tests. We can explain every line we merged.

*(Adjust if you also used other tools — be honest, evaluators check whether you understand the
code.)*

### 15. ★ Random file → the author explains it
Prepare one file each that you can walk through without notes. For Tomasz, good choices:
`backend/app/llm/rerank.py`, `backend/app/api/routes.py` (`/search`),
`backend/app/ingestion/pipeline.py`.

### 16. Why this idea? Who is the user?
Anyone in Warsaw (residents, students, tourists) asking "what can I do tonight?". The answer is
spread over Facebook, Ticketmaster and maps, in several languages. You type a vibe in your own
language and get grounded, ranked cards with a one-line pitch.

---

## C. Architecture

### 17. ★ The request path
Browser → **nginx** (TLS, :443) → **web** (Next.js) → Next.js rewrites proxy `/search`, `/auth`,
`/me`… to **api** (FastAPI :8000, internal only) → **Postgres** (data + vectors) and **Redis**
(quotas). Because the browser only ever talks to one origin, the session cookie is first-party and
no CORS is needed.

### 18. Why a modular monolith and not microservices?
Four people, one deployable. Modules (`api`, `auth`, `llm`, `retrieval`, `catalog`, `ingestion`) are
separate packages with clear boundaries, but there's no network hop or distributed transaction
between them. Ingestion already runs as a separate process (same image, different command), which
is the one place isolation matters.

### 19. ★ What happens when I type a search prompt?
1. `POST /search` with the prompt. The gate checks you're signed in (401) and verified (403).
2. Redis `INCR` on the daily quota → 429 when it runs out.
3. **Claude Haiku** turns the prompt into a typed `Intent` (categories, dates, budget, area,
   on-topic flag).
4. **Voyage** embeds the raw prompt (1024-dim vector).
5. A short DB transaction logs the intent and runs **one hybrid SQL query** (vector leg + trigram
   leg, fused with RRF) → top 30. The connection goes back to the pool here.
6. SSE stream: an `intent` event first. **Claude Sonnet** re-ranks the 30, drops the irrelevant ones
   and writes one line per card. Each `card` event is sent as soon as its line arrives. Then `done`.

### 20. Why SSE and not WebSockets?
Traffic is one-directional (server → browser) and per request. SSE is plain HTTP: it works through
nginx and the proxies, needs no extra protocol or connection state, and the stream ends when the
search ends. WebSockets would add a bidirectional channel we don't need. Detail: `EventSource` is
GET-only, so the client POSTs with `fetch` and parses the stream by hand
(`frontend/src/lib/api.ts`).

### 21. What is Redis used for?
Shared counters: the search quota (10/day per session) and the auth rate limit (10/min per IP). Keys
expire on their own. Both **fail open**: if Redis is down, requests are allowed, because these are
cost and abuse controls, not authorization. `/ready` reports Redis health.

### 22. How do sessions work? What if a cookie is stolen?
Starlette `SessionMiddleware`: a cookie **signed** with `SESSION_SECRET` that holds only the user id.
There is no server-side store, so any API replica can validate it. It can't be forged without the
secret. A stale or malformed cookie is cleared and returns 401. If a cookie is stolen, it works
until logout or expiry — that's the usual trade-off of stateless sessions. Mitigations: `HttpOnly`
(JS can't read it), `Secure` in production, `SameSite=Lax`, HTTPS only.

---

## D. Modules

### #1 Frameworks · #2 ORM · #3 SSR · #4 Design system

#### 23. Why Next.js + FastAPI? Server vs client components?
- **Next.js (App Router):** SSR for item pages, rewrites to proxy the API, and React for the
  interactive parts.
- **FastAPI:** typed endpoints from Pydantic models, automatic validation, easy SSE streaming.

**Server components** run on the server and send HTML; they can `await fetch` directly (the item
page). **Client components** (`"use client"`) run in the browser and can hold state and handle
clicks (search box, heart, profile form).

#### 24. ★ ORM: a model, a query, why an ORM, migrations, N+1?
Models are Python classes in `backend/app/catalog/models.py` (`Mapped[...]` = columns, `ForeignKey`
with `ondelete="CASCADE"`). One session per request (`get_session`). Commit means flush + COMMIT,
and an exception means everything rolls back together.

**Example:** `DELETE /me/avatar` is a bulk delete plus an attribute change on the user, committed as
one transaction (ORM.md §3).

**Why an ORM:** typed models shared by the API and ingestion, no hand-built SQL strings (so no
injection), and the identity map (`session.get` doesn't re-query).

**Migrations:** no Alembic. Locally the app runs `create_all` plus idempotent `ALTER … IF NOT EXISTS`
on startup (`main.py`). In production `DB_BOOTSTRAP=false` and schema changes are an admin step
(`make do-db-migrate`), because the runtime role can't do DDL.

**N+1:** list endpoints load in one query, e.g. `_my_statuses` reads all my friendships once instead
of once per found user.

#### 25. ★ Prove `/item/[id]` is server-rendered. SSR vs CSR vs SSG, hydration?
`frontend/src/app/item/[id]/page.tsx` is an async server component. It fetches `/items/{id}` on the
server (`revalidate: 60`) and `generateMetadata` sets the title and OG tags.

**Show:** `curl -sk https://localhost/item/<id> | grep -o '<title>[^<]*'` returns the event's title
with no JS. Or turn off JS in DevTools and reload.

- **SSR:** HTML built per request on the server.
- **CSR:** an empty shell that JS fills in.
- **SSG:** HTML built at build time.
- **Hydration:** React attaches event handlers to server-built HTML in the browser.

#### 26. Design system — tokens, components, consistency
- **Tokens:** palette and type as CSS variables in `frontend/src/app/globals.css`, used through
  Tailwind v4.
- **Components:** 18 shared files in `frontend/src/components/` (EventCard, Avatar, Header, Footer,
  EmptyState, CardSkeleton, SectionHeading, ShareButton, FriendActions, …).
- **Icons:** one `Icon.tsx` with SVG icons (Lucide paths) and a `Spinner`. No text glyphs.

Pages use the components rather than restyling, so a token change propagates everywhere.

### #5 User management · #6 OAuth · #9 File upload

#### 27. ★ Registration and email verification. Wrong/expired code? Brute force?
`POST /auth/register` → bcrypt hash → a 6-digit code is emailed (Resend). The code is generated with
`secrets.randbelow`, a CSPRNG.

The DB stores only `HMAC(session_secret, code)`, never the code, so a leaked DB can't be brute-forced
offline. Comparison is constant-time.

Guards on the code:
- **Expiry:** 15 minutes.
- **Attempts:** max 5 wrong tries.
- **Rate limit:** 10 auth requests per minute per IP (Redis).
- **Single use:** the code is cleared after it works.

Search is blocked until the email is verified (403), but browsing still works.

#### 28. How does online status work?
The frontend calls `POST /me/ping` on load and once a minute while the tab is open, which stamps
`users.last_seen_at = now()`. A user counts as **online if the last ping is < 2 minutes old**
(`ONLINE_WINDOW` in `api/social.py`). Close the window and they go offline within about 2 minutes.

#### 29. Friend requests: friending yourself? Duplicates?
`POST /friends/request/{id}`:
- yourself → **400** "Cannot friend yourself";
- unknown user → 404;
- already friends → **409**;
- you already sent one → **409**;
- *they* already asked you → it's accepted automatically (mutual).

Rows are directed (`requester` → `addressee`, `pending`/`accepted`) and RLS lets only the two
parties see a row.

#### 30. What happens to data when the account is deleted?
Every user-owned table has `ForeignKey("users.id", ondelete="CASCADE")`: saved items, friendships in
both directions, shared events sent and received, avatar. `session.delete(user)` removes it all in
one transaction. `intent_logs` has no user link at all.

#### 31. ★ OAuth 2.0 / OIDC flow, `state`, existing email?
1. `/auth/login/google` redirects to Google with `client_id`, `redirect_uri`, scope `openid email
   profile` and a random **`state`** stored in the session.
2. The user consents → Google redirects to `/auth/callback?code=…&state=…`.
3. authlib checks `state` matches, which blocks CSRF / login injection.
4. authlib exchanges the code server-to-server for tokens and validates the **ID token** (a signed
   JWT with `sub`, `email`, `email_verified`).
5. We upsert the user by email, store `google_sub`, and set the session cookie.

**Same email as a password account:** linked into one account, and the old password is **voided**.
Someone could have pre-registered your email with their password before you proved ownership
(account pre-hijacking).

A cancelled or failed callback redirects to `/login?error=oauth` instead of a 500.

#### 32. ★ Upload validation, size limit, why `bytea`?
- **Frontend:** `accept=` image types, a size check, and an upload progress bar from
  `XMLHttpRequest.upload.onprogress`. `fetch` has no upload progress, which is why XHR is used.
- **Backend:** never trusts extension or MIME. It reads at most 5 MB + 1 byte, so an oversized body
  is rejected without loading it all. Pillow then decodes the actual bytes, so a non-image fails.
  The pixel count is checked **before** decode (≤ 50 MP) to stop decompression bombs.
- **Re-encode:** centre-crop, resize to 256 px, save as JPEG. That also strips EXIF, including phone
  GPS.
- **Storage:** the result is ~20 KB, stored as `bytea` in its own `user_avatars` table. There's a DB
  `CHECK` (≤ 512 KB), no file storage to secure or back up separately, and it's deleted by the
  cascade.
- **Remove photo:** `DELETE /me/avatar` brings back the default avatar.

### #7 RAG

#### 33. ★ What is RAG? Where are R, A, G in the code?
Retrieval-Augmented Generation: the model answers from documents we retrieve, not from its own
memory.
- **R:** `backend/app/retrieval/search.py` — hybrid search over our catalog → top 30 cards.
- **A:** `backend/app/llm/rerank.py` — those 30 cards (description cut to 220 chars) are put into
  Sonnet's prompt as a numbered list.
- **G:** Sonnet picks and orders cards and writes one line each, only about the cards it was given.

The catalog (filled by our ingestion pipeline) is the knowledge base.

#### 34. ★ Embeddings, Voyage, 1024 dims, cosine, HNSW?
- **Embedding:** a vector where similar meaning means nearby points.
- **Voyage `voyage-3.5`:** multilingual (Claude has no embeddings endpoint). Cards are embedded as
  `document`, prompts as `query` (asymmetric mode).
- **1024 dims:** the model's output size, pinned in the `Item` model.
- **Cosine distance** (`<=>` in pgvector) compares direction, not length.
- **HNSW:** a graph index for *approximate* nearest-neighbour search. Fast, slightly inexact.
  - We set `ef_search=100` and `iterative_scan=relaxed_order`, so selective filters ("theatre,
    Saturday, < 50 PLN") don't starve the results.
  - Cut-off `distance ≤ 0.62`, so an unrelated query returns nothing instead of 30 bad cards.

#### 35. How are SQL filters + vectors + trigrams combined?
One SQL statement with two legs:
- **semantic:** pgvector cosine, HNSW, distance cut;
- **lexical:** `pg_trgm` `word_similarity` on the name, GIN index.

Both legs get the **same** filters (date, budget, category), each takes its top 50, and they are
fused with **Reciprocal Rank Fusion**: `score = Σ 1/(60 + rank)`. RRF uses ranks, not raw scores,
because cosine distance and trigram similarity aren't comparable. A card that both legs find
outranks a card only one leg likes.

The lexical leg exists for names and typos ("the weeknd") where vectors are weak.

#### 36. ★ How do you stop the model from making things up?
Structurally:
- Sonnet only gets the 30 retrieved cards, numbered.
- It returns `{"n": 7, "blurb": "…"}`, a **number**, not a name.
- We map `n` back to the object that came out of Postgres. An out-of-range or repeated `n` is
  dropped (`_parse_line`).
- Name, date, place, price and image always come from the DB row. The LLM writes only the one-line
  pitch and is told to use only the given card text.

**Show:** a card's date/price vs its item page.

#### 37. How does a Russian query match Polish data?
`voyage-3.5` is multilingual: "выставка" and "wystawa" land near each other in the same vector
space. Haiku also extracts categories and dates language-independently, and Sonnet is told to write
the blurb in the language of the query.

### #8 LLM interface

#### 38. Why two models?
- **Haiku** for intent: fast and cheap (~1 s), small structured output.
- **Sonnet** only for the final 30 cards: judgement and good writing.

Cost per search stays roughly constant whatever the catalog size, because the LLM is never the
index — Postgres narrows things down first.

#### 39. Structured output — show the intent schema
`backend/app/llm/schemas.py`:

```python
class Intent(BaseModel):
    on_topic: bool = True
    categories: list[str] = []
    date_from: str | None = None    # ISO 8601
    date_to: str | None = None
    budget_max: float | None = None # PLN
    area: str | None = None
    free_text: str = ""
```

It's called with `messages.parse(output_format=Intent)`, so we get a validated object instead of a
string to parse and hope. Today's date goes in the system prompt so "this Saturday" becomes real
dates.

#### 40. ★ Prompt injection ("ignore your instructions")?
The damage is bounded by design:
- The LLM has **no tools, no DB access, no secrets** in its context.
- Haiku's output must fit the `Intent` schema. The worst case is wrong filters or `on_topic=false`.
- Sonnet can only point at candidate numbers. Anything else is dropped by `_parse_line`, and cards
  still come from the DB.
- Prompts are capped at 2000 chars and the quota limits abuse.

The worst case is odd blurb text, rendered as escaped text by React.

#### 41. ★ LLM down / slow / out of quota — the degradation ladder
| What fails | What the user gets |
|---|---|
| Intent (timeout 15 s, error) | `Intent(free_text=prompt)`: search runs without structured filters |
| Voyage embedding | lexical-only retrieval |
| Re-rank, before any card | candidates in retrieval order, no blurbs |
| Re-rank, mid-stream | cards already shown stay, the rest follow in retrieval order |
| No Anthropic key | raw retrieval order (the keyless demo) |
| Redis down | quota fails open |
| Postgres down | 500, the only hard dependency |

Every stream ends with `done`, so the spinner never hangs.

#### 42. How is the 10-per-day quota enforced?
Redis key `ratelimit:search:{sid}:{YYYY-MM-DD}`, `INCR`. On the first hit, `EXPIRE` is set to
midnight Europe/Warsaw + 60 s. Over the limit → **429** with a clear message, which the frontend
shows as-is. It's a calendar day rather than a rolling 24 h, because users understand it.

**Show:** search 11 times, or `$STACK exec redis redis-cli KEYS 'ratelimit:*'`.

#### 43. How does streaming work end to end?
Sonnet streams tokens → `rerank_stream` buffers them and splits on `\n` → each complete JSON line
becomes an SSE `event: card`. The client reads `res.body.getReader()`, decodes with
`{stream: true}` (Polish and Russian characters can be split across chunks), and splits frames on
`\n\n`. A new search aborts the previous stream with an `AbortSignal`.

### #12 Ingestion (module of choice)

#### 44. ★ Why is this a Major module?
The product is only as good as its catalog, and no single source covers both events and places. It
is a real pipeline:
- 4 adapters behind one interface (OSM/Overpass + Wikidata, Facebook via Apify, Ticketmaster,
  fixtures);
- category inference;
- cross-source fuzzy dedup, with an LLM judge for unclear pairs;
- batched embeddings with retry/backoff;
- an idempotent upsert;
- per-source schedules (k8s CronJobs / ofelia locally);
- isolated failures per source and per record.

It's comparable in effort to the subject's Majors and is documented in INGESTION.md.

#### 45. ★ fetch → normalize → dedup → embed → upsert
1. **fetch:** `adapter.fetch() -> list[RawItem]`. The only per-source code. A failure aborts only
   that source.
2. **normalize:** fills missing categories (keyword table, PL+EN). One bad record doesn't kill the
   batch.
3. **dedup:** *before* embedding, so we don't pay to embed duplicates. Duplicates become extra
   `sources` on the existing card.
4. **embed:** Voyage, batches of 16. A failed batch is skipped, not dropped.
5. **upsert:** `ON CONFLICT (source, source_url) DO UPDATE`. The embedding is overwritten **only if
   this run computed one**, so a keyless run can't wipe the vectors.

**Show:** `make stack-seed` output and the summary line `fetched N → M new … merged … folded …`.

#### 46. How does cross-source dedup work?
1. **Normalize names:** NFKD; a strip table for `ł/ø/đ`; drop "warszawa", "official", years.
2. **Blocking:** compare only within the same day (events), the same ~110 m grid cell (places), or
   the same first 4 letters. That's faster and also correct: different days ⇒ different events.
3. **Score** with `rapidfuzz.token_set_ratio`, which handles one source appending the venue:
   - ≥ 90 → same;
   - 75–89 → ask Haiku "same event? yes/no";
   - < 75 → different.

When unsure, keep both. A visible duplicate is cosmetic; a wrong merge loses a real event.

#### 47. Scheduling, failures, idempotency
- **Schedules:** places Mondays 04:00, Facebook every 6 h, Ticketmaster every 12 h. One CronJob per
  source in the cloud (`concurrencyPolicy: Forbid`); `ofelia` locally (`make scheduler-up`).
- **Failures:** a failing source logs and exits without touching the others.
- **Idempotency:** re-runs are safe because the upsert key is `(source, source_url)`, so running
  twice updates rows instead of duplicating them.

#### 48. Do you re-embed unchanged items?
Yes, currently every card is re-embedded on each run. At a few hundred cards per source that's
cheaper than tracking changes. There's a TODO to switch to change detection (e.g. a content hash) at
tens of thousands of cards. Say this honestly.

### #10 ELK · #11 Prometheus + Grafana

#### 49. ★ How does a log line get to Kibana? Retention? Security?
`api`/`web` containers → Docker **fluentd log driver** → **Fluent Bit** (:24224) → **Logstash**
(TCP `json_lines`, parses `time` into `@timestamp`) → **Elasticsearch** daily index
`warsaw-logs-YYYY.MM.dd` → **Kibana** (index pattern `warsaw-logs-*`).

**Security:** Elasticsearch is not published at all (internal network only). Kibana is reachable
only through nginx with HTTPS + basic auth.

**Retention:** in the cloud an ILM policy deletes indices after **30 days**
(`elk_retention_days`). Locally there's no ILM; daily indices make deletion trivial. ES `xpack`
security is off locally because ES is not exposed.

#### 50. ★ Targets, dashboard, live alert. Pull or push? Which metrics?
- **Pull:** Prometheus scrapes `api:8000/metrics`, postgres-exporter, node-exporter,
  otel-collector and itself. It keeps 7 days (`--storage.tsdb.retention.time=7d`). Traces are
  *pushed* (OTLP → Tempo).
- **API metrics:** `prometheus-fastapi-instrumentator` gives request count, latency histograms and
  in-progress requests, per handler and status.
- **Alerts:** `APIDown`, `APIHighErrorRate`, `APIHighLatencyP95`, `TargetDown`, `PostgresDown`,
  `PostgresTooManyConnections`.

**Show:** `https://localhost:9090/targets` (all UP) → Grafana dashboards → `$STACK stop api`, wait
~2–3 min → `APIDown` firing in `:9090/alerts` and Alertmanager `:9093` → `$STACK start api`.

---

## E. Minor modules not yet in the README table (2FA, GDPR, health/backups)

### 51. 2FA: late email? Brute force?
When 2FA is on, a correct password doesn't log you in. It sets `pending_2fa` in the session and
emails a 6-digit code. `POST /auth/login/2fa` checks it with the same expiry, the 5-attempt cap, the
HMAC-stored code and the per-IP rate limit. A late or lost email: sign in with the password again
for a fresh code (the old one is replaced). Brute force: 5 wrong tries kill the code, plus 10/min
per IP.

### 52. GDPR: what's exported, what's deleted?
**Export** (`GET /me/export`) is a JSON download with:
- the profile;
- saved items;
- friendships (both directions);
- shared events (sent and received).

It contains ids only, nothing else about other users.

**Delete** (`DELETE /me`):
- password accounts must confirm the password;
- the user row is deleted and the cascade removes everything (including shares others sent you and
  your shares in their inbox);
- the session is cleared and a confirmation email goes out.

### 53. `/health` vs `/ready`, backups, restore
- **`/health`:** liveness. The process answers → `{"status":"ok"}`.
- **`/ready`:** readiness. Runs `SELECT 1` on Postgres and pings Redis; **503** with
  `{"db":…, "redis":…}` if either is down.
- **Status page** (`/status`): shows both, linked from the footer.

**Backups:** in the cloud, DigitalOcean managed Postgres keeps daily backups + 7-day point-in-time
recovery. `make do-db-backup` / `do-db-restore` does manual dumps.

**Recovery targets:** RPO is minutes within 7 days; RTO is ~15–30 min to rebuild everything
(DISASTER_RECOVERY.md). The catalog can be re-ingested; what really needs backing up is user data.

---

## F. Live changes and deep dives

### 54. ★ Make a change live
Have two ready:
- **Quota:** add `SEARCH_DAILY_LIMIT=5` to `backend/.env` (the setting is `search_daily_limit` in
  `backend/app/config.py`), then `$STACK up -d api` (recreate so `.env` is re-read) and show the
  6th search refused.
- **Colour token:** change a variable in `frontend/src/app/globals.css`, rebuild `web`
  (`$STACK up -d --build web`) and show it changes on every page.

### 55. ★ Explain one of your functions line by line
Suggested: `_parse_line` in `backend/app/llm/rerank.py`.
1. Strip the line and drop a trailing comma.
2. Not starting with `{` → it's prose, ignore.
3. Parse the JSON; malformed → ignore.
4. `n` must be an int in range and not already seen. That blocks hallucinated numbers and duplicate
   cards.
5. Return `(items[n-1], blurb)`.

### 56. What breaks if Postgres or Redis restarts?
- **Postgres:** a hard dependency. Requests 500 while it's down and `/ready` returns 503. The pool
  uses `pre_ping`, so stale connections reconnect on their own afterwards. Data is in the `pgdata`
  volume.
- **Redis:** nothing user-visible. Quotas and auth limits fail open, and the counters reset. `/ready`
  reports it.

### 57. How would you scale to 10× users?
- The API is stateless (signed cookies), so add replicas.
- The DB connection is released before the LLM stream, so the pool isn't the bottleneck (2 replicas
  × 10 connections < 25 on the managed DB).
- Next steps:
  - PgBouncer;
  - Postgres read replicas for search;
  - the Anthropic Batches API for dedup;
  - incremental embeddings;
  - CDN caching of SSR item pages (they already `revalidate: 60`).
- The real limit is LLM cost and rate limits, which the per-user quota caps.

### 58. Hardest bug?
Pick one you lived through. Candidates from our docs:
- **Embedding erasure:** a keyless ingest overwrote every vector with NULL, so semantic search
  silently died. Fix: split the upsert by `refresh_embedding`.
- **Stream ending without `done`:** a re-rank error mid-stream left the spinner turning forever. Fix:
  an `except` that always finishes with `done`.
- **Selective filters starving HNSW** (3 results instead of 30). Fix: iterative scan.
- **A DB connection held for the whole SSE stream.** Fix: commit + expunge + close before streaming.

### 59. What would you do differently?
- Alembic migrations from day one instead of `create_all` + manual `ALTER IF NOT EXISTS`.
- A CSRF token and per-account lockout, not only SameSite + per-IP limits.
- A password-reset flow.
- Incremental embeddings.
- Lock the 2FA/GDPR/status UIs earlier so they weren't last-minute.

### 60. What's unfinished / known limitations?
These are stated in SECURITY.md §11:
- no CSRF token;
- rate limits fail open;
- no password reset;
- no audit log;
- RLS isn't exercised in local dev (the owner role bypasses it; CI tests it);
- full re-embedding on each run;
- the cloud deployment is reference only. The graded stack is local Docker Compose.

The minor modules (2FA, GDPR, health/backups) have their UI merged (#58–#60) but count only once
they are added to the README module table.
