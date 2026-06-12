"""Embeddings via Voyage AI (voyage-3.5, multilingual, 1024 dims).

The SAME model embeds both sides: cards at ingestion time ("document")
and the user prompt at search time ("query"). Changing the model means
re-embedding the whole base — that is why it lives in one module.
"""

import httpx

from app.config import settings

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
BATCH_SIZE = 128


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
        response = httpx.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
            json={
                "input": texts[i : i + BATCH_SIZE],
                "model": settings.embedding_model,
                "input_type": input_type,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda d: d["index"])
        vectors.extend(d["embedding"] for d in data)
    return vectors


def card_text(name: str, description: str | None, category: str | None) -> str:
    """The exact text that represents a card in vector space."""
    parts = [name]
    if category:
        parts.append(f"({category})")
    if description:
        parts.append(description)
    return " ".join(parts)
