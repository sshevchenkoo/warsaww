from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawItem:
    """Raw card from a source — before normalization."""

    kind: str  # 'event' | 'place'
    name: str
    source: str
    description: str | None = None
    category: str | None = None
    lat: float | None = None
    lon: float | None = None
    price_from: float | None = None
    price_to: float | None = None
    image_url: str | None = None
    source_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_permanent: bool = False
    opening_hours: dict | None = None
    embedding: list[float] | None = None  # filled by the pipeline, not adapters
    sources: list | None = None  # all (source, source_url) refs after dedup


class SourceAdapter(ABC):
    """One adapter per source. Only fetch() differs between sources —
    the rest of the pipeline (normalize → dedup → embed → upsert) is shared."""

    source_name: str

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Pull raw cards from the source (API or scraping)."""
