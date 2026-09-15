# ALGORITHMS.md — every algorithm in the search path, and why it is that one

The other files in `docs/` are reference: they say what a component is and how to run it. This one is
a cross-section. It names every algorithm that decides *which cards come back and in what order*,
says what it computes, what it was chosen over, and where it lives — so a question of the form "why
did this query return that" has one place to be answered from.

Nothing here is new behaviour. If this file and the code disagree, the code is right and this file is
a bug.

Companions: [SEARCH.md](SEARCH.md) follows one request end to end; [INGESTION.md](INGESTION.md)
covers how the cards being ranked got into the table. The short reference versions are
[search-and-llm.md](search-and-llm.md) and [ingestion.md](ingestion.md).

---

## 1. The constraint everything else is built on

**The LLM is never the index.**

There is an obvious design for this product that we do not use: put the whole catalog in a prompt,
ask Claude which cards match, done. It works at 50 cards and collapses at 5,000 — every search pays
for the entire catalog in input tokens, and latency scales with the size of the base rather than with
the size of the answer.

So the pipeline is split at a fixed line:

```
  cheap, scales with the catalog          expensive, scales with the answer
  ────────────────────────────────        ────────────────────────────────
  Postgres: filters + vector + trigram  →  Claude: judge ≤30 cards, write 10 blurbs
      milliseconds, no token cost              seconds, a few cents
```

Everything below is a consequence of that line:

- **Postgres has to be good enough to put the right answer in the top 30**, because nothing
  downstream can rescue a card that retrieval never returned. That is why retrieval is hybrid rather
  than pure vector search (§4).
- **The LLM only ever sees a bounded, small input** — 30 candidates, each description truncated to
  220 characters (`rerank.MAX_DESCRIPTION_CHARS`). Cost per search is therefore roughly constant no
  matter how large the catalog grows.
- **Every LLM call is optional.** Intent extraction, query embedding and re-ranking each have a
  degraded path (§2, §3, §6). A search with all three models unavailable still returns lexical
  matches. This is not defensive decoration — it is what lets the stack run on a laptop with no API
  keys at all (`make stack-init`).

---

## 2. Prompt → intent

`backend/app/llm/intent.py`, `backend/app/llm/schemas.py`

A free-form prompt in Russian, Polish or English becomes a small typed object:

```python
class Intent(BaseModel):
    on_topic: bool = True
    categories: list[str] = []      # concert, party, exhibition, theatre, museum, castle, walk, food, family
    date_from: str | None = None    # ISO 8601
    date_to: str | None = None
    budget_max: float | None = None # PLN
    area: str | None = None         # Warsaw district
    free_text: str = ""
```

Model: `claude-haiku-4-5`, via `messages.parse(output_format=Intent)` — the SDK's structured-output
path, so the result is a validated `Intent` rather than a string that has to be JSON-parsed and
then trusted.

### Why a model at all, and not a parser

"Saturday evening", "next weekend", "до 50 злотых", "coś spokojnego nad wodą" — the mapping from
those to a date range and a budget is the part a hand-written parser gets wrong for every language
after the first. The model is given `today` in the system prompt (it has no clock) and returns
absolute ISO bounds.

### `on_topic` — the cheapest guard in the system

`"asdfgh"` and `"what is 2+2"` are not searches. Marking them at the intent stage means
`/search` skips the embedding call, the retrieval query and the whole re-rank — it returns an
`intent` event and `done` in about the time of one Haiku call. Without this, gibberish would still
cost a Voyage embedding plus a Sonnet stream, because vector search always returns *something*.

### Failure is permissive, not fatal

```python
except Exception:
    log.warning("intent extraction failed; falling back to raw retrieval", exc_info=True)
    return Intent(free_text=prompt)
```

A timeout, an API error, a refusal or malformed output must not 500 the request. The fallback
`Intent` is on-topic with no filters, which means retrieval still runs on the raw prompt over both
legs. **The only thing lost is the structured filters** (date/category/budget/area) — the search
degrades from "parties this Saturday under 50 PLN" to "parties", which is a worse answer and not an
error page.

`intent_timeout_s = 15.0` is applied per call with `with_options`, against the client-wide default of
120 s that is sized for the re-rank stream. Without an explicit timeout the SDK default is ten
minutes, long enough for one hung parse to pin a request, its rate-limit slot and the browser's SSE
connection for the whole window.

---

## 3. Text → vector

