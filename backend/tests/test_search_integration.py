"""Search integration tests: exercise the real hybrid retrieval (pgvector
semantic leg + pg_trgm lexical leg + filters) against a live Postgres.

Skipped unless TEST_DATABASE_URL is set (CI provides pgvector; local skips)."""

import os

import pytest
from sqlalchemy.orm import Session

from app.catalog.models import Item
from app.llm.schemas import Intent
from app.retrieval.search import search_items

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)

DIM = 1024


def _vec(hot: int) -> list[float]:
    """A unit vector with a single hot dimension — two different hot indices are
    orthogonal (cosine distance 1.0), the same index gives distance 0."""
    v = [0.0] * DIM
    v[hot] = 1.0
    return v


def _add(session, name, *, embedding=None, category=None, url):
    session.add(
        Item(
            kind="event",
            name=name,
            source="test",
            source_url=url,
            category=category,
            embedding=embedding,
        )
    )


def test_lexical_leg_matches_name_without_embedding(clean_db):
    with Session(clean_db) as s:
        _add(s, "The Weeknd", url="a")
        _add(s, "Chopin piano recital", url="b")
        s.commit()
        # No embedding available → hybrid search runs the lexical (pg_trgm) leg
        # alone. The leg matches a card NAME as a word-window inside the (longer)
        # user prompt — so an exact proper noun in a natural prompt still hits.
        results = search_items(
            s, Intent(), query_embedding=None,
            text_query="tickets for the weeknd this saturday",
        )
    names = [i.name for i in results]
    assert "The Weeknd" in names
    assert "Chopin piano recital" not in names


def test_semantic_leg_returns_near_drops_far(clean_db):
    near, far = _vec(0), _vec(1)  # orthogonal → far is beyond search_max_distance
    with Session(clean_db) as s:
        _add(s, "near card", embedding=near, url="n")
        _add(s, "far card", embedding=far, url="f")
        s.commit()
        results = search_items(
            s, Intent(), query_embedding=near, text_query="no lexical match here"
        )
    names = [i.name for i in results]
    assert "near card" in names       # distance 0 ≤ search_max_distance
    assert "far card" not in names    # distance 1.0 dropped by the cut


def test_category_filter_applied(clean_db):
    q = _vec(0)
    with Session(clean_db) as s:
        _add(s, "a concert", embedding=q, category="concert", url="c")
        _add(s, "a party", embedding=q, category="party", url="p")
        s.commit()
        results = search_items(
            s,
            Intent(categories=["concert"]),
            query_embedding=q,
            text_query="x",
        )
    cats = {i.category for i in results}
    assert cats == {"concert"}  # the party card is filtered out
