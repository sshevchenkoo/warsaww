# SECURITY.md — the layers, what each one actually stops, and what none of them do

An inventory of every control in the app, why it exists, and where the boundary sits. Written so that
a change near auth, sessions, RLS or uploads can be checked against the reasoning that put the
control there in the first place.

The short reference version of the identity flow is [auth.md](auth.md). This file supersedes it where
they disagree — in particular, the app *does* now handle passwords (§2).

---

## 1. The shape of the trust boundary

```
      browser
        │  signed session cookie (user id only, no server-side session store)
        ▼
   ingress (TLS, cert-manager)
        │  NetworkPolicy: default-deny ingress in the `warsaw` namespace
        ▼
      api pod ───────────────────────────────┐
        │  app-layer authz (FastAPI deps)    │  non-root, read-only rootfs,
        │                                    │  all capabilities dropped
        │  SET LOCAL app.user_id = <uuid>    │
        ▼                                    │
   postgres ◄── Row-Level Security ──────────┘
        │  connects as warsaw_app: DML only, no DDL, no CREATE ROLE
```

Three independent layers guard user-owned data: the FastAPI dependency decides *whether* the request
is authenticated, the query decides *what* it asks for, and RLS in Postgres decides what the database
is willing to return regardless of what the query asked. Each is sufficient on a good day; the point
is that a bug in one is not a breach.

---

## 2. Identity: two doors, one account

`backend/app/api/auth.py`, `backend/app/auth/`

| Door | Credential | Where it is stored |
|---|---|---|
| Google OAuth (authlib, OIDC) | none — Google asserts identity | `users.google_sub` |
| Email + password | bcrypt hash | `users.password_hash` |

**Email is the join key.** Registering with a password and later signing in with Google on the same
address lands you in the same account, not a second one.

### Account pre-hijacking, and why linking voids the password

That linking is also an attack if it is done naively:

1. An attacker registers `victim@example.com` with a password they choose. They cannot read the
   verification email, so the account stays unverified — but it exists, with a password on it.
2. The real owner later signs in with Google. Google proves they own the address, so linking is
   correct and the account becomes theirs.
3. Without further action, **the attacker's password still works on the victim's account.**

So on link:

```python
if user is not None and user.password_hash is not None:
    log.info("OAuth link: clearing pre-existing password on account %s", user.id)
    user.password_hash = None
```

The password was set before ownership was proven, so it is voided. The account becomes Google-owned.
The legitimate user who genuinely had a password loses nothing they cannot recover by continuing to
use Google.

### Password handling

- **bcrypt** (`bcrypt.gensalt()`, per-hash salt).
- bcrypt reads only the first 72 bytes of a password, so `MAX_PASSWORD_BYTES = 72` is enforced at the
  API schema — a longer password must be **rejected**, not silently truncated, or two different
  passwords would open the same account.
- `verify_password` catches `ValueError` on a malformed stored hash and returns `False` rather than
  raising a 500 that distinguishes "corrupt hash" from "wrong password".
- Login returns one message — `"Invalid email or password"` — for both an unknown email and a wrong
  password, so the endpoint is not a registration oracle.

### OAuth callback failures are not 500s

State mismatch, an expired or denied code, a Google 5xx: all routine. The callback logs a warning and
redirects to `/login?error=oauth` instead of showing a stack trace to a user who simply hit "cancel".

---

## 3. Email verification

`backend/app/auth/email.py`

A 6-digit numeric code the user types back, not a magic link. A link in an email is a credential that
travels through mail clients, link scanners and proxies; a code the user retypes stays with the
person reading the inbox.

A 6-digit code is only ~1M wide, so four separate controls carry the weight:

| Control | Value | Role |
|---|---|---|
| Expiry | 15 min (`email_verify_code_ttl_minutes`) | Bounds the guessing window |
| Attempt cap | 5 (`email_verify_max_attempts`) | Ends the guessing at the account level |
| Auth rate limit | 10/min per IP | Ends it at the network level |
| Single use | cleared on success | No replay |

What is stored is **never the code**: `hmac.new(session_secret, code, sha256)`. Keying the hash with
the session secret means a leaked database alone cannot be brute-forced offline — 10⁶ candidates
against a plain SHA-256 is seconds of work; against an HMAC whose key lives in the app's environment
it is nothing without that key too. Comparison is `hmac.compare_digest`, constant time.

`generate_code` uses `secrets.randbelow`, not `random` — `random` is a Mersenne Twister whose state is
recoverable from its output.

Delivery (Resend) **never raises**. A provider hiccup must not fail a registration that already
succeeded; the user asks for a resend. Without `RESEND_API_KEY` sending is a logged no-op, so local
dev and an unconfigured deploy still work.

`/auth/resend` is rate-limited for a reason beyond brute force: an unauthenticated-ish "send an email
to this address" endpoint is a spam relay if it is not.

---

## 4. Sessions

`SessionMiddleware` (Starlette), signed cookie, `same_site="lax"`, `https_only` in production.