`backend/app/llm/embeddings.py`

Model: Voyage `voyage-3.5`, multilingual, 1024 dimensions. Claude has no embeddings endpoint, so
this is the one non-Anthropic model in the stack.

### One module, because changing the model means re-embedding everything

Both sides of the comparison must come from the same model and the same version. Cards are embedded
at ingestion time with `input_type="document"`, the prompt at search time with `input_type="query"` —
the asymmetric mode Voyage provides for exactly this (a short query and a long document are
different distributions). Mixing models or dimensions does not error; it silently returns nonsense
distances. Hence `embedding_model` lives in config with a comment that says what changing it costs,
and `EMBEDDING_DIM = 1024` is pinned in the `Item` model.

### What exactly is embedded

```python
def card_text(name, description, category) -> str:
    # "Frederic Chopin Museum (museum) A biographical museum devoted to..."
```

Name, then category in parentheses, then description. Category is in the text on purpose: it puts
"museum" into the vector even for a card whose description never uses the word, which is what makes
`"a quiet museum about Chopin"` land without the SQL category filter having to fire.

On the query side, the **raw prompt is embedded, not `intent.free_text`**. The intent schema is lossy
by design — "romantic", "with a view", "spokojny" survive in the prompt and do not survive the
extraction into categories and dates.

### Batching and the 429 loop

| Constant | Value | Why |
|---|---|---|
| `BATCH_SIZE` | 16 | Small enough that one request fits the free tier's tokens-per-minute limit. A 64-doc batch exceeds it on its own, so the 429s would never clear no matter how long you back off. |
| `MAX_RETRIES` | 6 | With `2**attempt * 5` seconds of backoff, the last wait is ~160 s — past any per-minute window. |

`retry-after` from the response wins over the computed backoff when present. Two details that are
easy to get wrong and are handled explicitly:

- Voyage returns results with an `index` field and **no ordering guarantee**, so the response is
  sorted by `index` before the vectors are appended.
- If the count of returned vectors does not match the count of texts, `_embed` raises rather than
  returning a short list. The caller zips `items` against `vectors` positionally — a short response
  would silently attach the wrong vector to every card after the gap.

---

## 4. Retrieval: two legs and a fusion

`backend/app/retrieval/search.py`

This is the part that decides what the LLM is even allowed to consider. It runs as **one SQL
statement**.

```
                    intent + raw prompt + query vector
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
   semantic leg (pgvector)                  lexical leg (pg_trgm)
   cosine distance, HNSW                    word_similarity on name
   distance <= 0.62                         name <% query
   + the same SQL filters                   + the same SQL filters
   LIMIT 50 → rank                          LIMIT 50 → rank
              └───────────────────┬───────────────────┘
                                  ▼
                    RRF: score = Σ 1 / (60 + rank)
                         GROUP BY id, ORDER BY score
                                  ▼
                          top 30 → re-ranker
```

### 4.1 Why not vector search alone

Dense embeddings are good at meaning and bad at names. `"the weeknd"` is, to a multilingual
embedding model, a slightly odd English noun phrase — the vector for a card named
"The Weeknd | PGE Narodowy" is not reliably close to it, while some generic "live music evening" card
often is. Typos make it worse.

The lexical leg exists for exactly that class of query: proper nouns, venue names, near-misses.

### 4.2 The semantic leg

```python
distance = Item.embedding.cosine_distance(query_embedding)   # the <=> operator
... .where(Item.embedding.is_not(None), distance <= settings.search_max_distance, *conds)
    .order_by(distance).limit(CANDIDATE_POOL)
```

`search_max_distance = 0.62` is the cut that makes an off-base query return *nothing* rather than
the 30 least-bad cards in the catalog. The threshold is empirical for `voyage-3.5`: relevant hits
measure ~0.40–0.56, clearly unrelated ones ~0.62 and up. It is a config value because it is the one
number most likely to need retuning when the catalog composition changes.

Nearest-neighbour search without a threshold always succeeds. That is the failure mode it prevents:
a confidently ranked page of junk is worse than an empty result, because the user cannot tell the
difference between "nothing matches" and "the ranking is broken".

### 4.3 The lexical leg

```python
sim = func.word_similarity(Item.name, text_query)
... .where(Item.name.op("<%")(text_query), *conds).order_by(sim.desc()).limit(CANDIDATE_POOL)
```

