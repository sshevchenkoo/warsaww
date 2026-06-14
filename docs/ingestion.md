# Ingestion

The catalog is filled by an ingestion pipeline with one adapter per source. The
pipeline is shared; only `fetch()` differs between sources. Run it with:

```bash
python -m app.ingestion.runner --source=places
python -m app.ingestion.runner --source=facebook_events
```

In the cluster, each source is its own k8s CronJob (same image, different
`--source`) — see [deployment.md](deployment.md).

## Pipeline

```
fetch (adapter) → normalize → dedup → embed (Voyage) → upsert (Postgres)
```

- **normalize** — fill gaps the adapter couldn't, e.g. guess a missing category
  from name + description via an EN/PL keyword map.
- **dedup** — see below.
- **embed** — `name + description + category` → a Voyage vector. Skipped (and
  existing vectors preserved) when no Voyage key is set.
- **upsert** — `INSERT ... ON CONFLICT (source, source_url) DO UPDATE`, so
  re-running a source updates cards instead of duplicating them. The embedding
  is refreshed only when this run actually computed it.

## Sources

| Source | Type | Provides |
|---|---|---|
| OpenStreetMap (Overpass API) | API, free | Tourist-worthy places: castles, museums, monuments, parks |
| Wikidata / Wikipedia | API, free | Descriptions (article intro) + photos (Commons) by Q-id |
| Facebook Events (via Apify) | API, paid per use | Concerts, parties, local events with dates and venue coordinates |
| Ticketmaster Discovery API | API, free (apikey) | Concerts & shows with dates, venues, prices |
| Google Places | API, cheap | (future) prices, ratings, opening hours enrichment |

### Places — notability filter

Overpass is queried for Warsaw with `tourism` (museum/gallery/attraction/…),
`historic` (castle/palace/monument/…) and `leisure=park`, and **every match must
carry a `wikidata` tag**. That tag is the "worth visiting" signal — significant
places have a Wikipedia/Wikidata entry; benches and playgrounds don't, so they
are cut off at query level. ~385 places for Warsaw. Each is then enriched from
Wikidata: the Wikipedia article intro becomes the description and the Commons
photo (claim P18) becomes the image.

### Facebook events

The Apify "Facebook Events Scraper" actor is called over its REST API. Results
are filtered to a Warsaw bounding box (drops e.g. Warsaw, Virginia), and
canceled / past / online events are skipped. Facebook category labels are mapped
to our taxonomy.

### Ticketmaster Discovery API

Concerts and shows via the Discovery API (`/discovery/v2/events.json`). Only the
**Consumer Key** is needed (`apikey` query param; the Secret is for other
Ticketmaster APIs). The `ticketmaster` adapter searches `city=Warsaw,
countryCode=PL` sorted by date, paginates, and keeps the soonest `MAX_EVENTS`
(150). Maps `name`, `url`, `dates.start.dateTime`, the venue's coordinates,
`priceRanges` → price_from/to, the widest 16:9 image, and the segment
(Music → concert, Arts & Theatre → theatre). Dedup folds these with the other
event sources by day + name.

## Deduplication

The same real-world event can arrive from several sources under slightly
different names. Dedup (`app/ingestion/dedup.py`) compares the incoming batch
both against the existing catalog and against itself:

1. **Blocking** — only compare candidates in the same block (events by start
   day, places by rounded coordinates ≈110 m), so we never compare all-to-all.
2. **Fuzzy match** — rapidfuzz `token_set_ratio` over normalized names
   (lowercased, diacritics/emoji/year/noise stripped, Polish `ł` handled). Score
   ≥ 90 is an automatic duplicate.
3. **Ambiguous band 75–90** — adjudicated by a Claude Haiku "same event?" call
   (sync per pair now; the Batches API at scale).
4. **Merge** — a duplicate does not become its own card; its `(source,
   source_url)` is folded into the canonical card's `sources` list. Rows with
   the same `source_url` are left to the upsert, not treated as duplicates.

Adding a source = a new adapter class + a line in `ADAPTERS` + a CronJob
manifest. Nothing else changes.
