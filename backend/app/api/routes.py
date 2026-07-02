import json
import logging
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.catalog.db import SessionLocal, get_session
from app.catalog.models import Item, IntentLog
from app.config import settings
from app.llm.embeddings import embed_query
from app.llm.intent import ClaudeIntentExtractor
from app.llm.rerank import rerank_stream
from app.ratelimit import check_search_quota
from app.retrieval.search import search_items

router = APIRouter()

log = logging.getLogger(__name__)


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
def search(req: SearchRequest, request: Request) -> StreamingResponse:
    """Server-Sent Events: an `intent` event, then a `card` event per ranked
    result, then `done`.

    Connection lifecycle: the intent parse and prompt embedding are external
    HTTP calls and the re-rank is a seconds-long LLM stream — none need the DB.
    So a pooled connection is held only for the short window that logs the parse
    and runs retrieval, then released BEFORE streaming. Holding it across the
    stream throttled concurrency hard (managed max_connections=25)."""
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

    # External calls first — no DB connection held during them.
    extractor = ClaudeIntentExtractor()
    started = time.monotonic()
    intent = extractor.extract(req.prompt)
    latency_ms = int((time.monotonic() - started) * 1000)
    # The raw prompt (not the intent) is embedded — it keeps nuances the intent
    # schema drops ("romantic", "with a view"...) and feeds the lexical trigram
    # leg of hybrid search. Skipped for off-topic prompts. A Voyage failure
    # (timeout, rate limit, outage) degrades to the lexical-only leg rather than
    # 500-ing the search — search_items handles query_embedding=None.
    query_embedding = None
    if intent.on_topic and settings.voyage_api_key:
        try:
            query_embedding = embed_query(req.prompt)
        except Exception:
            log.warning("query embedding failed; using lexical retrieval only", exc_info=True)

    # Short-lived DB work, then the connection returns to the pool before the stream.
    with SessionLocal() as session:
        session.add(
            IntentLog(
                user_prompt=req.prompt,
                intent=intent.model_dump(),
                model=settings.intent_model,
                latency_ms=latency_ms,
            )
        )
        session.commit()  # commit BEFORE loading items so they aren't expired on detach
        # Off-topic (gibberish/spam): skip retrieval + re-rank, return empty fast.
        items = (
            search_items(session, intent, query_embedding, text_query=req.prompt)
            if intent.on_topic
            else []
        )
        session.expunge_all()  # detach so cards stay usable after the connection is freed

    def event_stream() -> Iterator[str]:
        yield _sse("intent", intent.model_dump())
        if settings.anthropic_api_key and items:
            emitted: set[uuid.UUID] = set()
            try:
                for item, blurb in rerank_stream(req.prompt, items):
                    emitted.add(item.id)
                    yield _sse("card", _card(item, blurb))
            except Exception:
                # A rerank failure mid-stream (timeout, API/network error, broken
                # output) would otherwise truncate the SSE with no `done`, leaving
                # the client hanging. Emit the candidates the re-ranker hadn't yet
                # returned in raw retrieval order, then close cleanly. On success
                # this except never runs, so the re-ranker's filtering/ordering is
                # preserved and un-picked candidates are NOT dumped.
                log.warning(
                    "rerank stream failed; emitting remaining cards in retrieval order",
                    exc_info=True,
                )
                for item in items:
                    if item.id not in emitted:
                        yield _sse("card", _card(item, None))
        else:
            # No re-ranker available (or off-topic) — emit raw retrieval order.
            for item in items:
                yield _sse("card", _card(item, None))
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
