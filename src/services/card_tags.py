"""
Tags for catalog cards, and the per-list tag filter built from them.

HelloFresh cards carry no tags, so they are derived from three signals:

* Words. The recipe name says what the dish is ("Ras el Hanout Lamb & Loaded
  Couscous" -> lamb, couscous). The headline is HelloFresh's "with ..." line
  and says what it is served with ("with Potato Wedges & Side Salad" -> sides).
  Name words become main tags; headline words become side tags, so "Salads"
  (the dish is a salad) and "Side salad" stay distinct.
* Overlap. A card that also sits in another classified collection (the same
  card in Chicken Recipes) carries that collection's theme value.
* Stored ingredient keys. When a card has been opened, its ingredient keys
  (from the imported recipe) are stored on the card. These replace text-derived
  ingredient: tags so the two sources cannot disagree; dish:, cuisine:, diet:,
  and side: tags from text and overlap are kept.

Main tags reuse the recipe-theme vocabulary, so "Chicken" here means the same
as the Main ingredient theme's "Chicken". Side tags exist only here.

A list offers a tag as a filter only when at least MIN_TAG_CARDS of its cards
carry it, so options fit the list (no "Bibimbap" chip on African Recipes),
and not every card does, since that tag could not narrow anything.
"""

import re
from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.source_catalog import SourceCollection, SourceCollectionCard
from src.services import ingredient_keys as _ingredient_keys
from src.services.recipe_themes import (
    COLLECTION_THEMES,
    TAG_INDEX,
    VALUE_LABELS,
    normalize_tag,
)

MIN_TAG_CARDS = 3

# Main-tag words beyond the theme vocabulary: common HelloFresh mains that are
# not theme values. key -> (label, spellings).
EXTRA_MAIN: dict[str, tuple[str, list[str]]] = {
    "ingredient:steak": ("Steak", ["steak", "sirloin", "ribeye", "flank steak"]),
    "ingredient:salmon": ("Salmon", ["salmon"]),
    "ingredient:shrimp": ("Shrimp", ["shrimp", "prawn"]),
    "ingredient:sausage": ("Sausage", ["sausage", "chorizo", "bratwurst"]),
    "ingredient:bacon": ("Bacon", ["bacon", "pancetta", "prosciutto"]),
    "ingredient:white-fish": ("White fish", ["cod", "tilapia", "barramundi", "catfish", "haddock"]),
    "ingredient:lentils": ("Lentils", ["lentil"]),
    "ingredient:chickpeas": ("Chickpeas", ["chickpea"]),
    "ingredient:rice": ("Rice", ["rice", "fried rice", "risotto rice"]),
    "ingredient:couscous": ("Couscous", ["couscous"]),
    "ingredient:sweet-potato": ("Sweet potato", ["sweet potato"]),
    "ingredient:zucchini": ("Zucchini", ["zucchini"]),
    "ingredient:peanut": ("Peanut", ["peanut"]),
    "ingredient:cheese": ("Cheese", ["cheese", "cheesy", "mozzarella", "cheddar", "parmesan", "feta", "brie"]),
    "cuisine:tex-mex": ("Tex-Mex", ["tex mex"]),
    "dish:stews": ("Stews", ["stew", "tagine"]),
    "dish:pizza": ("Pizza", ["pizza"]),
    "dish:gnocchi": ("Gnocchi", ["gnocchi"]),
    "dish:wraps": ("Wraps", ["wrap", "pita", "gyro"]),
    "dish:cutlets": ("Cutlets", ["cutlet", "schnitzel"]),
    "dish:melts": ("Melts", ["melt"]),
}

# Side-tag words, matched in the headline only. key -> (label, spellings).
SIDES: dict[str, tuple[str, list[str]]] = {
    "side:salad": ("Side salad", ["salad", "side salad", "slaw", "coleslaw"]),
    "side:potatoes": ("with potatoes", ["potato", "potatoes", "mash", "mashed potatoes", "wedges", "fries", "tots"]),
    "side:sweet-potato": ("with sweet potato", ["sweet potato", "sweet potato wedges", "sweet potato fries"]),
    "side:rice": ("with rice", ["rice", "jasmine rice", "basmati rice", "fried rice"]),
    "side:couscous": ("with couscous", ["couscous"]),
    "side:quinoa": ("with quinoa", ["quinoa"]),
    "side:green-beans": ("with green beans", ["green beans", "green bean"]),
    "side:broccoli": ("with broccoli", ["broccoli", "broccolini"]),
    "side:carrots": ("with carrots", ["carrot"]),
    "side:corn": ("with corn", ["corn"]),
    "side:bread": ("with bread", ["bread", "naan", "pita", "flatbread", "toast", "biscuits"]),
}


def _label_for_theme_key(key: str) -> str:
    theme, value = key.split(":", 1)
    return VALUE_LABELS[theme][value]


