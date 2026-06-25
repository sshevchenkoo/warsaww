import logging
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.catalog.db import Base, SessionLocal, engine
from app.catalog.models import Item
from app.config import settings
from app.ingestion.adapters import ADAPTERS
from app.ingestion.adapters.base import RawItem
from app.ingestion.dedup import deduplicate, make_haiku_adjudicator
from app.ingestion.taxonomy import guess_category
from app.llm.embeddings import BATCH_SIZE, card_text, embed_documents

log = logging.getLogger(__name__)


def normalize(raw: RawItem) -> RawItem:
    """Clean up and fill gaps the adapter could not."""
    if raw.category is None:
        raw.category = guess_category(raw.name, raw.description)
    return raw


def normalize_all(raw_items: list[RawItem]) -> list[RawItem]:
    """Normalize every record, skipping (not aborting on) the bad ones.

    One malformed record from a source must not throw away the rest of the
    batch — failures are logged and counted, survivors continue down the
    pipeline."""
    items, failed = [], 0
    for raw in raw_items:
        try:
            items.append(normalize(raw))
        except Exception:
            failed += 1
            log.warning("normalize failed for %r — skipping",
                        getattr(raw, "name", "?"), exc_info=True)
    if failed:
        log.warning("normalize: skipped %d/%d malformed records", failed, len(raw_items))
    return items


def embed(items: list[RawItem]) -> list[RawItem]:
    """Compute embeddings per batch and return only the cards that got one.

    Returns an empty list (and leaves DB embeddings untouched) when
    VOYAGE_API_KEY is not set. A single failing batch — a 429 storm or a bad
    response — is logged and skipped so the rest of the batches still produce
    vectors, instead of one failure discarding the whole run.

    A few hundred cards per source make re-embedding cheaper than tracking
    what changed. TODO: skip unchanged texts once the base grows past tens of
    thousands."""
    if not settings.voyage_api_key:
        log.warning("VOYAGE_API_KEY not set — skipping embeddings")
        return []
    embedded: list[RawItem] = []
    for start in range(0, len(items), BATCH_SIZE):
        chunk = items[start : start + BATCH_SIZE]
        texts = [card_text(i.name, i.description, i.category) for i in chunk]
        try:
            vectors = embed_documents(texts)
        except Exception:
            log.warning("embedding batch %d–%d failed — leaving those cards "
                        "without a fresh vector", start, start + len(chunk),
                        exc_info=True)
            continue
        for item, vector in zip(chunk, vectors):
            item.embedding = vector
            embedded.append(item)
    return embedded


def upsert(items: list[RawItem], refresh_embedding: bool = False) -> None:
    """Insert by (source, source_url); on conflict refresh the card's data.

    The embedding is overwritten only when this run actually computed it —
    otherwise an ingest without a Voyage key would erase existing vectors."""
    if not items:
        return
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


def _apply_merges(session: Session, merges: list[tuple]) -> None:
    """Append merged source refs onto the existing cards they belong to."""
    for existing_id, ref in merges:
        item = session.get(Item, existing_id)
        if item is None:
            continue
        refs = list(item.sources or [])
        if ref not in refs:
            refs.append(ref)
            item.sources = refs  # reassign so SQLAlchemy flags the JSONB dirty


def run(source: str) -> None:
    adapter = ADAPTERS[source]()
    try:
        raw_items = adapter.fetch()
    except Exception:
        # A source being down/erroring must not surface as a raw traceback from
        # the CronJob; log it and stop this source's run cleanly.
        log.exception("[%s] fetch failed — aborting this source's run", source)
        return
    items = normalize_all(raw_items)

    Base.metadata.create_all(engine)

    # Drop duplicates against the existing catalog and within this batch;
    # a duplicate's source ref is folded into the canonical card instead.
    with SessionLocal() as session:
        existing = list(session.scalars(select(Item)))
        canonical, merges = deduplicate(items, existing, make_haiku_adjudicator())
        _apply_merges(session, merges)
        session.commit()

    # Embed per batch; cards whose batch failed keep their existing vector
    # untouched (upserted with refresh_embedding=False) instead of being lost.
    embedded = embed(canonical)
    embedded_ids = {id(i) for i in embedded}
    not_embedded = [i for i in canonical if id(i) not in embedded_ids]
    upsert(embedded, refresh_embedding=True)
    upsert(not_embedded, refresh_embedding=False)

    folded = len(items) - len(canonical) - len(merges)
    log.info(
        "[%s] fetched %d → %d new cards (%d embedded, %d without fresh vector); "
        "merged %d into existing, folded %d within batch",
        source, len(items), len(canonical), len(embedded), len(not_embedded),
        len(merges), folded,
    )
