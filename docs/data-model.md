# Data model

> Deep dive: [SECURITY.md](SECURITY.md) §5 covers the Row-Level Security policies on
> `saved_items`, `friendships` and `shared_events`.

Events and places are **one entity** (`items`) with a `kind`, not separate
tables. That makes "what's on this Saturday evening" a single query: events in
the time window plus permanent places. Everything a user owns hangs off `users`
with `ON DELETE CASCADE`, so deleting an account removes their saves, friendships,
shares and avatar in one statement.

Tables are SQLAlchemy models in `backend/app/catalog/models.py`; the SQL below is
the equivalent schema. There are no migration files. `app.main._create_schema`
builds the schema in this order: extensions (`vector`, `pg_trgm`) →
`create_all` → `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for columns added after a
table already existed → indexes → CHECK constraints → RLS policies. Locally it
runs on app startup (`DB_BOOTSTRAP=true`, the default). In prod the runtime role
is DML-only, so `DB_BOOTSTRAP=false` and the same function runs as the admin via
`make do-db-migrate` before each deploy that changes the schema.

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

## `items` — the card catalog

```sql
CREATE TABLE items (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind          text NOT NULL CHECK (kind IN ('event', 'place')),
    name          text NOT NULL,
    description   text,
    category      text,                 -- concert, exhibition, castle, museum...
    lat           float,
    lon           float,
    price_from    numeric,
    price_to      numeric,
    image_url     text,
    source        text NOT NULL,        -- canonical source after dedup
    source_url    text,
    sources       jsonb,                -- all (source, source_url) refs after dedup
    -- events only:
    starts_at     timestamptz,
    ends_at       timestamptz,
    -- permanent places only:
    is_permanent  boolean NOT NULL DEFAULT false,
    opening_hours jsonb,                -- weekly schedule
    -- semantic search:
    embedding     vector(1024),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, source_url)         -- upsert key for ingestion
);
CREATE INDEX ix_items_embedding ON items USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_items_name_trgm ON items USING gin  (name gin_trgm_ops);
CREATE INDEX ix_items_starts_at ON items (starts_at);
CREATE INDEX ix_items_category  ON items (category);
```

Key columns:
- `embedding vector(1024)` — the card's semantic coordinates for vector search.
  Nullable: a keyless or rate-limited ingestion run leaves it untouched rather
  than wiping it (see [INGESTION.md](INGESTION.md) §4.5).
- `sources jsonb` — every source a card was seen at; duplicates don't create new
  rows, they append their ref here (see [ingestion.md](ingestion.md)).
- `UNIQUE (source, source_url)` — re-running a source upserts instead of duplicating.
- `hnsw` index — approximate nearest-neighbour search for the semantic leg of
  hybrid retrieval; without it every query would scan all rows.
- `gin (name gin_trgm_ops)` — trigram index for the lexical leg
  (`word_similarity` / `<%` on the card name); see [ALGORITHMS.md](ALGORITHMS.md) §4.

## `intent_logs` — prompt-parse log

Every prompt parse is logged: a future fine-tuning dataset for a local intent
model, and analytics on what users actually search for.

```sql
CREATE TABLE intent_logs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_prompt text NOT NULL,        -- what the user typed
    intent      jsonb NOT NULL,       -- what the model extracted
    model       text NOT NULL,        -- claude-haiku-4-5 / local-qwen...
    latency_ms  int,
    created_at  timestamptz NOT NULL DEFAULT now()
);
```

## `users` — accounts

One row per account, reachable through one of two doors: Google sign-in
(`google_sub`) or email + password (`password_hash`). `email` is the shared
identifier. Registering a password on an address that already has an account is
refused (409). A Google login on an address that already has a password account
**links** it — sets `google_sub` and voids `password_hash`, because that password
was set before ownership was proven and could belong to someone who pre-registered
the email (see [auth.md](auth.md), [SECURITY.md](SECURITY.md) §2).

```sql
CREATE TABLE users (
    id                           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub                   text UNIQUE,          -- Google's stable id; NULL for password-only accounts
    password_hash                text,                 -- bcrypt; NULL for Google-only accounts
    email                        text UNIQUE,          -- the login identifier
    email_verified               boolean NOT NULL DEFAULT false,
    -- pending verification code (never the code itself — a keyed hash):
    email_verify_code_hash       text,
    email_verify_code_expires_at timestamptz,
    email_verify_attempts        int NOT NULL DEFAULT 0,
    name                         text,
    avatar_url                   text,                 -- Google photo URL or /avatars/{user_id}
    last_seen_at                 timestamptz,          -- refreshed by the /me/ping heartbeat
    created_at                   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_users_name_trgm ON users USING gin (name gin_trgm_ops);
```

Key columns:
- `google_sub` / `password_hash` — exactly one is set at a time; linking makes
  the account Google-owned. `UNIQUE` on `google_sub` tolerates many NULLs.
- `email_verified` — Google logins prove ownership and set it immediately;
  password accounts start `false` and flip after entering the 6-digit code.
- `email_verify_*` — the code's HMAC, its expiry (15 min) and a wrong-attempt
  counter (cap 5). All NULL/0 once verified. [SECURITY.md](SECURITY.md) §3.
- `last_seen_at` — a user is "online" while this is within a short window
  (`app.api.social._is_online`).
- `gin (name gin_trgm_ops)` — makes `/users/search`'s `name ILIKE '%term%'`
  index-accelerated despite the leading wildcard.

## `saved_items` — favorites

```sql
CREATE TABLE saved_items (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id    uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, item_id)           -- a card is saved at most once per user
);
CREATE INDEX ix_saved_items_user_id ON saved_items (user_id);
CREATE INDEX ix_saved_items_item_id ON saved_items (item_id);
```

Both FKs are indexed on purpose — Postgres does not index FK columns, and
without `ix_saved_items_item_id` the `ON DELETE CASCADE` from `items` (and any
"who saved this card" lookup) is a sequential scan.

## `friendships` — directed request, mutual once accepted

```sql
CREATE TABLE friendships (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    addressee_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (requester_id, addressee_id)
);
CREATE INDEX ix_friendships_requester_id ON friendships (requester_id);
CREATE INDEX ix_friendships_addressee_id ON friendships (addressee_id);
```

One row per ordered `(requester, addressee)` pair. `pending` = the requester
asked and is waiting; `accepted` = friends, and direction stops mattering.
"Are A and B friends?" is an `accepted` row with `{requester, addressee} = {A, B}`
in either direction.

## `shared_events` — "shared with me" inbox

```sql
CREATE TABLE shared_events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id      uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    message      text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (from_user_id, to_user_id, item_id)   -- share a card to a friend once
);
CREATE INDEX ix_shared_events_from_user_id ON shared_events (from_user_id);
CREATE INDEX ix_shared_events_to_user_id   ON shared_events (to_user_id);
CREATE INDEX ix_shared_events_item_id      ON shared_events (item_id);
```

## `user_avatars` — uploaded avatar bytes

```sql
CREATE TABLE user_avatars (
    user_id      uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data         bytea NOT NULL,
    content_type text  NOT NULL,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(data) <= 524288)         -- 512 KiB hard ceiling
);
```

The blob lives in its own table, not as a column on `users`, so it never rides
along on the many `SELECT … FROM users` queries in the social layer. One row per
user (`user_id` is the primary key). The app resizes uploads well below the
CHECK; the constraint is the DB-level backstop and must stay in sync with
`settings.avatar_max_stored_bytes`. Bytes are served by `GET /avatars/{user_id}`,
and `users.avatar_url` points there for uploaded avatars (`POST` / `DELETE
/me/avatar` manage the row).
See [SECURITY.md](SECURITY.md) §7 for the decompression guard.

## Row-Level Security

The three user-owned relation tables have RLS as a backstop under the
app-layer authorisation. The requester is `current_setting('app.user_id')`, set
per request in `auth.deps.current_user`. Policies bite only for the runtime role
(`warsaw_app`); the table owner used for migrations and local dev bypasses them.

| Table | SELECT | INSERT | DELETE |
|---|---|---|---|
| `friendships` | either party | either party (`WITH CHECK`) | either party |
| `shared_events` | sender or recipient | sender only | recipient only (dismiss) |
| `saved_items` | own rows, or an **accepted friend's** rows | own rows | own rows |

`users`, `items`, `intent_logs` are public or non-tenant and carry no RLS.
Full policy text and the reasoning: [SECURITY.md](SECURITY.md) §5.
