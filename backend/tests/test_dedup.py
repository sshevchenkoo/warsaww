"""Dedup unit tests — no DB, no API (adjudicator stubbed where needed)."""

from datetime import datetime
from types import SimpleNamespace

from app.ingestion.adapters.base import RawItem
from app.ingestion.dedup import deduplicate, normalize_name

AUG4 = datetime(2026, 8, 4, 20, 0)
AUG5 = datetime(2026, 8, 5, 20, 0)


def _event(name, source, url, starts_at=AUG4) -> RawItem:
    return RawItem(kind="event", name=name, source=source, source_url=url, starts_at=starts_at)


def _existing(eid, name, url, source="ticketmaster", starts_at=AUG4):
    return SimpleNamespace(
        id=eid,
        name=name,
        source=source,
        source_url=url,
        starts_at=starts_at,
        lat=None,
        lon=None,
    )


def test_normalize_strips_noise_diacritics_emoji():
    assert normalize_name("The Weeknd - Warsaw 2026 🎤") == "the weeknd"
    assert normalize_name("Łazienki Królewskie") == "lazienki krolewskie"


def test_two_night_stand_not_merged():
    # Same artist, consecutive nights — different events, must both survive.
    items = [
        _event("The Weeknd - Warsaw", "facebook", "fb/1", AUG4),
        _event("The Weeknd - Warsaw", "facebook", "fb/2", AUG5),
    ]
    canonical, merges = deduplicate(items, existing=[])
    assert len(canonical) == 2
    assert merges == []


def test_cross_source_merges_into_existing():
    # A source that appends the venue still matches the bare name (token_set).
    existing = [_existing("tm-1", "The Weeknd - Warsaw", "tm/1")]
    items = [_event("The Weeknd | PGE Narodowy", "facebook", "fb/1", AUG4)]
    canonical, merges = deduplicate(items, existing)
    assert canonical == []
    assert merges == [("tm-1", {"source": "facebook", "source_url": "fb/1"})]


def test_within_batch_fold():
    items = [
        _event("Vamos Festival Warsaw", "facebook", "fb/1"),
        _event("Code Vamos Festival Warsaw", "facebook", "fb/2"),
    ]
    canonical, merges = deduplicate(items, existing=[])
    assert len(canonical) == 1
    assert {r["source_url"] for r in canonical[0].sources} == {"fb/1", "fb/2"}


def test_same_source_url_left_to_upsert():
    # A re-run yields the same URL — not a dedup merge; upsert handles it.
    existing = [_existing("fb-1", "The Weeknd - Warsaw", "fb/1", source="facebook")]
    items = [_event("The Weeknd - Warsaw", "facebook", "fb/1", AUG4)]
    canonical, merges = deduplicate(items, existing)
    assert len(canonical) == 1
    assert merges == []


def test_distinct_events_same_night_kept_apart():
    items = [
        _event("RNB SENSATION x THE ONE", "facebook", "fb/1"),
        _event("K-POP PARTY Bollywood Lounge", "facebook", "fb/2"),
    ]
    canonical, merges = deduplicate(items, existing=[])
    assert len(canonical) == 2
    assert merges == []
