"""Tourist-worthy places of Warsaw: castles, museums, monuments, parks.

Source — OpenStreetMap via Overpass API, free and keyless.

Notability filter: we only take objects that carry a `wikidata` tag,
i.e. places significant enough to have a Wikidata/Wikipedia entry
(Royal Castle, Lazienki Park, POLIN museum...). Benches, playgrounds
and other map noise never have one, so they are cut off at query level.

Descriptions/photos are enriched later from Wikidata (via the `wikidata`
tag), prices/ratings — from Google Places API.
"""

import httpx

from app.ingestion import wikidata
from app.ingestion.adapters.base import RawItem, SourceAdapter

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Overpass rejects requests without a descriptive User-Agent (406).
USER_AGENT = "warsaw-events-backend/0.1 (ingestion; contact: yros22776@gmail.com)"

# nwr = nodes + ways + relations. area admin_level=6 is the city of Warsaw.
# Both ["wikidata"] and ["name"] are required on every match — that is the
# "worth visiting as a tourist" cut-off.
OVERPASS_QUERY = """
[out:json][timeout:90];
area["name"="Warszawa"]["admin_level"="6"]->.warsaw;
(
  nwr["tourism"~"^(museum|gallery|attraction|viewpoint|zoo|theme_park)$"]["wikidata"]["name"](area.warsaw);
  nwr["historic"~"^(castle|palace|fort|monument|memorial|ruins|city_gate)$"]["wikidata"]["name"](area.warsaw);
  nwr["leisure"="park"]["wikidata"]["name"](area.warsaw);
);
out center tags;
"""

# First matching rule wins, so specific categories go before generic ones
# (Royal Castle is tourism=attraction AND historic=castle — must become 'castle').
CATEGORY_RULES: list[tuple[str, str, str]] = [
    ("tourism", "museum", "museum"),
    ("tourism", "gallery", "exhibition"),
    ("historic", "castle", "castle"),
    ("historic", "palace", "castle"),
    ("historic", "fort", "castle"),
    ("tourism", "zoo", "family"),
    ("tourism", "theme_park", "family"),
    ("historic", "monument", "walk"),
    ("historic", "memorial", "walk"),
    ("historic", "ruins", "walk"),
    ("historic", "city_gate", "walk"),
    ("tourism", "viewpoint", "walk"),
    ("tourism", "attraction", "walk"),
    ("leisure", "park", "walk"),
]


class PlacesAdapter(SourceAdapter):
    source_name = "places"

    def fetch(self) -> list[RawItem]:
        response = httpx.post(
            OVERPASS_URL,
            data={"data": OVERPASS_QUERY},
            headers={"User-Agent": USER_AGENT},
            timeout=120,
        )
        response.raise_for_status()
        elements = response.json()["elements"]

        pairs: list[tuple[RawItem, str]] = []
        for el in elements:
            tags = el.get("tags", {})
            item = self._to_raw_item(el, tags)
            if item is not None:
                pairs.append((item, tags["wikidata"]))

        # Descriptions (Wikipedia intro) + photos (Commons) by Q-id.
        wikidata.enrich(pairs)
        return [item for item, _ in pairs]

    def _to_raw_item(self, el: dict, tags: dict) -> RawItem | None:
        name = tags.get("name:en") or tags.get("name")
        category = self._category(tags)
        if not name or category is None:
            return None

        # Nodes carry lat/lon directly; ways/relations get a computed 'center'.
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        return RawItem(
            kind="place",
            name=name,
            source=self.source_name,
            description=tags.get("description"),
            category=category,
            lat=lat,
            lon=lon,
            source_url=f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
            is_permanent=True,
            opening_hours=({"raw": tags["opening_hours"]} if "opening_hours" in tags else None),
        )

    @staticmethod
    def _category(tags: dict) -> str | None:
        for key, value, category in CATEGORY_RULES:
            if tags.get(key) == value:
                return category
        return None
