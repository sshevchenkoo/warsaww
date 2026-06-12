import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.catalog.db import get_session
from app.catalog.models import IntentLog
from app.config import settings
from app.llm.embeddings import embed_query
from app.llm.intent import ClaudeIntentExtractor
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

    model_config = {"from_attributes": True}


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/search")
def search(req: SearchRequest, session: Session = Depends(get_session)) -> dict:
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

    # The raw prompt (not the intent) is embedded — it keeps nuances
    # the intent schema drops ("romantic", "with a view"...).
    query_embedding = embed_query(req.prompt) if settings.voyage_api_key else None

    items = search_items(session, intent, query_embedding)
    # TODO: re-rank top-30 via Opus (streaming) + SSE to the frontend
    return {
        "intent": intent.model_dump(),
        "items": [ItemOut.model_validate(item).model_dump() for item in items],
    }
