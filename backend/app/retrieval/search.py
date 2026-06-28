from datetime import datetime

from sqlalchemy import ColumnElement, Select, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.catalog.models import Item
from app.config import settings
from app.llm.schemas import Intent

# Reciprocal Rank Fusion: each leg contributes 1/(RRF_K + rank). The constant
# damps the weight of top ranks so no single leg dominates; 60 is the value from
# the original RRF paper and the common default. Each leg fetches a wider pool
# than the final limit so fusion has material to rerank across.
RRF_K = 60
CANDIDATE_POOL = 50


def _dt(value: str | None) -> datetime | None:
    """Parse an ISO date from the LLM intent, tolerating drift.

    date_from/date_to are produced by the model, so a non-ISO value is
    possible; treat it as 'no bound' rather than 500-ing the search."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _filter_conditions(intent: Intent) -> list[ColumnElement[bool]]:
    """SQL filters derived from the structured intent, applied to every
    retrieval leg so semantic and lexical candidates obey the same bounds."""
    conds: list[ColumnElement[bool]] = []

    date_from, date_to = _dt(intent.date_from), _dt(intent.date_to)
    if date_from and date_to:
        conds.append(
            or_(Item.starts_at.between(date_from, date_to), Item.is_permanent.is_(True))
        )
    if intent.budget_max is not None:
        conds.append(or_(Item.price_from <= intent.budget_max, Item.price_from.is_(None)))
    if intent.categories:
        conds.append(Item.category.in_(intent.categories))
    return conds


def _semantic_leg(
    query_embedding: list[float], conds: list[ColumnElement[bool]]
) -> Select:
    """Top candidates by cosine distance (`<=>`, HNSW index). The
    `search_max_distance` cut keeps only semantically close cards so an off-base
    query contributes nothing rather than far junk."""
    distance = Item.embedding.cosine_distance(query_embedding)
    return (
        select(Item.id.label("id"), func.row_number().over(order_by=distance).label("rank"))
        .where(
            Item.embedding.is_not(None), distance <= settings.search_max_distance, *conds
        )
        .order_by(distance)
        .limit(CANDIDATE_POOL)
    )


def _lexical_leg(text_query: str, conds: list[ColumnElement[bool]]) -> Select:
    """Top candidates by trigram word-similarity of the card name to the query.

    `word_similarity(name, query)` scores how well the name matches the best
    word-window of the (longer) prompt, so "the weeknd" inside "find the weeknd
    saturday" still matches; `<%` is the indexable boolean form (pg_trgm's
    word_similarity_threshold, default 0.6). No distance cut here — an exact
    name match must survive even when the embedding considers it far."""
    sim = func.word_similarity(Item.name, text_query)
    return (
        select(Item.id.label("id"), func.row_number().over(order_by=sim.desc()).label("rank"))
        .where(Item.name.op("<%")(text_query), *conds)
        .order_by(sim.desc())
        .limit(CANDIDATE_POOL)
    )


def _hybrid_search(
    session: Session,
    intent: Intent,
    query_embedding: list[float] | None,
    text_query: str,
    limit: int,
) -> list[Item]:
    """Fuse the semantic and lexical legs with RRF in a single query.

    Each leg ranks its own candidate pool; the ranks are unioned, summed per
    item as RRF scores, and the top `limit` cards are returned in fused order.
    With no embedding (no Voyage key) the lexical leg runs alone."""
    conds = _filter_conditions(intent)

    legs: list[Select] = [_lexical_leg(text_query, conds)]
    if query_embedding is not None:
        legs.append(_semantic_leg(query_embedding, conds))

    ranked = (legs[0] if len(legs) == 1 else union_all(*legs)).subquery()
    rrf = func.sum(1.0 / (RRF_K + ranked.c.rank)).label("rrf")
    fused = (
        select(ranked.c.id, rrf)
        .group_by(ranked.c.id)
        .order_by(rrf.desc())
        .limit(limit)
        .subquery()
    )
    stmt = select(Item).join(fused, Item.id == fused.c.id).order_by(fused.c.rrf.desc())
    return list(session.scalars(stmt))


def _semantic_search(
    session: Session,
    intent: Intent,
    query_embedding: list[float] | None,
    limit: int,
) -> list[Item]:
    """Pure semantic search: SQL filters + (optional) vector similarity order.

    Without an embedding it degrades to plain SQL filters. This is the
    pre-hybrid path, kept behind `settings.hybrid_search` for A/B comparison."""
    query = select(Item).where(*_filter_conditions(intent))
    if query_embedding is not None:
        distance = Item.embedding.cosine_distance(query_embedding)
        query = query.where(
            Item.embedding.is_not(None), distance <= settings.search_max_distance
        ).order_by(distance)
    return list(session.scalars(query.limit(limit)))


def search_items(
    session: Session,
    intent: Intent,
    query_embedding: list[float] | None = None,
    text_query: str | None = None,
    limit: int = 30,
) -> list[Item]:
    """Retrieve candidate cards for re-ranking.

    Hybrid (default): fuse semantic (pgvector) and lexical (pg_trgm) retrieval
    via RRF — see `_hybrid_search`. Falls back to pure semantic search when
    hybrid is disabled or no query text is available."""
    if settings.hybrid_search and text_query:
        return _hybrid_search(session, intent, query_embedding, text_query, limit)
    return _semantic_search(session, intent, query_embedding, limit)
