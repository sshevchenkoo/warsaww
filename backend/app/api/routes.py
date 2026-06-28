import json
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.catalog.db import get_session
from app.catalog.models import Item, IntentLog
from app.config import settings
from app.llm.embeddings import embed_query
from app.llm.intent import ClaudeIntentExtractor
from app.llm.rerank import rerank_stream
from app.ratelimit import check_search_quota
from app.retrieval.search import search_items

router = APIRouter()


class SearchRequest(BaseModel):
    # Cap the prompt: it is embedded and sent to the intent LLM, so an unbounded
    # string is a cost/latency abuse vector on the most expensive endpoint.
    prompt: str = Field(min_length=1, max_length=2000)


class ItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    description: str | None
    category: str | None
    price_from: float | None
    price_to: float | None
    image_url: str | None
    source: str
    source_url: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_permanent: bool
    blurb: str | None = None  # one-line pitch written by the re-ranker

    model_config = {"from_attributes": True}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _card(item: Item, blurb: str | None) -> dict:
    out = ItemOut.model_validate(item)
    out.blurb = blurb
    return out.model_dump(mode="json")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/upcoming")
def upcoming(limit: int = 12, session: Session = Depends(get_session)) -> list[ItemOut]:
    """Soonest upcoming events (no prompt, no LLM) — the home-page default feed.
    An event counts as upcoming until it ends (or starts, if it has no end)."""
    now = datetime.now(timezone.utc)
    items = (
        session.query(Item)
        .filter(Item.kind == "event", Item.starts_at.isnot(None))
        .filter(func.coalesce(Item.ends_at, Item.starts_at) >= now)
        .order_by(Item.starts_at.asc())
        .limit(min(max(limit, 1), 48))
        .all()
    )
    return [ItemOut.model_validate(item) for item in items]


@router.get("/items/{item_id}")
def get_item(item_id: uuid.UUID, session: Session = Depends(get_session)) -> ItemOut:
    """Full details for a single card — backs the item detail page."""
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return ItemOut.model_validate(item)


@router.post("/search")
def search(
    req: SearchRequest, request: Request, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Server-Sent Events: an `intent` event, then a `card` event per ranked
    result, then `done`. The DB/LLM prep runs before streaming starts."""
    # Per-session daily quota (the only costly endpoint). Anonymous visitors get
    # a session id so the limit follows them too.
    sid = request.session.get("sid")
    if not sid:
        sid = uuid.uuid4().hex
        request.session["sid"] = sid
    allowed, remaining = check_search_quota(sid)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {settings.search_daily_limit} searches reached. "
            "Try again tomorrow.",
        )

    extractor = ClaudeIntentExtractor()

    started = time.monotonic()
    intent = extractor.extract(req.prompt)
    latency_ms = int((time.monotonic() - started) * 1000)

    session.add(
        IntentLog(
            user_prompt=req.prompt,
            intent=intent.model_dump(),
            model=settings.intent_model,
            latency_ms=latency_ms,
        )
    )
    session.commit()

    # Gibberish / off-topic prompt: skip the costly embedding + vector search +
    # re-rank and return an empty result fast (the frontend shows "nothing matched").
    if not intent.on_topic:
        def empty_stream() -> Iterator[str]:
            yield _sse("intent", intent.model_dump())
            yield _sse("done", {})

        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # The raw prompt (not the intent) is embedded — it keeps nuances the
    # intent schema drops ("romantic", "with a view"...).
    query_embedding = embed_query(req.prompt) if settings.voyage_api_key else None
    # Pass the raw prompt for the lexical (trigram) leg of hybrid search; it
    # carries exact proper nouns the embedding may underweight.
    items = search_items(session, intent, query_embedding, text_query=req.prompt)

    def event_stream() -> Iterator[str]:
        yield _sse("intent", intent.model_dump())
        if settings.anthropic_api_key and items:
            for item, blurb in rerank_stream(req.prompt, items):
                yield _sse("card", _card(item, blurb))
        else:
            # No re-ranker available — emit raw vector-search order.
            for item in items:
                yield _sse("card", _card(item, None))
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
