# INGESTION.md — how a card gets into the catalog, and what it survives on the way

Four sources, one pipeline. This file is the build-and-maintenance view: the adapter contract, why
the pipeline stages are in that order, what each stage is allowed to fail at, and the checklist for
adding a fifth source.

[ALGORITHMS.md](ALGORITHMS.md) §6–7 covers the dedup and taxonomy algorithms themselves.
[ingestion.md](ingestion.md) is the one-page reference version of this document.

---

## 1. The shape

```
                 ADAPTERS registry  (adapters/__init__.py)
                 ┌──────────┬───────────────────┬──────────────┬──────────┐
                 │ places   │ facebook_events   │ ticketmaster │ fixtures │
                 └────┬─────┴─────────┬─────────┴──────┬───────┴────┬─────┘
                      │               │                │            │
                      └───────────────┴────── fetch() ─┴────────────┘
                                          │  list[RawItem]
                                          ▼
   normalize_all   guess a category for records that came without one
                                          ▼
   deduplicate     block → fuzzy score → (Haiku for the ambiguous band)
                                          ▼           ╲
                   canonical: new cards                ╲ merges: refs folded onto
                                          ▼             ╲ existing cards' `sources`
   embed           voyage-3.5, batches of 16
                                          ▼
   upsert          ON CONFLICT (source, source_url) DO UPDATE
                                          ▼
                                       items
```

One entrypoint, one source per invocation:

```bash
python -m app.ingestion.runner --source=places
```

In the cluster each source is its own CronJob running the **same image** as the API with a different
`--source`:

| Source | Schedule | Why that cadence |
|---|---|---|
| `places` | `0 4 * * 1` — Mondays 04:00 | The Royal Castle does not move. |
| `facebook_events` | `0 */6 * * *` | Events appear and get cancelled all day. |
| `ticketmaster` | `0 */12 * * *` | Concert announcements are regular but not hourly. |
| `fixtures` | never scheduled | Local demo data only. |

The CronJobs run with `DB_BOOTSTRAP=false`, `concurrencyPolicy: Forbid`, `readOnlyRootFilesystem`,
dropped capabilities and a non-root user. They get exactly three secrets: the database URL, the
Voyage key, the Anthropic key — no ingress, no session secret.

---

## 2. The adapter contract

`backend/app/ingestion/adapters/base.py`

```python
class SourceAdapter(ABC):
    source_name: str
    @abstractmethod
    def fetch(self) -> list[RawItem]: ...
```

That is the whole interface. **Only `fetch()` differs between sources** — normalisation, dedup,
embedding and upsert are shared, which is what keeps "add a source" at roughly one file.

`RawItem` is a plain dataclass, not a SQLAlchemy model, so an adapter cannot accidentally hold a
session open or half-write a row. Two of its fields are not for adapters to touch:

| Field | Filled by | Note |
|---|---|---|
| `embedding` | the pipeline | Adapters never call Voyage. |
| `sources` | dedup | The provenance list after merging. |

The fields an adapter *must* produce for a usable card: `kind` (`event` or `place`, CHECK-constrained
in the DB), `name`, `source`, `source_url`, and for events a `starts_at`. Everything else is
optional, and the pipeline fills what it can.

`source_url` deserves emphasis: `(source, source_url)` is the upsert key
(`uq_items_source_url`), so it is what makes re-running a source update rows instead of duplicating
them. An adapter that emits a `NULL` or unstable `source_url` will grow the table on every run.

---

## 3. The four sources

### 3.1 `places` — OpenStreetMap + Wikidata

Keyless, and the only source that needs no account at all. One Overpass query against
`area["name"="Warszawa"]["admin_level"="6"]`, matching `tourism`, `historic` and `leisure=park`
objects.

**The notability filter is `["wikidata"]` on every match.** Not a rating, not a popularity score —
whether the object carries a Wikidata Q-id. Benches, bus shelters and playgrounds never do; the Royal
Castle, Łazienki and POLIN always do. It cuts the map noise at query level, so we never download it,
and it doubles as the enrichment key.

`out center tags` is what makes ways and relations usable: a node has `lat`/`lon`, a polygon does not,
and `center` gives a computed centroid for both.

Categories come from an ordered rule table, and the order is the algorithm:

```python
("tourism", "museum", "museum"), ("historic", "castle", "castle"), ..., ("leisure", "park", "walk")
```

The Royal Castle is `tourism=attraction` **and** `historic=castle`. Scanned in the other order it
becomes a "walk".

