"""Facebook events in Warsaw via Apify (Facebook Events Scraper actor).

We do not scrape Facebook ourselves — the Apify actor does, we call its
REST API and get clean JSON back. Requires APIFY_TOKEN in .env (paid
per-usage on the Apify side).

run-sync-get-dataset-items starts the actor and waits for the dataset
in a single HTTP call (capped at ~5 min, fine for small batches).
"""

from datetime import datetime

import httpx

from app.config import settings
from app.ingestion.adapters.base import RawItem, SourceAdapter

ACTOR_ID = "apify~facebook-events-scraper"
RUN_SYNC_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"

MAX_EVENTS = 100

# Searching "Warsaw" also returns Warsaw, Virginia (US) — keep only events
# whose coordinates fall into the Warsaw metro area bounding box.
WARSAW_BBOX = {"lat": (51.9, 52.4), "lon": (20.7, 21.4)}

# Facebook discoveryCategories label → our taxonomy.
CATEGORY_BY_LABEL = {
    "Music": "concert",
    "Party": "party",
    "Art": "exhibition",
    "Theater": "theatre",
    "Comedy": "theatre",
    "Food & Drink": "food",
}


class FacebookEventsAdapter(SourceAdapter):
    source_name = "facebook_events"

    def fetch(self) -> list[RawItem]:
        if not settings.apify_token:
            raise RuntimeError("APIFY_TOKEN is not set in .env")

        # Pass the token in the Authorization header, NOT as a ?token= query
        # param: httpx logs the full request URL, so a URL-embedded token leaks
        # into the pod logs (and ELK). The header is not logged.
        response = httpx.post(
            RUN_SYNC_URL,
            headers={"Authorization": f"Bearer {settings.apify_token}"},
            json={
                "searchQueries": ["Warsaw"],
                "maxEvents": MAX_EVENTS,
            },
            timeout=330,
        )
        response.raise_for_status()

        items: list[RawItem] = []
        for event in response.json():
            item = self._to_raw_item(event)
            if item is not None:
                items.append(item)
        return items

    def _to_raw_item(self, event: dict) -> RawItem | None:
        if event.get("isCanceled") or event.get("isPast") or event.get("isOnline"):
            return None

        name = (event.get("name") or "").strip()
        url = event.get("url")
        starts_at = self._parse_dt(event.get("utcStartDate"))
        # An event without a name, link or date is unusable as a card.
        if not name or not url or starts_at is None:
            return None

        location = event.get("location") or {}
        lat, lon = location.get("latitude"), location.get("longitude")
        if not self._in_warsaw(lat, lon):
            return None

        # Venue name helps both the card and the embedding.
        description = (event.get("description") or "").strip()[:800] or None
        venue = location.get("name")
        if venue and description:
            description = f"Venue: {venue}. {description}"

        return RawItem(
            kind="event",
            name=name,
            source=self.source_name,
            description=description,
            category=self._category(event),
            lat=lat,
            lon=lon,
            image_url=event.get("imageUrl"),
            source_url=url,
            starts_at=starts_at,
            is_permanent=False,
        )

    @staticmethod
    def _in_warsaw(lat, lon) -> bool:
        if lat is None or lon is None:
            return False
        (lat_min, lat_max), (lon_min, lon_max) = (
            WARSAW_BBOX["lat"],
            WARSAW_BBOX["lon"],
        )
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

    @staticmethod
    def _category(event: dict) -> str | None:
        for cat in event.get("discoveryCategories") or []:
            mapped = CATEGORY_BY_LABEL.get(cat.get("label"))
            if mapped:
                return mapped
        # TODO: fallback — keyword heuristic over name+description in normalize()
        return None

    @staticmethod
    def _parse_dt(value) -> datetime | None:
        """The actor returns either ISO strings or epoch timestamps."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            # Epoch in ms if it's too large to be seconds.
            seconds = value / 1000 if value > 1e11 else value
            return datetime.fromtimestamp(seconds).astimezone()
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