`word_similarity(name, query)` — not `similarity(name, query)` — because the two arguments have very
different lengths. `similarity` compares whole strings, so a three-word name scored against a
ten-word prompt is penalised for the seven words it does not contain. `word_similarity` scores the
name against the best-matching *window* of the prompt, so `"the weeknd"` inside
`"find me the weeknd saturday night"` still scores high.

`<%` is the indexable boolean form of the same comparison (threshold from pg_trgm's
`word_similarity_threshold`, default 0.6), which lets `ix_items_name_trgm` — a GIN index with
`gin_trgm_ops` — serve the predicate instead of scanning.

**This leg deliberately has no distance cut.** An exact name match must survive even when the
embedding thinks the card is far away, and that is the whole reason the leg exists.

### 4.4 The filters are shared

`_filter_conditions(intent)` is built once and spliced into both legs. If a filter were applied only
after fusion, a leg could spend its entire 50-row budget on cards that the filter then removes, and
the two legs would be ranking different universes.

| Filter | SQL | The `or_` is not an accident |
|---|---|---|
| Date | `starts_at BETWEEN … OR is_permanent` | The Royal Castle has no `starts_at`. Without the `OR`, asking for "this Saturday" would erase every permanent place from the results. |
| Budget | `price_from <= max OR price_from IS NULL` | Unknown price is the common case in this data. Treating NULL as "too expensive" would delete most of the catalog on any budget query. |
| Category | `category IN (…)` | No `OR`: an explicit category request is a real narrowing. |

Dates come from a model, so `_dt()` parses them defensively — a non-ISO string becomes "no bound"
rather than a 500.

### 4.5 RRF, and why not a weighted score

The two legs produce incomparable numbers. Cosine distance lives in [0, 2] and lower is better;
trigram similarity lives in [0, 1] and higher is better. Blending them (`0.7*cos + 0.3*trgm`) means
inventing a normalisation and then re-tuning it every time the catalog or the embedding model
changes.

Reciprocal Rank Fusion throws the scores away and keeps only the ranks:

```
score(card) = Σ over legs that returned it of  1 / (RRF_K + rank_in_that_leg)
```

| Constant | Value | Why that value |
|---|---|---|
| `RRF_K` | 60 | The value from the original RRF paper and the common default. It damps the top of each leg: rank 1 scores 1/61 and rank 2 scores 1/62, a 1.6% gap rather than the 2× gap that `k=0` would give. So one leg being very confident does not let it dictate the fused order — and a card returned by *both* legs beats a card that only one leg loved. |
| `CANDIDATE_POOL` | 50 | Each leg fetches wider than the final 30 so fusion has material to work across. Equal for both legs, so neither is structurally favoured. |

Implementation detail worth knowing before editing: the ranks come from
`row_number() OVER (ORDER BY …)` inside each leg, the legs are `UNION ALL`-ed, and the sum is a
`GROUP BY id` over that union. One statement, one round trip, no application-side merging.

With no embedding available (no Voyage key, or the embedding call failed) the list of legs is just
the lexical one and the same fusion code runs unchanged over a single leg.

### 4.6 HNSW recall under filters

```python
SET LOCAL hnsw.ef_search = 100
SET LOCAL hnsw.iterative_scan = relaxed_order
```

An HNSW index returns approximate neighbours from a candidate list of size `ef_search` (default 40).
Postgres then applies the `WHERE` filters to those candidates. With a selective filter — "theatre,
this Saturday, under 50 PLN" — most of the 40 are removed and the query returns three rows, not
because only three match but because the index never looked further.

pgvector ≥ 0.8's iterative scan fixes this: it keeps probing past `ef_search` until enough rows
survive the filter. `relaxed_order` trades exact distance ordering for recall, which is free here —
the LLM re-ranker reorders everything anyway, so the only thing that matters from this stage is
*which* cards come back, not their exact order.

`SET LOCAL` scopes both settings to the current transaction, so they cannot leak onto the next
request that borrows the same pooled connection. The mode is validated against
`_ITERATIVE_SCAN_MODES` before interpolation, because `SET LOCAL` cannot take a bound parameter and
the value would otherwise be injected string into SQL.

### 4.7 The pre-hybrid path is still there

`settings.hybrid_search = False` falls back to `_semantic_search` — filters plus vector ordering,
no lexical leg, no fusion. Kept for A/B comparison against the previous behaviour, and it is the
honest way to answer "did hybrid actually help" for a given query.

---

