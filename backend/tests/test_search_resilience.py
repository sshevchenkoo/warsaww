"""The /search LLM-error-handling: a failed intent parse must degrade to a
permissive Intent (raw-text retrieval), never raise. No network — the Anthropic
client is replaced with one that always fails."""

from app.llm.intent import ClaudeIntentExtractor
from app.llm.schemas import Intent


class _BoomMessages:
    def parse(self, **kwargs):
        raise RuntimeError("simulated Anthropic outage")


class _BoomClient:
    def with_options(self, **kwargs):
        return self

    messages = _BoomMessages()


def test_intent_extract_falls_back_on_llm_failure():
    ex = ClaudeIntentExtractor()
    ex._client = _BoomClient()
    intent = ex.extract("концерт в субботу вечером")
    assert isinstance(intent, Intent)
    # Permissive fallback: stay on-topic so retrieval still runs on the raw text,
    # carry the prompt as free_text, and drop the structured filters.
    assert intent.on_topic is True
    assert intent.free_text == "концерт в субботу вечером"
    assert intent.categories == []
    assert intent.date_from is None and intent.budget_max is None


def test_intent_extract_falls_back_when_parsed_output_is_none():
    class _NoneParse:
        def parse(self, **kwargs):
            return type("R", (), {"parsed_output": None})()

    class _NoneClient:
        def with_options(self, **kwargs):
            return self

        messages = _NoneParse()

    ex = ClaudeIntentExtractor()
    ex._client = _NoneClient()
    intent = ex.extract("techno party")
    assert isinstance(intent, Intent)
    assert intent.free_text == "techno party"
