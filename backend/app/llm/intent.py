from datetime import date
from typing import Protocol

from app.config import settings
from app.llm.client import get_anthropic_client
from app.llm.schemas import Intent

SYSTEM_PROMPT = """\
You parse search queries for a service that finds events and places in Warsaw.
The user writes free-form text in Russian, Polish or English.
Extract a structured intent:
- on_topic: true if this is a genuine request to find events or places in the \
city; false for gibberish, random characters, spam, or off-topic questions \
(e.g. "asdfgh", "what is 2+2"). When false, the other fields can be empty.
- categories: matching ones from: concert, party, exhibition, theatre, museum, \
castle, walk, food, family. Empty list = any category.
- date_from / date_to: time window in ISO 8601. Today is {today}. \
"Saturday evening" = nearest Saturday 18:00-23:59. Not mentioned — null.
- budget_max: maximum budget in PLN, if mentioned.
- area: Warsaw district, if mentioned.
- free_text: the semantic gist of the query in one phrase — goes to vector search.
"""


class IntentExtractor(Protocol):
    """Single interface: Claude Haiku now, a fine-tuned local model later."""

    def extract(self, prompt: str) -> Intent: ...


class ClaudeIntentExtractor:
    def __init__(self) -> None:
        self._client = get_anthropic_client()

    def extract(self, prompt: str) -> Intent:
        response = self._client.messages.parse(
            model=settings.intent_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(today=date.today().isoformat()),
            messages=[{"role": "user", "content": prompt}],
            output_format=Intent,
        )
        return response.parsed_output
