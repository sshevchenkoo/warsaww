import json
import time
import uuid
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.catalog.db import get_session
from app.catalog.models import Item, IntentLog
from app.config import settings
from app.llm.embeddings import embed_query
from app.llm.intent import ClaudeIntentExtractor
from app.llm.rerank import rerank_stream
from app.retrieval.search import search_items

router = APIRouter()


class SearchRequest(BaseModel):
    prompt: str


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


@router.post("/search")
def search(req: SearchRequest, session: Session = Depends(get_session)) -> StreamingResponse:
    """Server-Sent Events: an `intent` event, then a `card` event per ranked
    result, then `done`. The DB/LLM prep runs before streaming starts."""
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

    # The raw prompt (not the intent) is embedded — it keeps nuances the
    # intent schema drops ("romantic", "with a view"...).
    query_embedding = embed_query(req.prompt) if settings.voyage_api_key else None
    items = search_items(session, intent, query_embedding)

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