The cookie holds **only the user id** (and an anonymous `sid` for the search quota). No server-side
session store, which is what lets any API replica serve any request — they all validate against the
same `session_secret`. The database row is the source of truth; the cookie is just a claim about
which row.

Consequences handled explicitly in `auth/deps.py`:

- A cookie whose value is not a UUID → clear it, return 401. Not a 500 from a failed parse.
- A cookie pointing at a deleted user → clear it, return 401. A stale cookie heals itself.

`same_site="lax"` blocks the cross-site POST shape of CSRF while still allowing the top-level
redirect back from Google's consent screen — which a `strict` cookie would break.

---

## 5. Row-Level Security

`backend/app/main.py::_ensure_rls`

The app-layer check (`WHERE user_id = :me`) is the first defence. RLS is the backstop for the query
that forgets it.

**How the identity reaches Postgres:** every authenticated endpoint depends on `current_user`, which
runs

```sql
SELECT set_config('app.user_id', :uid, true)   -- is_local => true
```

on the request's transaction. Transaction-local, so it is cleared when the transaction ends and can
never leak onto the next request that borrows the same pooled connection. Anonymous endpoints do not
set it and do not touch RLS-protected tables.

| Table | Policy |
|---|---|
| `friendships` | Only the requester and the addressee can see or modify the row. |
| `shared_events` | Sender and recipient read; only the sender inserts; only the recipient deletes (dismiss from inbox). |
| `saved_items` | Write only your own. Read your own **or an accepted friend's** — and that friend check reads `friendships`, which is itself RLS-scoped. |
| `users`, `items`, `intent_logs` | No RLS — public or non-tenant data. |

Four implementation details that are each a footgun:

- **RLS does not apply to the table owner.** It bites `warsaw_app` (the least-privilege runtime role)
  and is bypassed by `doadmin`, which runs the migration. Policies are *not* `FORCE`d, so local dev —
  which connects as the owner — also bypasses them. **This means local manual testing does not
  exercise RLS.** `backend/tests/test_rls.py` does, against a real Postgres in CI.
- **Policies are dropped and recreated** on every startup/migrate, so the function is idempotent and
  a policy change actually takes effect rather than silently colliding with the old one.
- `current_setting('app.user_id', true)` is wrapped as `(select …)` so the planner evaluates it once
  per statement instead of once per row.
- `nullif(…, '')::uuid` — an unset setting returns `''`, and casting that to uuid would error. As
  NULL, every policy comparison is simply false, which is the correct default for a request with no
  identity.

---

## 6. Rate limits

`backend/app/ratelimit.py`, Redis-backed.

| Limit | Key | Default | Purpose |
|---|---|---|---|
| Search | `ratelimit:search:{sid}:{date}` | 10/day per session | Cost control on the only endpoint that spends money |
| Auth | `ratelimit:auth:{ip}:{minute}` | 10/min per IP | Brute-force friction on login/register/verify/resend |

**Both fail open.** `redis.RedisError` → allow. This is a deliberate, stated choice: these are cost
and abuse controls, not authorization boundaries. Redis is not on the critical path for deciding who
may read what — Postgres and the session cookie are — so a Redis outage degrades cost control rather
than taking the product down or, worse, locking everyone out.

Both counters expire themselves (`EXPIRE` to midnight Europe/Warsaw, or 60 s), so nothing sweeps
them.

Client IP for the auth limit is the **first hop of `X-Forwarded-For`**, falling back to the socket
peer. Behind the ingress the socket peer is the ingress controller, so keying on it would throttle
the whole internet as one client.

---

## 7. Uploads: the avatar decompression guard

`backend/app/api/avatars.py`

The 5 MB input cap does **not** bound memory. A few-kilobyte PNG of uniform data can declare
50000×50000 pixels and expand to gigabytes the moment it is decoded — the classic decompression bomb.
So the order of operations is the control:

1. `await file.read(max + 1)` — read one byte past the limit. An oversized upload (or a lying
   `Content-Length`) is rejected without pulling the whole body into memory.
2. `Image.open()` — lazy; reads the header and dimensions only.
3. **Reject on `width * height > 50_000_000` before `img.load()`.** This is the actual guard; step 4
   is the backstop.
4. `img.load()` inside a `try` that also catches `Image.DecompressionBombError` (`Image.MAX_IMAGE_PIXELS`
   is pinned to the same number).
5. Re-encode: centre-crop to a square, resize to 256 px, flatten alpha onto white, save as JPEG.

Step 5 has a second security effect beyond size: **re-encoding strips metadata.** Uploaded EXIF —
including GPS coordinates from a phone photo — does not survive, because the output is built from
pixels rather than copied from the input.

What lands in the database is 15–25 KB, with `CHECK (octet_length(data) <= 524288)` as a DB-level
ceiling that holds even if the application logic is bypassed. Avatars live in their own
`user_avatars` table so the blob never rides along on the many `SELECT … FROM users` queries in the
social layer.

---

## 8. Secrets

