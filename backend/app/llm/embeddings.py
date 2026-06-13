"""Embeddings via Voyage AI (voyage-3.5, multilingual, 1024 dims).

The SAME model embeds both sides: cards at ingestion time ("document")
and the user prompt at search time ("query"). Changing the model means
re-embedding the whole base — that is why it lives in one module.
"""

import time

import httpx

from app.config import settings

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
BATCH_SIZE = 64  # smaller batches stay under the per-minute token limit
MAX_RETRIES = 6


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed card texts at ingestion time."""
    return _embed(texts, input_type="document")


def embed_query(text: str) -> list[float]:
    """Embed the user prompt at search time."""
    return _embed([text], input_type="query")[0]


def _embed(texts: list[str], input_type: str) -> list[list[float]]:
    if not settings.voyage_api_key:
        raise RuntimeError("VOYAGE_API_KEY is not set in .env")

    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        payload = {
            "input": texts[i : i + BATCH_SIZE],
            "model": settings.embedding_model,
            "input_type": input_type,
        }
        data = _post_with_retry(payload)
        ordered = sorted(data["data"], key=lambda d: d["index"])
        vectors.extend(d["embedding"] for d in ordered)
    return vectors


def _post_with_retry(payload: dict) -> dict:
    """POST one batch, backing off on 429 (rate / token-per-minute limit)."""
    for attempt in range(MAX_RETRIES):
        response = httpx.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
            json=payload,
            timeout=120,
        )
        if response.status_code == 429 and attempt < MAX_RETRIES - 1:
            retry_after = response.headers.get("retry-after")
            wait = float(retry_after) if retry_after else 2**attempt * 5
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("Voyage rate limit: retries exhausted")


def card_text(name: str, description: str | None, category: str | None) -> str:
    """The exact text that represents a card in vector space."""
    parts = [name]
    if category:
        parts.append(f"({category})")
    if description:
        parts.append(description)
    return " ".join(parts)