Overpass rejects requests without a descriptive `User-Agent` (406), so one is set explicitly — the
same one the Wikidata calls use.

**Enrichment** (`ingestion/wikidata.py`) turns a Q-id into a description and a photo, both free:

- photo: Wikidata claim **P18** → a Commons file URL;
- description: the intro paragraph of the Wikipedia article (`prop=extracts&exintro`), **English
  preferred, Polish as fallback**, with the one-line Wikidata description as a last resort, trimmed to
  800 characters.

Batched at 50 entities (`wbgetentities` limit) and 20 titles (`exlimit`) per request. The subtle part
is title mapping: the MediaWiki API normalises and follows redirects, so the title you asked for is
often not the title in the response. `_fetch_extracts` walks the `normalized` + `redirects` chains
back to the requested title (with a `seen` set, because a redirect loop would otherwise hang).

Why put this much work into descriptions: **the description is the bulk of what gets embedded**
(`card_text` = name + category + description). A place with no description is a place that semantic
search can only find by its name.

### 3.2 `facebook_events` — via Apify

We do not scrape Facebook. The Apify actor `apify~facebook-events-scraper` does, and we call its REST
API — `run-sync-get-dataset-items` starts the run and returns the dataset in one HTTP call, capped
around five minutes (our timeout: 330 s). Paid per use on the Apify side.

Two filters that matter:

- **The bounding box.** Searching "Warsaw" also returns Warsaw, Virginia. `WARSAW_BBOX` keeps only
  events whose coordinates fall in the metro area — lat 51.9–52.4, lon 20.7–21.4.
- **`isCanceled` / `isPast` / `isOnline`** are dropped outright, as is any event missing a name, a URL
  or a start date. A card you cannot link to or date is not a card.

The token travels in an `Authorization` header, **not** as a `?token=` query parameter, because httpx
logs the full request URL and a URL-embedded token would land in the pod logs and from there in ELK.
`runner.py` additionally pins `logging.getLogger("httpx")` to WARNING as defence in depth. See
[SECURITY.md](SECURITY.md) §7.

### 3.3 `ticketmaster` — Discovery API

Only the Consumer Key is needed (the Secret belongs to other Ticketmaster APIs). Paged: `size=100`,
sorted by date ascending, stopping at `MAX_EVENTS = 150` or when `page + 1 >= totalPages`. The API
rejects `page * size >= 1000`, which the cap keeps us well under.

The retry loop distinguishes two kinds of failure, which is the part worth copying into a new
adapter:

```python
except httpx.TransportError as err:   last_error = err            # retry
else:
    if response.status_code < 500:    response.raise_for_status()  # do NOT retry
    last_error = HTTPStatusError(...)                              # 5xx → retry
```

A 401 or a 400 is a configuration bug and retrying it three times just delays the error message. A
connection reset or a 503 is transient. Backoff is `2**attempt * 3` seconds.

Prices are real here (`priceRanges`), which makes this the source that actually exercises the budget
filter.

### 3.4 `fixtures` — the keyless demo set

~100 bundled events from `app/ingestion/fixtures/test_events.json`, loaded with no external call and
no API key. This is what `make stack-init` seeds, and it is why a fresh machine can show a working
catalog in about a minute.

Dates are **relative**: each record carries `in_days` / `hour` / `duration_hours` and the adapter
resolves them against `now` in `Europe/Warsaw`, so the demo events are always upcoming no matter when
you seed.

Every card is marked twice — `[TEST]` prefixed on the name and a `⚠ Sample TEST event` marker line
appended to the description — so demo data can never be mistaken for a real listing, in the UI or in
a database someone inherits.

Without a Voyage key these cards are inserted unembedded: they appear in `/upcoming` and are findable
by the lexical leg, just not semantically. That is the honest degraded demo, and it works.

---

## 4. The pipeline, stage by stage

`backend/app/ingestion/pipeline.py`

### 4.1 `fetch` — one source's failure is that source's problem

```python
try: raw_items = adapter.fetch()
except Exception:
    log.exception("[%s] fetch failed — aborting this source's run", source)
    return
```

Overpass being down must not surface as a raw traceback from a CronJob, and must not affect the other
three sources — which is precisely why each source is its own CronJob rather than one "ingest
everything" job.

### 4.2 `normalize_all` — one bad record is not a bad batch

Per-record `try`, failures counted and logged, survivors continue. Normalisation currently only fills
a missing category via `guess_category`, but the loop shape is the contract: **a malformed record
from a source may not throw away the other 99**.

