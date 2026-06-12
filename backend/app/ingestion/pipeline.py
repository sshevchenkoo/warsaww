from dataclasses import asdict

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.catalog.db import Base, SessionLocal, engine
from app.catalog.models import Item
from app.ingestion.adapters import ADAPTERS
from app.ingestion.adapters.base import RawItem
from app.ingestion.taxonomy import guess_category


def normalize(raw: RawItem) -> RawItem:
    """Clean up and fill gaps the adapter could not."""
    if raw.category is None:
        raw.category = guess_category(raw.name, raw.description)
    return raw


def upsert(items: list[RawItem]) -> None:
    """Insert by (source, source_url); on conflict refresh the card's data.

    The embedding is NOT overwritten here — it is recomputed separately
    only when the text actually changed (cheaper than re-embedding all)."""
    rows = [asdict(item) for item in items]
    stmt = pg_insert(Item).values(rows)
    refreshable = [
        "name",
        "description",
        "category",
        "lat",
        "lon",
        "price_from",
        "price_to",
        "image_url",
        "starts_at",
        "ends_at",
        "is_permanent",
        "opening_hours",
    ]
    stmt = stmt.on_conflict_do_update(
        constraint="uq_items_source_url",
        set_={col: getattr(stmt.excluded, col) for col in refreshable},
    )
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()


def run(source: str) -> None:
    adapter = ADAPTERS[source]()
    raw_items = adapter.fetch()
    items = [normalize(r) for r in raw_items]

    # TODO: dedup — rapidfuzz over (name, date, venue), ambiguous pairs
    #       batched to Haiku via the Batches API
    # TODO: embed — name + description + category → embedding,
    #       once the model is chosen (Voyage vs bge-m3)

    Base.metadata.create_all(engine)
    upsert(items)

    print(f"[{source}] cards loaded: {len(items)}")
