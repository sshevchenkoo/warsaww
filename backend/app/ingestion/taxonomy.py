"""Category fallback: keyword heuristic over name + description.

Sources often leave the category empty (Facebook fills it for ~20% of
events). Vector search works without a category, but SQL filters and
card badges want one. First matching rule wins, so specific categories
go before generic ones. Keywords cover EN + PL.
"""

CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "party",
        [
            "party",
            "impreza",
            "rave",
            "techno",
            "house music",
            "clubbing",
            "club night",
            "dj set",
            "disco",
            "afterparty",
        ],
    ),
    (
        "concert",
        [
            "concert",
            "koncert",
            "live music",
            "music festival",
            "gig",
            "symphon",
            "orchestr",
            "filharmoni",
            "unplugged",
            "tour 20",
        ],
    ),
    (
        "exhibition",
        [
            "exhibition",
            "wystawa",
            "vernissage",
            "wernisaż",
            "gallery",
            "galeria",
            "biennale",
        ],
    ),
    (
        "theatre",
        [
            "theatre",
            "theater",
            "teatr",
            "spektakl",
            "stand-up",
            "standup",
            "comedy",
            "kabaret",
            "improv",
        ],
    ),
    (
        "food",
        [
            "food",
            "restaurant",
            "restauracj",
            "kulinar",
            "degustac",
            "tasting",
            "brunch",
            "wine",
            "craft beer",
            "targ śniadaniowy",
        ],
    ),
    (
        "family",
        [
            "for kids",
            "dla dzieci",
            "family",
            "rodzinn",
            "playground",
            "warsztaty dla",
        ],
    ),
    (
        "walk",
        [
            "city tour",
            "spacer",
            "wycieczka",
            "sightseeing",
            "bike tour",
            "biketour",
            "guided tour",
        ],
    ),
]


def guess_category(name: str, description: str | None) -> str | None:
    text = f"{name} {description or ''}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return None
