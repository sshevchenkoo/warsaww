from dataclasses import asdict

from app.catalog.db import Base, SessionLocal, engine
from app.catalog.models import Item
from app.ingestion.adapters import ADAPTERS
from app.ingestion.adapters.base import RawItem


def normalize(raw: RawItem) -> RawItem:
    """Map source categories to our taxonomy, clean up text.
    TODO: source taxonomy mapping ('techno' → 'party' etc.)."""
    return raw


def run(source: str) -> None:
    adapter = ADAPTERS[source]()
    raw_items = adapter.fetch()
    items = [normalize(r) for r in raw_items]

    # TODO: dedup — rapidfuzz over (name, date, venue), ambiguous pairs
    #       batched to Haiku via the Batches API
    # TODO: embed — name + description + category → embedding,
    #       once the model is chosen (Voyage vs bge-m3)

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        # TODO: upsert by (source, source_url) instead of a plain insert
        for item in items:
            session.add(Item(**asdict(item)))
        session.commit()

    print(f"[{source}] cards loaded: {len(items)}")