## 5. Re-ranking and blurbs

`backend/app/llm/rerank.py`

Input: the user's raw query and up to 30 candidates. Output: a stream of `(item, blurb)` pairs, best
first, at most 10.

Model: `settings.rerank_model`, currently `claude-sonnet-4-6`, called with
`thinking={"type": "adaptive"}` and `max_tokens=8192`.

### The wire format is one JSON object per line

```
{"n": 7,  "blurb": "Kameralne muzeum Chopina w Pałacu Gnińskich — cicho i blisko centrum."}
{"n": 2,  "blurb": "..."}
```

Not one JSON array, and that is the entire point. An array can only be parsed once it is closed, so
the first card would appear after the last token. Line-delimited objects can be parsed as they
arrive: `rerank_stream` accumulates into a buffer, splits on `\n`, and yields each complete line
immediately. The user sees card 1 while the model is still writing card 6.

Candidates are sent as a numbered block and the model returns the number, not the name or the id.
It is fewer tokens, and it makes hallucination structurally detectable — `n` either indexes into the
list we sent or it does not.

### `_parse_line` is total, never raising

```python
line = line.strip().rstrip(",")
if not line.startswith("{"):        return None   # prose, markdown fence, blank line
try: obj = json.loads(line)
except json.JSONDecodeError:        return None   # partial or malformed
n = obj.get("n")
if not isinstance(n, int) or not (1 <= n <= len(items)) or n in seen: return None
```

Four separate things this drops on the floor: a preamble line the model wrote despite the
instruction, a malformed object, an out-of-range `n` (a hallucinated candidate number), and a
**repeat** of an already-emitted `n`. The `seen` set is what stops one duplicated line from showing
the same card twice in the UI.

After the stream ends, the buffer is parsed once more — the final line has no trailing newline, so
without that call the last card would be silently dropped.

### What the re-ranker is allowed to do

Drop candidates, reorder them, and write one sentence each. It is explicitly told to match the
language of the query and not to drift to a related one (the RU/PL/EN confusion is real and users
notice it immediately). It never invents a card: every emitted item is `items[n-1]`, an object that
came out of Postgres.

---

## 6. Deduplication

`backend/app/ingestion/dedup.py`

Runs at ingestion time, not at search time — see [INGESTION.md](INGESTION.md) for where it sits in
the pipeline. It belongs in this document because it decides what a "card" is.

The same real-world event arrives from several sources under different names:
`"The Weeknd - Warsaw"`, `"The Weeknd | PGE Narodowy"`, `"THE WEEKND ✨ Warszawa 2026"`. Three cards
for one concert reads as spam.

### 6.1 Normalisation

```python
def normalize_name(name: str) -> str:
    # NFKD, strip combining marks, strip non-alphanumerics, drop noise tokens and bare numbers
```

`unicodedata.normalize("NFKD", …)` plus dropping combining characters handles `ą ę ó ś ż` and
strips emoji and punctuation. It does **not** handle `ł`, `ø`, `đ` — those are single code points
with no decomposition, so they get an explicit `_STROKE` translation table first. Miss that and
"Łazienki" and "Lazienki" are different entities.

Noise tokens (`warsaw`, `warszawa`, `poland`, `official`, `save`, `date`) and bare numbers (years)
are dropped: every card in this catalog is in Warsaw, so the token carries no discriminating
information and its presence in one source's naming convention would otherwise raise every pairwise
score.

### 6.2 Blocking, so the comparison is not quadratic

Comparing every incoming card against every existing card is O(n·m). Instead each card gets a block
key and only cards sharing a key are ever compared:

| Card has | Block key | Cell size |
|---|---|---|
| `starts_at` | `("day", <date>)` | one calendar day |
| `lat`/`lon` | `("geo", round(lat,3), round(lon,3))` | ~110 m |
| neither | `("name", <first 4 chars of normalized name>)` | crude, but it is the fallback |

This is also a correctness statement, not just an optimisation: two concerts on different days are
not the same event, however similar their names. The block encodes that.

### 6.3 Scoring and the three bands

`rapidfuzz.fuzz.token_set_ratio` — chosen over `ratio` because it scores a *subset* highly. "The
Weeknd" inside "The Weeknd | PGE Narodowy" is the normal shape of this data: one source appends the
venue, another does not.