def _build_main_index() -> dict[str, str]:
    """spelling -> key, for name matching."""
    index: dict[str, str] = {}
    for spelling, (theme, value) in TAG_INDEX.items():
        if theme == "meal_type":
            continue  # "main", "side", "dinner" in a name say little about the dish
        index[spelling] = f"{theme}:{value}"
    # Salad in the name means the dish is a salad.
    index["salad"] = "dish:salads"
    # "Sweet Chili Chicken" is not a chili: only count chili as the dish itself.
    index.pop("chili", None)
    for phrase in ("chili con carne", "beef chili", "turkey chili", "bean chili", "veggie chili", "white chili"):
        index[phrase] = "dish:chili"
    # Green beans are a vegetable, not legumes.
    index["green bean"] = "side:green-beans"
    for key, (_, spellings) in EXTRA_MAIN.items():
        for s in spellings:
            index.setdefault(normalize_tag(s), key)
    return index


def _build_side_index() -> dict[str, str]:
    return {normalize_tag(s): key for key, (_, spellings) in SIDES.items() for s in spellings}


MAIN_INDEX = _build_main_index()
SIDE_INDEX = _build_side_index()

LABELS: dict[str, str] = {
    **{key: label for key, (label, _) in EXTRA_MAIN.items()},
    **{key: label for key, (label, _) in SIDES.items()},
}


def tag_label(key: str) -> str:
    if key in LABELS:
        return LABELS[key]
    if key.startswith("ingredient:"):
        value = key.split(":", 1)[1]
        if value not in VALUE_LABELS.get("ingredient", {}):
            return _ingredient_keys.label_for(value)
    return _label_for_theme_key(key)


def _match(text: Optional[str], index: dict[str, str]) -> set[str]:
    """
    Keys whose spellings appear in text as whole words (plural s/es allowed).

    Longest spellings first, and a matched span is blanked out, so "green
    beans" does not also count as "beans" nor "sweet potato" as "potato".
    """
    if not text:
        return set()
    padded = " " + normalize_tag(re.sub(r"[^\w&\- ]", " ", text)) + " "
    found: set[str] = set()
    for spelling in sorted(index, key=len, reverse=True):
        pattern = re.compile(rf" {re.escape(spelling)}(?:s|es)? ")
        if pattern.search(padded):
            found.add(index[spelling])
            padded = pattern.sub("  ", padded)
    return found


def tags_from_text(name: Optional[str], headline: Optional[str]) -> set[str]:
    """Main tags from the name, side tags from the headline."""
    return _match(name, MAIN_INDEX) | _match(headline, SIDE_INDEX)


def overlap_tags(db: Session, card_ids: Iterable[UUID]) -> dict[UUID, set[str]]:
    """card id -> theme keys of every classified collection the card sits in."""
    ids = list(card_ids)
    if not ids:
        return {}
    rows = (
        db.query(SourceCollectionCard.card_id, SourceCollection.source_type, SourceCollection.slug)
        .join(SourceCollection, SourceCollection.id == SourceCollectionCard.collection_id)
        .filter(SourceCollectionCard.card_id.in_(ids))
        .all()
    )
    result: dict[UUID, set[str]] = {}
    for card_id, source_type, slug in rows:
        classified = COLLECTION_THEMES.get(source_type, {}).get(slug)
        if classified:
            result.setdefault(card_id, set()).add(f"{classified[0]}:{classified[1]}")
    return result


@dataclass
class TagOption:
    key: str
    label: str
    kind: str  # "main" or "side"
    count: int


def tag_cards(
    db: Session,
    cards: list,
    collection_source: str,
    collection_slug: str,
) -> tuple[dict[UUID, list[str]], list[TagOption]]:
    """
    Tag each card and pick the list's filter options.

    Returns (card id -> sorted tag keys, options). The list's own theme value
    is dropped from both: every card in Chicken Recipes is chicken.
    """
    own = COLLECTION_THEMES.get(collection_source, {}).get(collection_slug)
    own_key = f"{own[0]}:{own[1]}" if own else None

    overlap = overlap_tags(db, (c.id for c in cards))
    card_tags: dict[UUID, list[str]] = {}
    counts: dict[str, int] = {}
    for card in cards:
        text_tags = tags_from_text(card.name, card.headline)
        overlap_set = overlap.get(card.id, set())
        stored_keys = getattr(card, "ingredient_keys", None)
        if stored_keys is not None:
            # Stored keys are authoritative for ingredient: tags; drop text-derived
            # and overlap-derived ingredient: tags so the two sources cannot disagree.
            text_tags = {t for t in text_tags if not t.startswith("ingredient:")}
            overlap_set = {t for t in overlap_set if not t.startswith("ingredient:")}
            tags = text_tags | overlap_set | {f"ingredient:{k}" for k in stored_keys}
        else:
            tags = text_tags | overlap_set
        tags.discard(own_key)
        card_tags[card.id] = sorted(tags)
        for key in tags:
            counts[key] = counts.get(key, 0) + 1

    options = [
        TagOption(key=key, label=tag_label(key), kind="side" if key.startswith("side:") else "main", count=n)
        for key, n in counts.items()
        # A tag on every card cannot narrow the list ("Bowls" on Asian Food Recipes).
        if MIN_TAG_CARDS <= n < len(cards)
    ]
    # Mains before sides, fullest first.
    options.sort(key=lambda o: (o.kind != "main", -o.count, o.label))
    return card_tags, options
