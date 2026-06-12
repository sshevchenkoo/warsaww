from dataclasses import asdict

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.catalog.db import Base, SessionLocal, engine
from app.catalog.models import Item
from app.config import settings
from app.ingestion.adapters import ADAPTERS
from app.ingestion.adapters.base import RawItem
from app.ingestion.taxonomy import guess_category
from app.llm.embeddings import card_text, embed_documents


def normalize(raw: RawItem) -> RawItem:
    """Clean up and fill gaps the adapter could not."""
    if raw.category is None:
        raw.category = guess_category(raw.name, raw.description)
    return raw


def embed(items: list[RawItem]) -> bool:
    """Compute embeddings for all cards in the batch. Returns False (and
    leaves the DB embeddings untouched) when VOYAGE_API_KEY is not set.

    A few hundred cards per source make re-embedding the whole batch
    cheaper than tracking what changed. TODO: skip unchanged texts once
    the base grows past tens of thousands."""
    if not settings.voyage_api_key:
        print("VOYAGE_API_KEY not set — skipping embeddings")
        return False
    texts = [card_text(i.name, i.description, i.category) for i in items]
    vectors = embed_documents(texts)
    for item, vector in zip(items, vectors):
        item.embedding = vector
    return True


def upsert(items: list[RawItem], refresh_embedding: bool = False) -> None:
    """Insert by (source, source_url); on conflict refresh the card's data.

    The embedding is overwritten only when this run actually computed it —
    otherwise an ingest without a Voyage key would erase existing vectors."""
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
    if refresh_embedding:
        refreshable.append("embedding")
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

    embedded = embed(items)

    Base.metadata.create_all(engine)
    upsert(items, refresh_embedding=embedded)

    print(f"[{source}] cards loaded: {len(items)}")