| Score | Decision | Cost |
|---|---|---|
| ≥ 90 (`AUTO_MATCH`) | same entity | free |
| 75–89 (`AMBIGUOUS`) | ask Claude Haiku: "same real-world event? yes/no" | one tiny call per pair |
| < 75 | different entities | free |

The middle band is a handful of pairs per run, which is why a synchronous per-pair call is
acceptable. At a larger catalog this moves to the Batches API — that is a scale decision, not a
design one.

Two guards in `_best_match`: an empty normalised name (the name was *all* noise) never matches
anything, and when checking against the DB, candidates with the same `source_url` are skipped —
that case belongs to the `(source, source_url)` upsert, not to fuzzy matching.

If the adjudicator call fails, it returns `False`. The conservative direction is **keep both cards**:
a visible duplicate is a cosmetic bug, a wrongly merged pair silently loses a real event.

### 6.4 What a merge actually does

A duplicate is never inserted as its own row. Its `(source, source_url)` reference is appended to the
canonical card's `sources` JSONB list. One card, several provenance links — so the UI can show "also
on Ticketmaster" instead of a second tile.

`deduplicate` handles both directions in one pass: against cards already in the DB (producing
`merges`, applied by id) and against cards seen earlier *in the same batch* (folded directly into the
twin's `sources`).

---

## 7. Category fallback

`backend/app/ingestion/taxonomy.py`

Sources leave the category empty most of the time (Facebook fills it for roughly 20% of events).
Vector search does not need one; the SQL category filter and the card badge do.

A table of `(category, [keywords])` scanned in order over `name + description`, lowercased, first
match wins. Ordering is the algorithm: `party` before `concert`, because "techno party with a live
set" is a party, and a keyword list scanned in the other order would call it a concert. Keywords
cover English and Polish, and several are deliberately truncated stems (`symphon`, `restauracj`,
`degustac`) so they match across inflections.

Not a model, on purpose: this runs over every ingested record on every run, the failure mode is a
wrong badge rather than a wrong answer, and a table is greppable and free.

---

## 8. Every tunable in one place

| Constant | Where | Value | What happens if you move it |
|---|---|---|---|
| `search_max_distance` | `config.py` | 0.62 | Lower → stricter, off-base queries return empty sooner, real hits start disappearing below ~0.55. Higher → junk re-enters the candidate pool and the LLM pays to reject it. |
| `RRF_K` | `retrieval/search.py` | 60 | Lower → the top of each leg dominates the fusion. Higher → the legs flatten toward "returned by both" being the only signal. |
| `CANDIDATE_POOL` | `retrieval/search.py` | 50 | Per leg, before fusion. Raising it costs SQL time and helps only if the right card is ranked 50–100 in one leg. |
| `limit` (retrieval) | `search_items` | 30 | The re-ranker's input size — the main driver of re-rank input tokens. |
| `limit` (re-rank) | `rerank_stream` | 10 | Cards the user can actually get. |
| `hnsw_ef_search` | `config.py` | 100 | Index candidate list. Higher = better recall, slower vector leg. |
| `hnsw_iterative_scan` | `config.py` | `relaxed_order` | `off` reproduces the pre-0.8 behaviour where selective filters starve results. |
| `AUTO_MATCH` / `AMBIGUOUS` | `ingestion/dedup.py` | 90 / 75 | Widening the band sends more pairs to Haiku; narrowing it decides more pairs by string score alone. |
| `BATCH_SIZE` | `llm/embeddings.py` | 16 | Tied to the Voyage tokens-per-minute limit, not to performance. |
| `MAX_DESCRIPTION_CHARS` | `llm/rerank.py` | 220 | Per candidate, in the re-rank prompt. The main lever on input token cost. |
| `intent_timeout_s` / `rerank_timeout_s` | `config.py` | 15 / 120 | Both degrade rather than fail on expiry — see [SEARCH.md](SEARCH.md) §5. |

---

## 9. What is deliberately not here

- **No learned ranker.** RRF is unsupervised and needs no click data. There is none yet, and
  `intent_logs` exists to accumulate the dataset that would justify one.
- **No query expansion or HyDE.** Another LLM round trip in front of retrieval, for a gain the
  hybrid lexical leg already covers on the queries that were failing.
- **No cross-encoder.** The Sonnet re-rank *is* the cross-encoder, and it produces the blurb in the
  same pass.
- **No cache on search.** Prompts are free-form, so the hit rate would be near zero; the daily
  per-session quota is the cost control instead (see [SECURITY.md](SECURITY.md) §6).