| Rule | Where | Why |
|---|---|---|
| API tokens go in headers, never query strings | `adapters/facebook_events.py` | httpx logs the full URL at INFO; a `?token=` would land in the pod logs and then in ELK |
| `httpx` logger pinned to WARNING | `ingestion/runner.py` | Defence in depth for the same class of leak |
| App secrets never enter CI | `.github/workflows/deploy.yml` | `warsaw-secrets` is applied manually with `kubectl`; the deploy job only has the DO token |
| `envsubst` restricted to three named vars | deploy step | So a stray `$SOMETHING` in a manifest cannot be substituted from the runner's environment |
| Deploy waits for a human | `environment: production` | The GitHub Environment gate pauses the job for a reviewer |

### The config validator that refuses to boot

`backend/app/config.py`:

```python
if self.session_https_only:              # our "this is production" signal
    if self.session_secret == INSECURE_SESSION_SECRET: raise ValueError(...)
    if "*" in self.cors_origins:         raise ValueError(...)
```

The dev default signing key is public knowledge — it is in the repo. A production deploy still
carrying it has forgeable session cookies, and a wildcard CORS origin next to credentialed requests
is the other half of the same hole. Both are silent failures: everything works, and the security
property is simply absent. Refusing to start turns a silent hole into an obvious crash loop.

---

## 9. Least privilege, at every layer

**Database** (`backend/db/app-role.sql`). The runtime role `warsaw_app` gets `CONNECT`, `USAGE ON
SCHEMA`, and DML on existing tables and sequences. No DDL, no `TRUNCATE`, no `CREATE ROLE`, no other
database. A compromised API pod cannot drop the schema, create a backdoor login, or reach another
database in the cluster. `ALTER DEFAULT PRIVILEGES` covers tables created later by the admin-run
migrate step, so the grant does not have to be re-run after every migration.

This is why `db_bootstrap` exists: locally the app owns its schema and runs `create_all` on startup;
in production `DB_BOOTSTRAP=false` and schema changes are an admin step (`make do-db-migrate`). The
same flag gates DDL in the ingestion pipeline.

**Kubernetes.** Default-deny ingress for the whole `warsaw` namespace, then named allows — the
ingress controller and the web pod to the API, Prometheus to `/metrics`, and a narrow exception on
:8089 for cert-manager's ACME HTTP-01 solver (without it, TLS issuance silently never completes).
Egress stays open because the API and the CronJobs call Anthropic, Voyage, Overpass and friends.
Pods run non-root with a read-only root filesystem, `allowPrivilegeEscalation: false`, and all
capabilities dropped.

---

## 10. What is covered by tests

`backend/tests/`, run in CI against a real Postgres with pgvector:

| File | What it pins down |
|---|---|
| `test_rls.py` | Saved items scoped to the owner; visible to an accepted friend but not a pending one or a stranger; friendship rows visible only to the two parties; `shared_events` read scope; insert `WITH CHECK` rejects another user's id |
| `test_auth_security.py` | bcrypt round-trip and salting, the 72-byte limit, a bad hash returns false rather than raising, per-IP auth limiting, fail-open on Redis down, `X-Forwarded-For` first-hop parsing |
| `test_search_gate.py` | 401 unauthenticated, 401 when the cookie's user is gone, 403 unverified, 401 + cookie cleared on a malformed cookie, pass when verified |
| `test_email_verify.py` | Success clears the code, wrong code increments attempts, expiry, the attempt cap, already-verified is a no-op |
| `test_avatars.py` | Valid image becomes a JPEG square, oversized dimensions rejected, non-image bytes rejected, Pillow's pixel cap is pinned |

The RLS tests matter disproportionately, because local development bypasses RLS entirely (§5) — CI is
the only place the policies are actually exercised.

---

## 11. What none of this protects against

Stated plainly, because an inventory that only lists strengths is misleading:

- **No CSRF token.** The defence is `same_site="lax"` plus the fact that state-changing endpoints are
  POST/JSON. A browser that mishandles SameSite, or a future state-changing GET, would need one.
- **Fail-open rate limits.** An attacker who can take Redis down gets unlimited search and unlimited
  auth attempts. Passwords are still bcrypt and authorization still holds; the cost control does not.
- **No account lockout or 2FA.** The auth limit is per-IP per-minute and a distributed attacker is not
  meaningfully slowed by it.
- **No password reset flow.** A user with a password-only account who forgets it has no path back
  except signing in with Google on the same address.
- **Trust in `X-Forwarded-For`.** A client that can reach the API directly, bypassing the ingress, can
  forge the header and evade the per-IP limit. The NetworkPolicy is what makes that hard.
- **No audit log.** `intent_logs` records searches, not administrative or authentication events.
- **Ingested content is not sanitised as HTML.** Names, descriptions and image URLs come from
  OpenStreetMap, Wikipedia, Apify and Ticketmaster. They are rendered as text by React (which escapes
  by default) — that is the whole defence, so any future `dangerouslySetInnerHTML` on card content
  would be an XSS sink fed by third parties.
