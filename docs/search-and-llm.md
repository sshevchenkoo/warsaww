# Search & LLM

Three models, orchestrated by plain code (no agent framework) — two Claude LLMs
and one embedding model. SDK: the official `anthropic` package for Python.

| Stage | Model | Price /1M | Notes |
|---|---|---|---|
| Prompt → JSON intent | `claude-haiku-4-5` | $1 in / $5 out | Structured outputs (`messages.parse`) → guaranteed valid JSON |
| Re-rank + card blurbs | `claude-sonnet-4-6` | $3 in / $15 out | Streaming (SSE), one blurb per card in the user's language |
| Embeddings | Voyage `voyage-3.5` | — | Multilingual, 1024-dim; Claude has no embeddings endpoint |

Per search ≈ a fraction of a cent on Haiku + a few cents on Sonnet. The main
cost is the re-rank; levers are caching, the top-N size, and (if needed)
switching the re-rank model back to Opus for maximum quality (one config line).

## Request flow

1. **Prompt → intent.** Claude Haiku parses free text into structured JSON
   (categories, date/time, budget, area, free-text gist). The pair is written to
   `intent_logs`.
2. **Hybrid search.** SQL filters from the intent (date, price, category) plus
   vector similarity of the prompt embedding against the `embedding` column, in
   one Postgres query, returning the top-30 candidates.
3. **Re-rank & stream.** Claude Sonnet drops irrelevant candidates, reorders the
   rest, and writes a one-line blurb per card in the user's language. It emits
   one JSON object per line; the backend parses them as they stream and pushes
   them to the frontend over SSE (`intent` → `card`… → `done`).

```sql
-- step 2, simplified:
SELECT * FROM items
WHERE (starts_at BETWEEN $from AND $to OR is_permanent)
  AND (price_from <= $budget OR price_from IS NULL)
  AND (category = ANY($categories) OR $categories IS NULL)
ORDER BY embedding <=> $query_vector   -- <=> = cosine distance, smaller = closer
LIMIT 30;
```

## Embeddings — what and where

An embedding turns text into a vector where semantically close texts get close
vectors, regardless of language. It is the bridge between a free-form prompt and
the stored cards: "zamek królewski" and "old castle" land near each other even
without shared words. The **same model** is used on both sides:

1. **Ingestion (write):** when a card is stored, `name + description + category`
   is embedded into the `embedding` column. For static places, once.
2. **Query (read):** the raw prompt is embedded per request and nearest vectors
   are found in pgvector.

> Vectors from different models are not comparable. Changing the embedding model
> means re-embedding the whole base (minutes at our volume).

## Multilingual behaviour

Prompts work in any language (RU / PL / EN); the multilingual embedding model
matches them to cards regardless of the stored language, and Sonnet writes
blurbs in the prompt's language. The DB stores each card in its source language
(no translation at ingestion time).

## Future: a local intent model

Prompt parsing is the most mechanical LLM call. `intent_logs` accumulates
`prompt → intent` pairs as a fine-tuning dataset; the extractor sits behind an
`IntentExtractor` protocol, so swapping Claude Haiku for a fine-tuned local
model (e.g. Qwen via vLLM with constrained JSON decoding) is a one-line config
change once volume justifies it.
