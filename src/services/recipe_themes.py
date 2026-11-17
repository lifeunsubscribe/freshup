"""
Recipe themes: the attributes the Recipes page groups and filters lists by.

A theme (cuisine, main ingredient, dish type, diet, meal type, source) has
values (Italian, Chicken, Tacos, ...). Each value gathers whole lists, never
slices of them:

* HelloFresh collections, classified by slug in ``HELLOFRESH_COLLECTION_THEMES``.
* A "your recipes" list: library recipes carrying a matching tag (or, for the
  source theme, a matching source_type), queried through ``GET /recipes``.

Lists stay per-source. An Italian HelloFresh collection and your Italian
recipes are two lists under the same value, each naming its own source, so
more sources can join later without merging anything.

The vocabulary is hand-maintained. Collections not listed here (e.g. "Hall
of Fame") simply belong to no theme; tags outside the vocabulary are ignored.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard

HELLOFRESH_SOURCE = "hellofresh_web"
HOMECHEF_SOURCE = "homechef_web"

# Display order of the theme bar.
THEMES: list[tuple[str, str]] = [
    ("cuisine", "Cuisine"),
    ("ingredient", "Main ingredient"),
    ("dish", "Dish type"),
    ("diet", "Diet"),
    ("meal_type", "Meal type"),
    ("source", "Source"),
]

# value key -> label, per tag-backed theme. Keys double as tag aliases
# (hyphens read as spaces), so "latin-american" matches the tag "latin american".
VALUE_LABELS: dict[str, dict[str, str]] = {
    "cuisine": {
        "african": "African", "american": "American", "asian": "Asian", "british": "British",
        "cajun": "Cajun", "caribbean": "Caribbean", "chinese": "Chinese", "cuban": "Cuban",
        "french": "French", "german": "German", "greek": "Greek", "hawaiian": "Hawaiian",
        "indian": "Indian", "italian": "Italian", "japanese": "Japanese", "korean": "Korean",
        "latin-american": "Latin American", "mediterranean": "Mediterranean",
        "mexican": "Mexican", "middle-eastern": "Middle Eastern", "moroccan": "Moroccan",
        "peruvian": "Peruvian", "spanish": "Spanish", "thai": "Thai", "vietnamese": "Vietnamese",
    },
    "ingredient": {
        "beef": "Beef", "chicken": "Chicken", "duck": "Duck", "pork": "Pork", "seafood": "Seafood",
        "turkey": "Turkey", "tofu": "Tofu", "beans-legumes": "Beans & legumes", "grains": "Grains",
        "mushrooms": "Mushrooms", "potatoes": "Potatoes", "lamb": "Lamb", "salmon": "Salmon",
        "shrimp": "Shrimp",
    },
    "dish": {
        "bibimbap": "Bibimbap", "bowls": "Bowls", "burgers": "Burgers", "burritos": "Burritos",
        "casseroles": "Casseroles", "chili": "Chili", "curry": "Curry", "enchiladas": "Enchiladas",
        "fajitas": "Fajitas", "falafel": "Falafel", "flatbreads": "Flatbreads",
        "meatballs": "Meatballs", "meatloaf": "Meatloaf", "noodles": "Noodles",
        "one-pot": "One-pot meals", "panini": "Panini", "pasta": "Pasta",
        "quesadillas": "Quesadillas", "risotto": "Risotto", "salads": "Salads",
        "sandwiches": "Sandwiches", "skewers": "Skewers", "skillet": "Skillet meals",
        "soups": "Soups", "stir-fries": "Stir-fries", "tacos": "Tacos", "tostadas": "Tostadas",
    },
    "diet": {
        "vegetarian": "Vegetarian", "plant-based": "Plant-based", "pescatarian": "Pescatarian",
        "calorie-smart": "Calorie smart", "carb-smart": "Carb smart",
        "kid-friendly": "Kid-friendly", "gluten-free": "Gluten-free", "dairy-free": "Dairy-free",
    },
    "meal_type": {
        "breakfast-brunch": "Breakfast & brunch", "lunch": "Lunch", "main-course": "Main course",
        "sides": "Sides", "appetizers": "Appetizers", "desserts": "Desserts", "snacks": "Snacks",
    },
}

# Extra tag spellings beyond the value key itself (normalized: lowercase,
# hyphens/underscores as spaces, "&" as "and").
TAG_ALIASES: dict[tuple[str, str], list[str]] = {
    ("ingredient", "beans-legumes"): ["beans", "legumes", "beans and legumes"],
    ("ingredient", "grains"): ["grain"],
    ("ingredient", "mushrooms"): ["mushroom"],
    ("ingredient", "potatoes"): ["potato"],
    ("dish", "bowls"): ["bowl"], ("dish", "burgers"): ["burger"], ("dish", "burritos"): ["burrito"],
    ("dish", "casseroles"): ["casserole"], ("dish", "enchiladas"): ["enchilada"],
    ("dish", "fajitas"): ["fajita"], ("dish", "flatbreads"): ["flatbread"],
    ("dish", "meatballs"): ["meatball"], ("dish", "noodles"): ["noodle"],
    ("dish", "one-pot"): ["one pot", "one pan", "one pot meals"],
    ("dish", "quesadillas"): ["quesadilla"], ("dish", "salads"): ["salad"],
    ("dish", "sandwiches"): ["sandwich"], ("dish", "skewers"): ["skewer"],
    ("dish", "soups"): ["soup"], ("dish", "stir-fries"): ["stir fry"],
    ("dish", "tacos"): ["taco"], ("dish", "tostadas"): ["tostada"],
    ("diet", "plant-based"): ["vegan", "plant based"],
    ("diet", "calorie-smart"): ["low calorie"], ("diet", "carb-smart"): ["low carb"],
    ("meal_type", "breakfast-brunch"): ["breakfast", "brunch", "breakfast and brunch"],
    ("meal_type", "main-course"): ["main", "main dish", "dinner", "entree"],
    ("meal_type", "sides"): ["side", "side dish"],
    ("meal_type", "appetizers"): ["appetizer", "starter", "starters"],
    ("meal_type", "desserts"): ["dessert"], ("meal_type", "snacks"): ["snack"],
}

# Per-source top-level collection theme map: source_type -> slug -> (theme, value).
# Add a new source by inserting its slug map under its source_type key.
COLLECTION_THEMES: dict[str, dict[str, tuple[str, str]]] = {
    HELLOFRESH_SOURCE: {
    **{f"{v}-recipes": ("cuisine", v) for v in (
        "african", "american", "asian", "cajun", "chinese", "cuban", "french", "hawaiian",
        "indian", "italian", "japanese", "korean", "latin-american", "mediterranean",
        "mexican", "middle-eastern", "spanish", "thai", "vietnamese",
    )},
    "beef-recipes": ("ingredient", "beef"), "chicken-recipes": ("ingredient", "chicken"),
    "duck-recipes": ("ingredient", "duck"), "pork-recipes": ("ingredient", "pork"),
    "seafood-recipes": ("ingredient", "seafood"), "turkey-recipes": ("ingredient", "turkey"),
    "tofu-recipes": ("ingredient", "tofu"),
    "bean-and-legume-recipes": ("ingredient", "beans-legumes"),
    "beans-legumes-recipes": ("ingredient", "beans-legumes"),
    "grain-recipes": ("ingredient", "grains"), "mushroom-recipes": ("ingredient", "mushrooms"),
    "potato-recipes": ("ingredient", "potatoes"),
    "bibimbap-recipes": ("dish", "bibimbap"), "bowl-recipes": ("dish", "bowls"),
    "burger-recipes": ("dish", "burgers"), "burrito-recipes": ("dish", "burritos"),
    "casserole-recipes": ("dish", "casseroles"), "chili-recipes": ("dish", "chili"),
    "curry-recipes": ("dish", "curry"), "enchilada-recipes": ("dish", "enchiladas"),
    "fajita-recipes": ("dish", "fajitas"), "falafel-recipes": ("dish", "falafel"),
    "flatbread-recipes": ("dish", "flatbreads"), "meatball-recipes": ("dish", "meatballs"),
    "meatloaf-recipes": ("dish", "meatloaf"), "noodle-recipes": ("dish", "noodles"),
    "one-pot-pan-meals": ("dish", "one-pot"), "panini-recipes": ("dish", "panini"),
    "pasta-recipes": ("dish", "pasta"), "quesadilla-recipes": ("dish", "quesadillas"),
    "risotto-recipes": ("dish", "risotto"), "sandwich-recipes": ("dish", "sandwiches"),
    "skewer-recipes": ("dish", "skewers"), "skillet-recipes": ("dish", "skillet"),
    "soup-recipes": ("dish", "soups"), "stir-fry-recipes": ("dish", "stir-fries"),
    "taco-recipes": ("dish", "tacos"), "tostada-recipes": ("dish", "tostadas"),
    "vegetarian-recipes": ("diet", "vegetarian"), "plant-based-recipes": ("diet", "plant-based"),
    "pescatarian-recipes": ("diet", "pescatarian"),
    "calorie-smart-recipes": ("diet", "calorie-smart"),
    "carb-smart-recipes": ("diet", "carb-smart"),
    "kid-friendly-recipes": ("diet", "kid-friendly"),
    "breakfast-and-brunch": ("meal_type", "breakfast-brunch"),
    },
    HOMECHEF_SOURCE: {
        "chicken": ("ingredient", "chicken"),
        "beef": ("ingredient", "beef"),
        "steak": ("ingredient", "beef"),
        "pork": ("ingredient", "pork"),
        "lamb": ("ingredient", "lamb"),
        "salmon": ("ingredient", "salmon"),
        "shrimp": ("ingredient", "shrimp"),
        "seafood": ("ingredient", "seafood"),
        "fish": ("ingredient", "seafood"),
        "cod": ("ingredient", "seafood"),
        "vegetarian": ("diet", "vegetarian"),
        "calorie-conscious": ("diet", "calorie-smart"),
        "carb-conscious": ("diet", "carb-smart"),
        "breakfast": ("meal_type", "breakfast-brunch"),
        "dessert": ("meal_type", "desserts"),
        "pasta": ("dish", "pasta"),
        "salad": ("dish", "salads"),
    },
}

# Backward-compatible alias; existing code and tests that import this name continue to work.
HELLOFRESH_COLLECTION_THEMES: dict[str, tuple[str, str]] = COLLECTION_THEMES[HELLOFRESH_SOURCE]

# Source theme: recipe source_type -> (value, label). Several source types can
# share a value (HelloFresh cards and web imports are both "HelloFresh").
SOURCE_VALUES: dict[str, tuple[str, str]] = {
    "hellofresh_web": ("hellofresh", "HelloFresh"),
    "hellofresh_card": ("hellofresh", "HelloFresh"),
    "homechef_web": ("homechef", "Home Chef"),
    "kitchen_sanctuary": ("kitchen_sanctuary", "Kitchen Sanctuary"),
    "url_import": ("web", "From the web"),
    "photo_upload": ("photos", "From photos"),
    "manual": ("manual", "Added by hand"),
    "ad_hoc": ("pantry", "Made from the pantry"),
}
# Catalog source -> source theme value, so its collections join that value.
CATALOG_SOURCE_VALUES: dict[str, str] = {
    HELLOFRESH_SOURCE: "hellofresh",
    HOMECHEF_SOURCE: "homechef",
}


def normalize_tag(tag: str) -> str:
    """Lowercase, hyphens/underscores as spaces, "&" as "and", single-spaced."""
    cleaned = tag.lower().replace("&", " and ").replace("-", " ").replace("_", " ")
    return " ".join(cleaned.split())


def _build_tag_index() -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for theme, values in VALUE_LABELS.items():
        for value, label in values.items():
            for spelling in [value, label, *TAG_ALIASES.get((theme, value), [])]:
                index.setdefault(normalize_tag(spelling), (theme, value))
    return index


TAG_INDEX = _build_tag_index()


@dataclass
class ThemeCollectionData:
    source_type: str
    slug: str
    name: str
    card_count: int
    last_fetched_at: Optional[datetime]
    # "theme:value" keys this collection's cards also appear under, via other
    # collections sharing the same card. Lets filters combine on whole lists:
    # Italian Recipes passes a Vegetarian filter if one of its cards is also
    # in Vegetarian Recipes.
    contains: list[str] = field(default_factory=list)


@dataclass
class ThemeValueData:
    value: str
    label: str
    # How to query "your recipes" for this value; at most one is set.
    library_tag: Optional[str] = None
    library_source_type: Optional[str] = None
    library_count: int = 0
    # Every tag / source_type that counts as this value, for "list contains it" checks.
    match_tags: list[str] = field(default_factory=list)
    match_source_types: list[str] = field(default_factory=list)
    collections: list[ThemeCollectionData] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.library_count + sum(c.card_count for c in self.collections)


@dataclass
class ThemeData:
    key: str
    label: str
    values: list[ThemeValueData]


def _collection_contains(db: Session) -> dict:
    """
    Map collection id -> {"theme:value"} for values its cards also belong to.

    One self-join over the card/collection join table: two collections sharing
    a card means each contains the other's value. Sub-collections count too
    when classified (they are not, today; only top-level slugs are).
    """
    left = aliased(SourceCollectionCard)
    right = aliased(SourceCollectionCard)
    pairs = (
        db.query(left.collection_id, SourceCollection.source_type, SourceCollection.slug)
        .join(right, right.card_id == left.card_id)
        .join(SourceCollection, SourceCollection.id == right.collection_id)
        .filter(left.collection_id != right.collection_id)
        .distinct()
        .all()
    )
    result: dict = {}
    for collection_id, source_type, other_slug in pairs:
        source_map = COLLECTION_THEMES.get(source_type, {})
        classified = source_map.get(other_slug)
        if classified:
            result.setdefault(collection_id, set()).add(f"{classified[0]}:{classified[1]}")
    return result


def build_themes(db: Session) -> list[ThemeData]:
    """
    Classify every list into theme values.

    Values with nothing behind them are left out. A collection fetched and
    found empty counts as nothing; a never-fetched one is kept so its row can
    lazily fetch on the page.

    Library tags are tallied in Python over all recipes' tags. The recipe table
    is small (household scale); revisit with a tag table if it grows large.
    """
    values: dict[tuple[str, str], ThemeValueData] = {}

    def value_for(theme: str, value: str, label: str) -> ThemeValueData:
        key = (theme, value)
        if key not in values:
            values[key] = ThemeValueData(value=value, label=label)
        return values[key]

    # Library tags: count recipes per raw tag, grouped by the value it maps to.
    raw_tag_counts: dict[tuple[str, str], Counter] = {}
    source_counts: dict[str, Counter] = {}
    for tags, source_type in db.query(Recipe.tags, Recipe.source_type).all():
        seen_values: set[tuple[str, str]] = set()
        for raw in tags or []:
            if not isinstance(raw, str):
                continue
            mapped = TAG_INDEX.get(normalize_tag(raw))
            if mapped and mapped not in seen_values:
                seen_values.add(mapped)
                raw_tag_counts.setdefault(mapped, Counter())[raw.lower()] += 1
        if source_type in SOURCE_VALUES:
            src_value, _ = SOURCE_VALUES[source_type]
            source_counts.setdefault(src_value, Counter())[source_type] += 1

    for (theme, value), counter in raw_tag_counts.items():
        entry = value_for(theme, value, VALUE_LABELS[theme][value])
        # The list endpoint matches one exact tag, so the row queries the most
        # common spelling and the count is that spelling's count.
        entry.library_tag, entry.library_count = counter.most_common(1)[0]
        entry.match_tags = sorted(counter)

    for src_value, counter in source_counts.items():
        label = next(lbl for st, (v, lbl) in SOURCE_VALUES.items() if v == src_value)
        entry = value_for("source", src_value, label)
        entry.library_source_type, entry.library_count = counter.most_common(1)[0]
        entry.match_source_types = sorted(counter)

    # Collections: top-level only, with card counts.
    rows = (
        db.query(SourceCollection, func.count(SourceCollectionCard.card_id))
        .outerjoin(SourceCollectionCard, SourceCollectionCard.collection_id == SourceCollection.id)
        .filter(SourceCollection.parent_slug.is_(None))
        .group_by(SourceCollection.id)
        .all()
    )
    contains = _collection_contains(db)
    for coll, count in rows:
        if count == 0 and coll.last_fetched_at is not None:
            continue  # fetched and empty: nothing to show
        data = ThemeCollectionData(
            source_type=coll.source_type,
            slug=coll.slug,
            name=coll.name,
            card_count=count,
            last_fetched_at=coll.last_fetched_at,
            contains=sorted(contains.get(coll.id, ())),
        )
        classified = COLLECTION_THEMES.get(coll.source_type, {}).get(coll.slug)
        if classified:
            theme, value = classified
            value_for(theme, value, VALUE_LABELS[theme][value]).collections.append(data)
        src_value = CATALOG_SOURCE_VALUES.get(coll.source_type)
        if src_value:
            label = next(lbl for v, lbl in SOURCE_VALUES.values() if v == src_value)
            value_for("source", src_value, label).collections.append(data)

    themes: list[ThemeData] = []
    for key, label in THEMES:
        theme_values = [v for (t, _), v in values.items() if t == key]
        for v in theme_values:
            v.collections.sort(key=lambda c: (-c.card_count, c.name))
        theme_values.sort(key=lambda v: (-v.total, v.label))
        themes.append(ThemeData(key=key, label=label, values=theme_values))
    return themes
