from app.ingestion.adapters.base import SourceAdapter
from app.ingestion.adapters.places import PlacesAdapter

# New source = new adapter class + a line here + a CronJob manifest in k8s.
ADAPTERS: dict[str, type[SourceAdapter]] = {
    PlacesAdapter.source_name: PlacesAdapter,
}
