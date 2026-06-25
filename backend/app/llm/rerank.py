"""Re-rank the top hybrid-search candidates with Claude Opus.

Vector search returns up to 30 candidates ordered by raw similarity.
Opus reads the actual query and the cards, keeps the ones that genuinely
fit, reorders them, and writes a one-line pitch ("blurb") for each in the
user's own language. Output is streamed card-by-card (one JSON object per
line) so the API can push results to the frontend as they are produced.
"""

import json
from collections.abc import Iterator

from app.catalog.models import Item
from app.config import settings
from app.llm.client import get_anthropic_client

SYSTEM_PROMPT = """\
You re-rank candidate cards for a service that finds events and places in \
Warsaw. You receive the user's free-form query and a numbered list of \
candidates (events and permanent places) already pre-filtered by vector search.

Keep only the candidates that genuinely match the query and order them from \
best to worst fit. Drop anything irrelevant. Return at most {limit}.

For each pick write one short sentence (a "blurb") that pitches the card and \
says why it fits — written in the SAME LANGUAGE as the user's query (the query \
is normally Russian, Polish or English; match it exactly, do not switch to a \
related language).

Output strictly one JSON object per line and nothing else — no markdown, no \
prose, no preamble:
{{"n": <candidate number>, "blurb": "<one sentence>"}}
"""

MAX_DESCRIPTION_CHARS = 220


def _candidate_block(items: list[Item]) -> str:
    lines: list[str] = []
    for n, item in enumerate(items, 1):
        head = f"[{n}] {item.name} — {item.category or 'n/a'}"
        if item.starts_at:
            head += f" — {item.starts_at:%Y-%m-%d %H:%M}"
        elif item.is_permanent:
            head += " — permanent"
        if item.price_from is not None:
            head += f" — from {item.price_from} PLN"
        lines.append(head)
        if item.description:
            lines.append(f"    {item.description[:MAX_DESCRIPTION_CHARS]}")
    return "\n".join(lines)


def rerank_stream(prompt: str, items: list[Item], limit: int = 10) -> Iterator[tuple[Item, str]]:
    """Yield (item, blurb) pairs ordered best-to-worst as Opus produces them."""
    if not items:
        return

    client = get_anthropic_client()
    user_content = f"User query:\n{prompt}\n\nCandidates:\n{_candidate_block(items)}"

    buffer = ""
    seen: set[int] = set()
    with client.messages.stream(
        model=settings.rerank_model,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT.format(limit=limit),
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        for text in stream.text_stream:
            buffer += text
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                pair = _parse_line(line, items, seen)
                if pair is not None:
                    yield pair

    pair = _parse_line(buffer, items, seen)  # trailing line without a newline
    if pair is not None:
        yield pair


def _parse_line(line: str, items: list[Item], seen: set[int]) -> tuple[Item, str] | None:
    line = line.strip().rstrip(",")
    if not line.startswith("{"):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    n = obj.get("n")
    if not isinstance(n, int) or not (1 <= n <= len(items)) or n in seen:
        return None
    seen.add(n)
    return items[n - 1], (obj.get("blurb") or "")
