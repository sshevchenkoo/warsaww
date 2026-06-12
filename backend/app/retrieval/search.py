from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.catalog.models import Item
from app.llm.schemas import Intent


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def search_items(session: Session, intent: Intent, limit: int = 30) -> list[Item]:
    """SQL filters from the intent. TODO: + ORDER BY embedding <=> query_vector
    once the embedding model is chosen (Voyage vs bge-m3)."""
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

    return list(session.scalars(query.limit(limit)))
