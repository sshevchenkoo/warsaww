"""Local demo dataset: ~100 diverse, clearly-marked TEST events.

Loads bundled sample data (no external API, no keys) so a fresh machine can be
seeded with a browseable catalog in seconds:

    python -m app.ingestion.runner --source=fixtures

Every card is unmistakably a test: the name is prefixed ``[TEST]`` and the
description ends with a marker line, so seeded demo data is never confused with
real listings. Dates are relative to now (from each record's ``in_days``), so the
events always land in the upcoming feed regardless of when you seed.

Without a Voyage key the pipeline still inserts these cards (just without vectors,
so they show in the feed and lexical search); with a Voyage key they are embedded
and become semantically searchable like any other source.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.ingestion.adapters.base import RawItem, SourceAdapter

_DATA = Path(__file__).resolve().parent.parent / "fixtures" / "test_events.json"
_WARSAW = ZoneInfo("Europe/Warsaw")

# Shown on every seeded card so demo data is never mistaken for a real listing.
TEST_MARKER = "⚠ Sample TEST event — demo data, not a real listing."


class FixturesAdapter(SourceAdapter):
    source_name = "fixtures"

    def fetch(self) -> list[RawItem]:
        records = json.loads(_DATA.read_text(encoding="utf-8"))
        now = datetime.now(_WARSAW)
        items: list[RawItem] = []
        for i, rec in enumerate(records):
            start = (now + timedelta(days=rec["in_days"])).replace(
                hour=rec["hour"] % 24, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(hours=rec["duration_hours"])
            items.append(
                RawItem(
                    kind="event",
                    name=f"[TEST] {rec['name']} — {rec['area']}",
                    description=f"{rec['description']}\n\n{TEST_MARKER}",
                    category=rec["category"],
                    lat=rec["lat"],
                    lon=rec["lon"],
                    price_from=rec.get("price_from"),
                    price_to=rec.get("price_to"),
                    image_url=rec.get("image_url"),
                    source=self.source_name,
                    source_url=f"fixtures://test-event/{i}",
                    starts_at=start,
                    ends_at=end,
                )
            )
        return items
