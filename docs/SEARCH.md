# SEARCH.md — one `/search` request, from keystroke to card

A single trace through the most expensive endpoint in the system: what runs, in what order, what
holds a database connection while it runs, and what the user sees when each hop fails.

[ALGORITHMS.md](ALGORITHMS.md) explains *why* each stage computes what it computes. This file is
about ordering, resources and failure. Read it before changing `backend/app/api/routes.py` or
`frontend/src/lib/api.ts`.

---

## 1. The whole request on one page

```
browser                    api (FastAPI)                     external                postgres
───────                    ─────────────                     ────────                ────────
POST /search ─────────────► gate: signed in + verified?                              ▪ short read
  {prompt}                  quota: Redis INCR ─────────────► redis
                            intent extraction ─────────────► claude-haiku   ~1 s
                            embed raw prompt ──────────────► voyage-3.5     ~0.2 s
                            ┌─ open session ────────────────────────────────────────► INSERT intent_log
                            │  hybrid retrieval ────────────────────────────────────► SELECT (one query)
                            └─ expunge + CLOSE  ◄── connection returns to the pool
       ◄─ event: intent      (no DB connection held from here on)
                            rerank stream ─────────────────► claude-sonnet  ~3-8 s
       ◄─ event: card        (yielded per line as the model writes)
       ◄─ event: card
       ◄─ event: done
```

Two properties of that picture are load-bearing and easy to break:

1. **Every external call happens outside a database transaction.**
2. **The database connection is released before the stream starts**, not when the response ends.

---

## 2. The gate, before any spend

```python
if settings.require_verified_email_to_search:
    _require_verified_user(request)
```

`/search` is the only endpoint that costs real money per call, so authorization is checked before the
first token is spent. `_require_verified_user` returns:

| Condition | Status | Client behaviour |
|---|---|---|
| No `user_id` in the session cookie, or it does not parse, or the row is gone | 401 | `AuthError` — the cookie is cleared server-side first, so a stale cookie heals itself |
| Signed in, `email_verified = false` | 403 | `AuthError`, message asks the user to verify |

It deliberately does **not** use the `current_user` FastAPI dependency. A dependency-resolved session
is bound to the request scope and would stay checked out of the pool for the entire SSE stream —
seconds, for a check that takes microseconds. So the lookup runs in its own short-lived
`SessionLocal()` block and closes immediately.

The unverified user is not locked out of the product: `/upcoming` and `/items/{id}` are open, so the
home feed and every card detail page still render. Only the prompt box is gated. See
[SECURITY.md](SECURITY.md) §3.

---

## 3. The quota

```python
sid = request.session.get("sid") or uuid4().hex   # anonymous visitors get one too
allowed, remaining = check_search_quota(sid)
```

Redis key `ratelimit:search:{sid}:{YYYY-MM-DD}`, `INCR`, and on the first hit of the day an
`EXPIRE` set to seconds-until-midnight in `Europe/Warsaw` (+60 s of slack). The counter therefore
disappears on its own; nothing sweeps it.

A calendar day in a named timezone, rather than a rolling 24 h window, because "10 searches a day"
is a sentence a user understands and a sliding window is a sentence they do not.

Over the limit → **429** with the limit in the message. The frontend turns that into a
`RateLimitError` and shows it verbatim rather than a generic failure.

**Fail-open on Redis errors.** `check_search_quota` catches `redis.RedisError` and returns
`(True, limit)`. This is cost control, not an authorization boundary — Redis being down should not
take search down with it. The authorization boundary is §2, and that one is backed by Postgres.

---

## 4. The work

### 4.1 Intent, then embedding — both before the database

```python
intent = extractor.extract(req.prompt)          # claude-haiku, 15 s cap
if intent.on_topic and settings.voyage_api_key:
    try: query_embedding = embed_query(req.prompt)
    except Exception: log.warning(...)          # → lexical-only retrieval
```

