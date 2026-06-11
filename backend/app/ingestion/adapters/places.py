from app.ingestion.adapters.base import RawItem, SourceAdapter


class PlacesAdapter(SourceAdapter):
    """Historic places of Warsaw: castles, museums, monuments.

    Source — OpenStreetMap (Overpass API) + Wikidata, free and keyless.
    Opening hours and prices are enriched later from Google Places API.
    """

    source_name = "places"

    def fetch(self) -> list[RawItem]:
        # TODO: Overpass query for the Warsaw bbox:
        #   tourism=attraction|museum|castle, historic=*
        # https://overpass-api.de/api/interpreter
        raise NotImplementedError("first real adapter — next step")
