from app.ingestion.adapters.base import SourceAdapter
from app.ingestion.adapters.facebook_events import FacebookEventsAdapter
from app.ingestion.adapters.fixtures import FixturesAdapter
from app.ingestion.adapters.places import PlacesAdapter
from app.ingestion.adapters.ticketmaster import TicketmasterAdapter

# New source = new adapter class + a line here + a CronJob manifest in k8s.
ADAPTERS: dict[str, type[SourceAdapter]] = {
    PlacesAdapter.source_name: PlacesAdapter,
    FacebookEventsAdapter.source_name: FacebookEventsAdapter,
    TicketmasterAdapter.source_name: TicketmasterAdapter,
    # Local demo data (no API keys) — clearly marked [TEST] cards. See fixtures.py.
    FixturesAdapter.source_name: FixturesAdapter,
}
