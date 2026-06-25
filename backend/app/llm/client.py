"""Shared Anthropic client.

A new `anthropic.Anthropic()` opens its own connection pool, so constructing one
per request (as intent extraction and re-ranking used to) paid a TLS/handshake
cost on every /search. One process-wide client, created lazily, reuses
connections across requests. The SDK client is thread-safe, which matters
because FastAPI runs sync endpoints in a threadpool.
"""

import anthropic

from app.config import settings

_client: anthropic.Anthropic | None = None


def get_anthropic_client() -> anthropic.Anthropic:
    """Return the process-wide Anthropic client, creating it on first use.

    api_key may be None — the SDK then falls back to the ANTHROPIC_API_KEY env
    var (see app.config)."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client
