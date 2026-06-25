"""Cross-source deduplication for ingested cards.

The same real-world event arrives from several sources under slightly
different names ("The Weeknd - Warsaw" vs "The Weeknd | PGE Narodowy").
Left alone, the results look spammy. Strategy:

1. Block candidates that *could* match (same event day, or near coordinates
   for places) so we never compare everything against everything.
2. Fuzzy-compare normalized names with rapidfuzz. A high score is an
   automatic match; a middle band is ambiguous.
3. Ambiguous pairs are adjudicated by Claude Haiku ("same event? yes/no") —
   only if an adjudicator is supplied.

A duplicate is not inserted as its own card: its (source, source_url) ref
is recorded on the canonical card's `sources` list instead. Two cards from
the *same* source_url are left to the (source, source_url) upsert, not here.
"""

import logging
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable

import anthropic
from rapidfuzz import fuzz

from app.config import settings
from app.llm.client import get_anthropic_client

log = logging.getLogger(__name__)

AUTO_MATCH = 90  # >= this: same entity, no LLM needed
AMBIGUOUS = 75  # [AMBIGUOUS, AUTO_MATCH): ask the adjudicator
# < AMBIGUOUS: treated as different

_NOISE = {"warsaw", "warszawa", "poland", "polska", "pl", "official", "save", "date"}

Adjudicator = Callable[[object, object], bool]


# NFKD does not decompose these stroke letters into base + diacritic.
_STROKE = str.maketrans({"ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d"})


def normalize_name(name: str) -> str:
    """Lowercase, strip diacritics/emoji/punctuation, drop noise + year tokens."""
    text = unicodedata.normalize("NFKD", name.translate(_STROKE))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    tokens = [t for t in text.split() if t not in _NOISE and not t.isdigit()]
    return " ".join(tokens)


def block_key(item) -> tuple:
    """Items that share a block are the only ones compared against each other."""
    if getattr(item, "starts_at", None):
        return ("day", item.starts_at.date().isoformat())
    if getattr(item, "lat", None) is not None and getattr(item, "lon", None) is not None:
        return ("geo", round(item.lat, 3), round(item.lon, 3))  # ~110 m cell
    return ("name", normalize_name(item.name)[:4])


def _ref(item) -> dict:
    return {"source": item.source, "source_url": item.source_url}


def _best_match(
    norm: str,
    item,
    candidates: list[tuple[str, object]],
    adjudicate: Adjudicator | None,
    skip: Callable[[object], bool] | None = None,
) -> object | None:
    if not norm:  # name was all noise — never match it to anything
        return None
    best, best_score = None, 0.0
    for cand_norm, cand in candidates:
        if skip is not None and skip(cand):
            continue
        # token_set_ratio scores subset names highly ("The Weeknd" inside
        # "The Weeknd | PGE Narodowy") — common when a source appends a venue.
        score = fuzz.token_set_ratio(norm, cand_norm)
        if score > best_score:
            best, best_score = cand, score
    if best is None:
        return None
    if best_score >= AUTO_MATCH:
        return best
    if best_score >= AMBIGUOUS and adjudicate is not None and adjudicate(item, best):
        return best
    return None


def make_haiku_adjudicator() -> Adjudicator | None:
    """Build a 'same event?' decider backed by Claude Haiku, or None if no key.

    Called only for the ambiguous score band, i.e. a handful of pairs per
    run — a sync call per pair is fine. At scale, move to the Batches API."""
    if not settings.anthropic_api_key:
        return None
    client = get_anthropic_client()

    def adjudicate(a, b) -> bool:
        question = (
            "Are these two listings the same real-world event? "
            "Answer only 'yes' or 'no'.\n"
            f"A: {a.name} | {getattr(a, 'starts_at', None)}\n"
            f"B: {b.name} | {getattr(b, 'starts_at', None)}"
        )
        try:
            resp = client.messages.create(
                model=settings.intent_model,
                max_tokens=5,
                messages=[{"role": "user", "content": question}],
            )
        except anthropic.AnthropicError:
            # A transient LLM failure must not abort the whole ingest run; the
            # conservative fallback is "not a match", which keeps both cards
            # (a possible duplicate) rather than dropping the batch entirely.
            log.warning("adjudicator call failed for %r / %r — keeping separate",
                        a.name, b.name, exc_info=True)
            return False
        text = "".join(blk.text for blk in resp.content if blk.type == "text")
        return text.strip().lower().startswith("y")

    return adjudicate


def deduplicate(
    items: list, existing: list, adjudicate: Adjudicator | None = None
) -> tuple[list, list[tuple]]:
    """Split incoming `items` into cards to write and merges into existing cards.

    Returns (canonical, merges):
    - canonical: items to embed + upsert, each with `sources` populated;
    - merges: list of (existing_id, source_ref) to append onto existing cards.
    """
    existing_blocks: dict[tuple, list[tuple[str, object]]] = defaultdict(list)
    for e in existing:
        existing_blocks[block_key(e)].append((normalize_name(e.name), e))

    canonical: list = []
    merges: list[tuple] = []
    batch_blocks: dict[tuple, list[tuple[str, object]]] = defaultdict(list)

    for item in items:
        norm = normalize_name(item.name)
        bkey = block_key(item)

        # 1) same entity already in the DB from a different source_url → merge.
        match = _best_match(
            norm,
            item,
            existing_blocks.get(bkey, []),
            adjudicate,
            skip=lambda e: e.source_url == item.source_url,
        )
        if match is not None:
            merges.append((match.id, _ref(item)))
            continue

        # 2) same entity seen earlier in this very batch → fold into it.
        twin = _best_match(norm, item, batch_blocks.get(bkey, []), adjudicate)
        if twin is not None:
            twin.sources.append(_ref(item))
            continue

        # 3) genuinely new card.
        item.sources = [_ref(item)]
        canonical.append(item)
        batch_blocks[bkey].append((norm, item))

    return canonical, merges