Off-topic prompts skip the embedding entirely — no vector, no retrieval, no re-rank (§1 of
[ALGORITHMS.md](ALGORITHMS.md)).

The prompt is capped at 2000 characters by the Pydantic model:

```python
prompt: str = Field(min_length=1, max_length=2000)
```

Without the cap, one request can push an arbitrarily large string into both an embedding call and an
LLM prompt. It is a cost and latency abuse vector on the one endpoint where that matters.

### 4.2 The short database window

```python
with SessionLocal() as session:
    session.add(IntentLog(...))
    session.commit()            # commit BEFORE loading items
    items = search_items(...) if intent.on_topic else []
    session.expunge_all()       # detach, so the cards outlive the connection
```

Three ordering details, each of which caused a real problem:

- **`commit()` before loading items.** A commit expires every instance in the identity map by
  default. Committing *after* the `SELECT` would leave the `Item` objects needing a refresh — from a
  connection that is about to be returned to the pool.
- **`expunge_all()` before leaving the block.** The cards are read in the generator that runs after
  the session is closed. Attached instances would raise `DetachedInstanceError` on first attribute
  access; expunged ones carry their loaded values with them.
- **The `with` block ends here.** Everything after it — the whole LLM stream — runs with no
  connection checked out.

`intent_logs` records the prompt, the parsed intent, the model name and the parse latency. It is the
dataset a future fine-tuned local intent model would be trained on, and it is the only thing in the
request that is written rather than read.

### 4.3 Why the connection release matters more than it looks

Managed Postgres on the DigitalOcean basic tier allows **25 connections total**. The pool is sized
against that ceiling:

```
2 API replicas × (db_pool_size 5 + db_max_overflow 5) = 20 < 25
```

leaving headroom for the ingestion CronJobs and DigitalOcean's own monitoring roles. If a connection
were held for the duration of the SSE stream, concurrency would be capped at 20 *simultaneous
searches* for the whole cluster — while each of those connections sat idle waiting on an LLM. Holding
it for the ~50 ms of actual query time instead makes the pool a non-issue.

Supporting settings, all in `config.py`:

| Setting | Value | Reason |
|---|---|---|
| `db_pool_pre_ping` | `True` | Managed Postgres drops idle connections; without a pre-ping that surfaces as a mid-request error instead of a transparent reconnect. |
| `db_pool_recycle` | 1800 s | Retire connections before the server's own idle timeout does. |
| `db_statement_timeout_ms` | 30000 | A runaway query cannot pin a pooled connection indefinitely. |

---

## 5. The stream, and the degradation ladder

```python
def event_stream():
    yield _sse("intent", intent.model_dump())
    ...
    yield _sse("done", {})
```

Wire format is plain SSE: `event: <name>`, `data: <json>`, blank line. `ensure_ascii=False`, so
Polish and Russian blurbs go out as UTF-8 rather than escape sequences.

| Event | When | Payload |
|---|---|---|
| `intent` | always, first | the parsed `Intent` — the UI can show the interpreted filters before any card exists |
| `card` | 0..n times | one `ItemOut` including `blurb` |
| `done` | always, last | `{}` |

`intent` is sent first for a reason beyond debugging: it is the first byte of the response, so it
flushes headers and proves the connection is alive while Sonnet is still thinking.

### What the user gets when something breaks

| What fails | Where it is caught | Result |
|---|---|---|
| Intent extraction (timeout, API error, malformed output) | `ClaudeIntentExtractor.extract` | Permissive `Intent(free_text=prompt)`; retrieval runs on the raw prompt, structured filters lost. Search succeeds. |
| Voyage embedding | `try` around `embed_query` in the route | `query_embedding = None` → lexical-only retrieval via the same fusion code. Search succeeds. |
| Re-rank, **before any card** | `except` around the stream loop | All retrieved candidates are emitted in raw retrieval order, no blurbs, then `done`. |
| Re-rank, **mid-stream** | same | Cards already emitted stay; the rest are emitted in retrieval order (`emitted` set prevents duplicates), then `done`. |
| No `ANTHROPIC_API_KEY` at all | `if settings.anthropic_api_key and items` | Raw retrieval order, no blurbs. This is the keyless local-demo path. |
| Off-topic prompt | `intent.on_topic` is false | `intent` event, then `done`. No cards, no spend. |
| Redis down | `check_search_quota` | Fail-open, request proceeds. |
| Postgres down | not caught | 500. It is the one hard dependency. |

