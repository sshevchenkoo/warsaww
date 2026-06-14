"""Concerts and shows in Warsaw from the Ticketmaster Discovery API.

Only the Consumer Key is needed (passed as the `apikey` query param) — the
Secret is for other Ticketmaster APIs, not Discovery. Register at
developer.ticketmaster.com. Discovery returns upcoming events only; we sort by
date and keep a light slice (MAX_EVENTS).
"""

import time
from datetime import datetime

import httpx

from app.config import settings
from app.ingestion.adapters.base import RawItem, SourceAdapter

EVENTS_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
PAGE_SIZE = 100  # API max is 200; (page * size) must stay under 1000
MAX_EVENTS = 150
MAX_RETRIES = 3

# Ticketmaster segment → our taxonomy. Unmapped → normalize() guesses.
SEGMENT_CATEGORY = {
    "Music": "concert",
    "Arts & Theatre": "theatre",
}


class TicketmasterAdapter(SourceAdapter):
    source_name = "ticketmaster"

    def fetch(self) -> list[RawItem]:
        if not settings.ticketmaster_api_key:
            raise RuntimeError("TICKETMASTER_API_KEY is not set in .env")

        items: list[RawItem] = []
        page = 0
        while len(items) < MAX_EVENTS:
            payload = self._get_page(page)
            events = payload.get("_embedded", {}).get("events", [])
            if not events:
                break
            for event in events:
                item = self._to_raw_item(event)
                if item is not None:
                    items.append(item)
            page_info = payload.get("page", {})
            if page + 1 >= page_info.get("totalPages", 0):
                break
            page += 1
        return items[:MAX_EVENTS]

    def _get_page(self, page: int) -> dict:
        params = {
            "apikey": settings.ticketmaster_api_key,
            "city": "Warsaw",
            "countryCode": "PL",
            "sort": "date,asc",
            "size": PAGE_SIZE,
            "page": page,
        }
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = httpx.get(EVENTS_URL, params=params, timeout=60)
            except httpx.TransportError as err:
                last_error = err
            else:
                if response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                last_error = httpx.HTTPStatusError(
                    f"{response.status_code}", request=response.request, response=response
                )
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt * 3)
        raise RuntimeError(f"Ticketmaster API unreachable: {last_error}")

    def _to_raw_item(self, event: dict) -> RawItem | None:
        name = (event.get("name") or "").strip()
        url = event.get("url")
        starts_at = _start(event.get("dates", {}).get("start", {}))
        if not name or not url or starts_at is None:
            return None

        venue = (event.get("_embedded", {}).get("venues") or [{}])[0]
        lat, lon = _coords(venue.get("location"))
        price_from, price_to = _price(event.get("priceRanges"))

        venue_name = venue.get("name")
        info = (event.get("info") or "").strip() or None
        description = f"{venue_name}. {info}" if venue_name and info else (info or venue_name)

        return RawItem(
            kind="event",
            name=name,
            source=self.source_name,
            description=description,
            category=_category(event.get("classifications")),
            lat=lat,
            lon=lon,
            price_from=price_from,
            price_to=price_to,
            image_url=_image(event.get("images")),
            source_url=url,
            starts_at=starts_at,
            is_permanent=False,
        )


def _start(start: dict) -> datetime | None:
    value = start.get("dateTime") or start.get("localDate")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _coords(location) -> tuple[float | None, float | None]:
    if not isinstance(location, dict):
        return None, None
    try:
        lat, lon = float(location["latitude"]), float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, None
    if abs(lat) > 90 or abs(lon) > 180:
        return None, None
    return lat, lon


def _price(price_ranges) -> tuple[float | None, float | None]:
    if not price_ranges:
        return None, None
    first = price_ranges[0]
    return first.get("min"), first.get("max")


def _category(classifications) -> str | None:
    if not classifications:
        return None
    segment = (classifications[0].get("segment") or {}).get("name")
    return SEGMENT_CATEGORY.get(segment)


def _image(images) -> str | None:
    if not images:
        return None
    # Prefer a wide 16:9 image, largest width; fall back to the first one.
    wide = [i for i in images if i.get("ratio") == "16_9" and i.get("url")]
    pool = wide or [i for i in images if i.get("url")]
    if not pool:
        return None
    return max(pool, key=lambda i: i.get("width", 0)).get("url")