### 4.3 `deduplicate` — before embedding, deliberately

Order matters for cost. Dedup first means duplicates are folded *before* anyone pays to embed them.
It also means the merge decision is made against the current DB state in a short transaction that
commits and closes before the slow part starts.

```python
with SessionLocal() as session:
    existing = list(session.scalars(select(Item)))
    canonical, merges = deduplicate(items, existing, make_haiku_adjudicator())
    _apply_merges(session, merges)
    session.commit()
```

`make_haiku_adjudicator()` returns `None` when there is no Anthropic key, and `deduplicate` handles
`None` by treating the ambiguous band as "not a match". Keyless ingestion still dedups — just by
string score alone.

`_apply_merges` reassigns the whole list (`item.sources = refs`) rather than appending in place,
because SQLAlchemy does not track mutation *inside* a JSONB value. Appending to `item.sources`
directly leaves the change unflushed and silently lost. Loading every existing `Item` into memory is
fine at a few thousand cards and is the first thing to revisit at a hundred thousand.

### 4.4 `embed` — batch failures are survivable, individually

Each batch of 16 is embedded in its own `try`. A failed batch is logged and skipped; the rest still
produce vectors. The cards from a failed batch are not dropped — they flow on to the upsert with
`refresh_embedding=False`.

Every card is re-embedded on every run. At a few hundred cards per source that is cheaper than
tracking what changed; the `TODO` in the code marks tens of thousands as the point where that stops
being true.

### 4.5 `upsert` — the embedding-erasure trap

```python
upsert(embedded,     refresh_embedding=True)
upsert(not_embedded, refresh_embedding=False)
```

This split is the most important five lines in the file. `ON CONFLICT DO UPDATE` refreshes name,
description, category, coordinates, prices, image, dates and opening hours — always. It refreshes
`embedding` **only when this run actually computed one**.

Without the split, running an ingest without a Voyage key (or with Voyage rate-limiting) would
overwrite every existing vector with `NULL` and silently turn off semantic search for the whole
catalog. The failure would be invisible: no error, no empty table, just worse results.

### 4.6 The run summary

```
[places] fetched 412 → 380 new cards (380 embedded, 0 without fresh vector);
         merged 12 into existing, folded 20 within batch
```

Five numbers, each of which answers a different question: did the source return anything, how much of
it was new, did embedding work, is cross-source dedup firing, is the source duplicating itself.
`folded` is derived (`len(items) - len(canonical) - len(merges)`), so a negative or absurd value in
that log line means the dedup accounting is broken.

---

## 5. Adding a source

1. **Write the adapter.** `backend/app/ingestion/adapters/<source>.py`, subclass `SourceAdapter`, set
   `source_name`, implement `fetch() -> list[RawItem]`. Emit a stable `source_url`. Put any API
   credential in `config.py` as `Optional` and raise a clear `RuntimeError` from `fetch()` when it is
   missing.
2. **Register it.** One line in `adapters/__init__.py`. `runner.py` picks up the choices from the
   registry, so `--source=<name>` works immediately with no argparse change.
3. **Map categories.** A source-specific label map for what the source provides, and let
   `taxonomy.guess_category` handle the rest.
4. **Add the CronJob.** Copy a block in `deploy/cloud/k8s/50-cronjobs.yml`, change the name, the
   `--source` and the schedule, and add any new secret key to the manifest and to
   `secret.example.yml`.
5. **Check dedup blocks against the existing catalog.** If the new source is events, its cards land in
   `("day", date)` blocks alongside Facebook and Ticketmaster and will start merging immediately —
   run it once and read the `merged`/`folded` counts before trusting it.

Local smoke test, no cluster needed:

```bash
make stack-up
docker compose -f deploy/local/docker-compose.yml exec api \
  python -m app.ingestion.runner --source=<name>
```

---

## 6. Cost and quota, per run

| Source | Money | Limit that actually bites |
|---|---|---|
| `places` | free | Overpass fair use — hence weekly, and the `wikidata` filter keeping the result set small |
| `facebook_events` | Apify per-use | `MAX_EVENTS = 100` per run |
| `ticketmaster` | free tier | 5000 calls/day, `(page * size) < 1000` |
| `fixtures` | free | none |
| Embeddings | Voyage per-token | Tokens-per-minute on the free tier — the reason `BATCH_SIZE` is 16 |
| Dedup adjudication | Haiku, a few calls | Only the 75–89 score band reaches it |