The mid-stream case is the subtle one. Without it, a re-rank failure would end the SSE response with
no `done` event — and the client's `while` loop would simply stop with the spinner still turning. The
`except` exists to guarantee that **every stream ends with `done`**, whatever happened.

Note what the `except` does *not* do: on a successful stream it never runs, so un-picked candidates
are never dumped into the results. The re-ranker's filtering is preserved on the happy path and only
bypassed when there is no re-ranker output to preserve.

---

## 6. The client side

`frontend/src/lib/api.ts`

`EventSource` is GET-only and cannot send a JSON body, so the client POSTs with `fetch` and parses
the stream by hand:

```ts
const reader = res.body.getReader();
buffer += decoder.decode(value, { stream: true });
while ((sep = buffer.indexOf("\n\n")) !== -1) {   // frames are separated by a blank line
  const { event, data } = parseFrame(buffer.slice(0, sep));
  ...
}
```

`{ stream: true }` on the decoder matters: a multi-byte UTF-8 character can be split across two
network chunks, and decoding each chunk independently would corrupt it. Polish and Russian blurbs
make that a near-certainty rather than an edge case.

Three more deliberate choices:

- **Relative URLs everywhere** (`/search`, not `https://api…/search`). In production the web service
  and the API sit behind one origin; in dev, Next's rewrites proxy them. Same-origin means the
  session cookie is sent without CORS credential gymnastics.
- **`credentials: "include"`**, so the cookie that carries `sid` and `user_id` actually rides along.
- **`signal`** from an `AbortSignal`, so typing a new prompt cancels the in-flight stream instead of
  interleaving two result sets into the same list.

Status codes are turned into named errors (`RateLimitError`, `AuthError`) carrying the API's own
`detail` string, because those two cases have something specific to tell the user and a generic
"search failed" would waste it.

---

## 7. Latency budget

Rough shape of a warm request, hybrid retrieval, ~5k cards:

| Stage | Time | Notes |
|---|---|---|
| Gate + quota | < 5 ms | one indexed `SELECT`, one Redis `INCR` |
| Intent (Haiku) | ~0.6–1.5 s | the fixed cost of understanding the prompt |
| Embedding (Voyage) | ~150–300 ms | one short query |
| Retrieval (Postgres) | ~10–50 ms | single fused query, HNSW + GIN |
| **First card visible** | **~2–4 s** | the re-ranker's first line |
| Last card | ~4–9 s | depends on how many cards survive |

The re-rank dominates, which is exactly why cards stream instead of arriving as one array — the
perceived latency is the time to the *first* card, and that is a number the architecture can move
even when the total cannot.

The process-wide Anthropic client (`llm/client.py`) exists for the same reason: constructing
`anthropic.Anthropic()` per request opened a new connection pool and paid a TLS handshake on every
search. One lazily-created client, reused across requests, and it is thread-safe — which matters
because FastAPI runs these sync endpoints in a threadpool.

---

## 8. Related endpoints

| Endpoint | Auth | LLM | Notes |
|---|---|---|---|
| `GET /upcoming?limit=` | none | none | Soonest events, `coalesce(ends_at, starts_at) >= now`, so an event stays listed until it ends. Limit clamped to 1..48. |
| `GET /items/{id}` | none | none | One card; backs the SSR detail page. |
| `POST /search` | signed in + verified | Haiku + Sonnet + Voyage | This document. |

`/upcoming` is what makes the app useful before a user has signed in, and it costs nothing to serve —
no prompt, no model, one indexed query.
