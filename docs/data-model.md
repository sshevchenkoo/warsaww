# Data model

Events and places are **one entity** (`items`) with a `kind`, not separate
tables. That makes "what's on this Saturday evening" a single query: events in
the time window plus permanent places. Tables are defined as SQLAlchemy models
in `backend/app/catalog/models.py` and created on app startup; the SQL below is
the equivalent schema.

## `items` — the card catalog

```sql
CREATE TABLE items (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind          text NOT NULL,        -- 'event' | 'place'
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
    is_permanent  boolean DEFAULT false,
    opening_hours jsonb,                -- weekly schedule
    -- semantic search:
    embedding     vector(1024),
    created_at    timestamptz DEFAULT now(),
    updated_at    timestamptz DEFAULT now(),
    UNIQUE (source, source_url)         -- upsert key for ingestion
);
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON items (starts_at);
CREATE INDEX ON items (category);
```

Key columns:
- `embedding vector(1024)` — the card's semantic coordinates for vector search.
- `sources jsonb` — every source a card was seen at; duplicates don't create new
  rows, they append their ref here (see [ingestion.md](ingestion.md)).
- `UNIQUE (source, source_url)` — re-running a source upserts instead of duplicating.
- `hnsw` index — fast approximate nearest-neighbour search; without it every
  query would scan all rows.

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
    created_at  timestamptz DEFAULT now()
);
```

## `users` and `saved_items` — accounts & favorites

Added with the auth module (see [auth.md](auth.md)); the tables above are unchanged.

```sql
CREATE TABLE users (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub text NOT NULL UNIQUE,    -- Google's stable user id
    email      text,
    name       text,
    avatar_url text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE saved_items (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id    uuid NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE (user_id, item_id)           -- a card is saved at most once per user
);
CREATE INDEX ON saved_items (user_id);
```
