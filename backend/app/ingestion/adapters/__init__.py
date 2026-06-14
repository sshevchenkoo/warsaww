from app.ingestion.adapters.base import SourceAdapter
from app.ingestion.adapters.facebook_events import FacebookEventsAdapter
from app.ingestion.adapters.places import PlacesAdapter
from app.ingestion.adapters.ticketmaster import TicketmasterAdapter

# New source = new adapter class + a line here + a CronJob manifest in k8s.
ADAPTERS: dict[str, type[SourceAdapter]] = {
    PlacesAdapter.source_name: PlacesAdapter,
    FacebookEventsAdapter.source_name: FacebookEventsAdapter,
    TicketmasterAdapter.source_name: TicketmasterAdapter,
}
