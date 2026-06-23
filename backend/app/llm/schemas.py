from pydantic import BaseModel


class Intent(BaseModel):
    """Structured intent extracted from a free-form user prompt."""

    on_topic: bool = True  # false = not a real events/places search (gibberish, off-topic)
    categories: list[str] = []
    date_from: str | None = None  # ISO 8601
    date_to: str | None = None
    budget_max: float | None = None  # PLN
    area: str | None = None  # Warsaw district
    free_text: str = ""  # semantic gist — used for vector search
