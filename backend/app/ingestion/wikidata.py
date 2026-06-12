"""Wikidata/Wikipedia enrichment for places.

OSM gives us a `wikidata` Q-id per place. From it we pull, for free:
- photo — Wikidata claim P18 → Wikimedia Commons file URL;
- description — intro paragraph of the Wikipedia article (EN preferred,
  PL fallback), with the one-line Wikidata description as a last resort.

Good descriptions matter: they are the main text that gets embedded.
"""

import httpx

USER_AGENT = "warsaw-events-backend/0.1 (ingestion; contact: yros22776@gmail.com)"

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_BATCH = 50  # wbgetentities limit
WIKIPEDIA_BATCH = 20  # extracts (exintro) limit per request

MAX_DESCRIPTION_CHARS = 800


def enrich(pairs: list[tuple]) -> None:
    """Fill description and image_url in-place. pairs = [(RawItem, qid), ...]"""
    entities = _fetch_entities([qid for _, qid in pairs])

    # Group items by the Wikipedia article we will need, one language at a time.
    wanted_titles: dict[str, dict[str, list]] = {"en": {}, "pl": {}}
    for item, qid in pairs:
        entity = entities.get(qid)
        if not entity:
            continue
        if item.image_url is None:
            item.image_url = _image_url(entity)
        if item.description is None:
            item.description = _short_description(entity)  # fallback one-liner

        sitelinks = entity.get("sitelinks", {})
        for lang, sitelink in (("en", "enwiki"), ("pl", "plwiki")):
            title = sitelinks.get(sitelink, {}).get("title")
            if title:
                wanted_titles[lang].setdefault(title, []).append(item)
                break  # EN article wins, PL only as fallback

    for lang, by_title in wanted_titles.items():
        extracts = _fetch_extracts(lang, list(by_title))
        for title, items in by_title.items():
            extract = extracts.get(title)
            if extract:
                for item in items:
                    item.description = _trim(extract)


def _fetch_entities(qids: list[str]) -> dict[str, dict]:
    entities: dict[str, dict] = {}
    unique = sorted(set(qids))
    for i in range(0, len(unique), WIKIDATA_BATCH):
        response = httpx.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(unique[i : i + WIKIDATA_BATCH]),
                "props": "descriptions|claims|sitelinks",
                "languages": "en|pl",
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        entities.update(response.json().get("entities", {}))
    return entities


def _fetch_extracts(lang: str, titles: list[str]) -> dict[str, str]:
    """Intro paragraphs of Wikipedia articles, keyed by the requested title."""
    extracts: dict[str, str] = {}
    for i in range(0, len(titles), WIKIPEDIA_BATCH):
        batch = titles[i : i + WIKIPEDIA_BATCH]
        response = httpx.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": "max",
                "redirects": 1,
                "titles": "|".join(batch),
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        query = response.json().get("query", {})

        # The API may rename titles (normalization, redirects) — map back.
        renames = {
            r["from"]: r["to"] for r in query.get("normalized", []) + query.get("redirects", [])
        }
        by_final_title = {
            page["title"]: page.get("extract") for page in query.get("pages", {}).values()
        }
        for title in batch:
            final = title
            seen = set()
            while final in renames and final not in seen:
                seen.add(final)
                final = renames[final]
            extract = by_final_title.get(final)
            if extract:
                extracts[title] = extract
    return extracts


def _image_url(entity: dict) -> str | None:
    p18 = entity.get("claims", {}).get("P18")
    if not p18:
        return None
    filename = p18[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    if not filename:
        return None
    name = filename.replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=800"


def _short_description(entity: dict) -> str | None:
    descriptions = entity.get("descriptions", {})
    for lang in ("en", "pl"):
        if lang in descriptions:
            return descriptions[lang]["value"]
    return None


def _trim(text: str) -> str:
    """First paragraph, capped at a sentence boundary near the limit."""
    paragraph = text.strip().split("\n\n")[0]
    if len(paragraph) <= MAX_DESCRIPTION_CHARS:
        return paragraph
    cut = paragraph[:MAX_DESCRIPTION_CHARS]
    last_sentence_end = max(cut.rfind(". "), cut.rfind(".\n"))
    return cut[: last_sentence_end + 1] if last_sentence_end > 0 else cut
