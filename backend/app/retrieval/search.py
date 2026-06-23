from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.catalog.models import Item
from app.config import settings
from app.llm.schemas import Intent


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def search_items(
    session: Session,
    intent: Intent,
    query_embedding: list[float] | None = None,
    limit: int = 30,
) -> list[Item]:
    """Hybrid search: SQL filters from the intent + vector similarity.

    With an embedding the candidates come back ordered by semantic
    closeness to the prompt (`<=>` = cosine distance, HNSW index);
    without one (no Voyage key) it degrades to plain SQL filters."""
    query = select(Item)

    date_from, date_to = _dt(intent.date_from), _dt(intent.date_to)
    if date_from and date_to:
        query = query.where(
            or_(Item.starts_at.between(date_from, date_to), Item.is_permanent.is_(True))
        )

    if intent.budget_max is not None:
        query = query.where(or_(Item.price_from <= intent.budget_max, Item.price_from.is_(None)))

    if intent.categories:
        query = query.where(Item.category.in_(intent.categories))

    if query_embedding is not None:
        distance = Item.embedding.cosine_distance(query_embedding)
        # Keep only semantically close cards; drop the rest so an off-base query
        # yields nothing (and skips the re-rank) instead of returning far junk.
        query = query.where(
            Item.embedding.is_not(None), distance <= settings.search_max_distance
        ).order_by(distance)

    return list(session.scalars(query.limit(limit)))
