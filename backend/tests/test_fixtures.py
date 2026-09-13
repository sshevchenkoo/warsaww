"""The local demo dataset (fixtures adapter): 100 clearly-marked TEST events,
loadable with no API keys."""

from datetime import datetime, timezone

from app.ingestion.adapters.fixtures import TEST_MARKER, FixturesAdapter


def test_fixtures_load_100_events():
    items = FixturesAdapter().fetch()
    assert len(items) == 100


def test_every_card_is_marked_as_test():
    items = FixturesAdapter().fetch()
    for it in items:
        assert it.name.startswith("[TEST] ")
        assert TEST_MARKER in (it.description or "")


def test_source_and_urls_are_unique():
    items = FixturesAdapter().fetch()
    assert {it.source for it in items} == {"fixtures"}
    urls = [it.source_url for it in items]
    assert len(set(urls)) == len(urls)  # no duplicate upsert keys


def test_dates_are_in_the_future_and_ordered():
    items = FixturesAdapter().fetch()
    now = datetime.now(timezone.utc)
    for it in items:
        assert it.kind == "event"
        assert it.starts_at is not None and it.ends_at is not None
        assert it.starts_at >= now.astimezone(it.starts_at.tzinfo).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        assert it.ends_at > it.starts_at
