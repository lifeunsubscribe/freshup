"""
Taste scoring service.

Learns per-user affinity for ingredient, cuisine, dish, and diet keys from
behavioural signals (cook events, ratings, likes, bookmarks, views) blended
with explicit taste preferences, then scores any recipe against those
affinities.

Blocking (allergy / never-suggest) applies only here — never to search or
list endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.user_cook_event import UserCookEvent
from src.db.models.user_recipe import UserRecipeRelation
from src.db.models.user_recipe_view import UserRecipeView
from src.services.card_tags import tags_from_text
from src.services.ingredient_keys import ALLERGENS, allergens_for, keys_for, keys_for_recipe
from src.services.recipe_themes import TAG_INDEX, normalize_tag

# source_type -> set of collection slugs considered "featured" for popularity scoring
FEATURED_COLLECTIONS: dict[str, set[str]] = {
    "hellofresh_web": {"hall-of-fame"},
    "homechef_web": {"customer-favorites"},
}

_SIGNAL_CUTOFF_DAYS = 90

# Explicit prior weights by taste level (never has no weight — it only blocks)
_PRIOR_WEIGHTS: dict[str, float] = {"love": 6.0, "like": 3.0, "less": -4.0}

# Common free-text aliases for allergen group slugs (see ALLERGENS in ingredient_keys.py).
# Slugs that are already canonical (e.g. "milk", "peanut") pass through unchanged.
# A value may be a list when the free-text term spans multiple allergen groups
# (e.g. "nuts" covers both tree-nut and peanut).
_ALLERGY_ALIASES: dict[str, str | list[str]] = {
    "dairy": "milk",
    "peanuts": "peanut",
    "tree nut": "tree-nut",
    "tree nuts": "tree-nut",
    "tree-nuts": "tree-nut",
    # "nut"/"nuts" colloquially covers both tree nuts and peanuts
    "nut": ["tree-nut", "peanut"],
    "nuts": ["tree-nut", "peanut"],
    "soya": "soy",
    "gluten": "wheat",
    "eggs": "egg",
    # ingredient-level shellfish terms that must map to the allergen group
    "shrimp": "shellfish",
    "prawn": "shellfish",
    "crab": "shellfish",
    "lobster": "shellfish",
    # "seafood" spans both fish and shellfish allergen groups
    "seafood": ["fish", "shellfish"],
}


def _allergy_groups(allergy_text: str) -> set[str]:
    """
    Resolve a free-text allergy string to canonical allergen group slugs.

    Resolution order:
    1. _ALLERGY_ALIASES lookup (handles "dairy", "peanuts", "tree nut", "shrimp", etc.)
    2. Canonical allergen slug passthrough (the value is already e.g. "milk", "peanut")
    3. keys_for() fallback: ingredient-level terms like "almonds", "cashews", "salmon", "prawns"
    """
    normalised = allergy_text.strip().lower()
    mapped = _ALLERGY_ALIASES.get(normalised)
    if mapped is not None:
        return set(mapped) if isinstance(mapped, list) else {mapped}
    if normalised in ALLERGENS:
        return {normalised}
    return allergens_for(keys_for(normalised))


def recipe_keys(recipe) -> set[str]:
    """
    Return the full key set for a recipe.

    ingredient:<key> for each key from the recipe's ingredients list, plus
    cuisine:, dish:, and diet: keys derived from the recipe's tags.
    """
    keys: set[str] = set()

    for key in keys_for_recipe(recipe):
        keys.add(f"ingredient:{key}")

    for raw_tag in recipe.tags or []:
        if not isinstance(raw_tag, str):
            continue
        classified = TAG_INDEX.get(normalize_tag(raw_tag))
        if classified and classified[0] in ("cuisine", "dish", "diet"):
            theme, value = classified
            keys.add(f"{theme}:{value}")

    return keys


def user_affinities(user_id: UUID, db: Session) -> dict[str, float]:
    """
    Build a normalised affinity dict for a user over their signal history.

    Behavioural weights:
    - Cook: +3 per cook, up to 3 cooks counted per recipe
    - Rated 4-5: +2; Rated 1-2: -3
    - Liked: +2
    - Bookmarked: +1
    - View: +0.5 per view, up to 2 views counted per recipe

    Signals older than 90 days count at half weight.

    Explicit priors from taste_preferences (flat dict key->level):
    - love: +6, like: +3, less: -4

    Returns dict normalised to -1..1 by dividing by the largest absolute value.
    Returns empty dict when no signals or preferences exist.
    """
    from src.db.models.recipe import Recipe
    from src.db.models.user import User

    now = datetime.now(timezone.utc)

    def _age_factor(dt: datetime | None) -> float:
        if dt is None:
            return 1.0
        aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        return 0.5 if (now - aware).days > _SIGNAL_CUTOFF_DAYS else 1.0

    raw: dict[str, float] = {}

    def _add(keys: set[str], delta: float) -> None:
        for k in keys:
            raw[k] = raw.get(k, 0.0) + delta

    # --- Cook events (cap at 3 per recipe) ---
    cook_events = (
        db.query(UserCookEvent)
        .filter(UserCookEvent.user_id == user_id)
        .all()
    )
    cook_groups: dict = {}
    for ev in cook_events:
        cook_groups.setdefault(ev.recipe_id, []).append(ev)

    for recipe_id, events in cook_groups.items():
        recipe = db.get(Recipe, recipe_id)
        if recipe is None:
            continue
        keys = recipe_keys(recipe)
        for ev in sorted(events, key=lambda e: e.cooked_at, reverse=True)[:3]:
            _add(keys, 3.0 * _age_factor(ev.cooked_at))

    # --- Ratings, likes, bookmarks ---
    relations = (
        db.query(UserRecipeRelation)
        .filter(UserRecipeRelation.user_id == user_id)
        .all()
    )
    for rel in relations:
        recipe = db.get(Recipe, rel.recipe_id)
        if recipe is None:
            continue
        keys = recipe_keys(recipe)
        af = _age_factor(rel.updated_at)
        if rel.rating is not None:
            if rel.rating >= 4:
                _add(keys, 2.0 * af)
            elif rel.rating <= 2:
                _add(keys, -3.0 * af)
        if rel.is_liked:
            _add(keys, 2.0 * af)
        if rel.is_bookmarked:
            _add(keys, 1.0 * af)

    # --- Views (cap at 2 per recipe) ---
    views = (
        db.query(UserRecipeView)
        .filter(UserRecipeView.user_id == user_id)
        .all()
    )
    view_groups: dict = {}
    for v in views:
        view_groups.setdefault(v.recipe_id, []).append(v)

    for recipe_id, view_list in view_groups.items():
        recipe = db.get(Recipe, recipe_id)
        if recipe is None:
            continue
        keys = recipe_keys(recipe)
        for v in sorted(view_list, key=lambda x: x.viewed_at, reverse=True)[:2]:
            _add(keys, 0.5 * _age_factor(v.viewed_at))

    # --- Explicit priors from taste_preferences ---
    user = db.get(User, user_id)
    if user is not None:
        for pref_key, level in (user.taste_preferences or {}).items():
            weight = _PRIOR_WEIGHTS.get(level)
            if weight is not None:
                raw[pref_key] = raw.get(pref_key, 0.0) + weight

    if not raw:
        return {}

    # Normalise to -1..1
    max_abs = max(abs(v) for v in raw.values())
    if max_abs == 0.0:
        return {}
    return {k: v / max_abs for k, v in raw.items()}


def is_blocked(recipe, user) -> bool:
    """
    Return True when the recipe should be blocked for this user.

    Blocked when any recipe key appears in taste_preferences with level "never",
    or when any allergen group for the recipe's ingredient keys matches a user
    allergy (case-insensitive).
    """
    prefs = user.taste_preferences or {}
    keys = recipe_keys(recipe)

    # never-suggest preference check
    for key in keys:
        if prefs.get(key) == "never":
            return True

    # Allergen check: strip the "ingredient:" prefix before calling allergens_for
    ingredient_keys = {k[len("ingredient:"):] for k in keys if k.startswith("ingredient:")}
    recipe_allergens = allergens_for(ingredient_keys)
    user_allergies: set[str] = set()
    for a in (user.allergies or []):
        user_allergies.update(_allergy_groups(str(a)))
    if recipe_allergens & user_allergies:
        return True

    return False


def score_recipe(recipe, affinities: dict[str, float]) -> float:
    """
    Return mean affinity over the recipe's keys that have an affinity entry.

    Returns 0.0 when no recipe key has a matching affinity.
    """
    if not affinities:
        return 0.0
    keys = recipe_keys(recipe)
    matched = [affinities[k] for k in keys if k in affinities]
    return sum(matched) / len(matched) if matched else 0.0


def card_keys(card, overlap_keys: set[str]) -> set[str]:
    """
    Return taste keys for a catalog card.

    ingredient: keys come from stored ingredient_keys when the column is not None,
    otherwise from ingredient: tags produced by tags_from_text on the card's name
    and headline. cuisine:/dish:/diet: keys are added from both tags_from_text and
    overlap_keys. side: tags are excluded.
    """
    text_tags = tags_from_text(card.name, getattr(card, "headline", None))
    keys: set[str] = set()

    if card.ingredient_keys is not None:
        for k in card.ingredient_keys:
            keys.add(f"ingredient:{k}")
    else:
        for tag in text_tags:
            if tag.startswith("ingredient:"):
                keys.add(tag)

    _TASTE_PREFIXES = ("cuisine", "dish", "diet")
    for tag in text_tags:
        if tag.split(":", 1)[0] in _TASTE_PREFIXES:
            keys.add(tag)
    for tag in overlap_keys:
        if tag.split(":", 1)[0] in _TASTE_PREFIXES:
            keys.add(tag)

    return keys


def popularity(card, source_prior: "float | None", featured: set[str]) -> float:
    """
    Return a 0..1 popularity score for a catalog card.

    Rated card: Bayesian average (rating * count + prior_mean * 50) / (count + 50)
    mapped from the 1..5 scale to 0..1 via (x - 1) / 4, where prior_mean is
    source_prior. A card in its source's featured collection scores at least 0.8.
    Unrated, unfeatured: source_prior mapped the same way, or 0.5 when source_prior
    is None (source has no rated cards).
    """
    source_featured = FEATURED_COLLECTIONS.get(card.source_type, set())
    in_featured = bool(featured & source_featured)

    rating = card.rating
    count = card.rating_count or 0

    if rating is None or count == 0:
        if source_prior is None:
            base = 0.5
        else:
            base = max(0.0, min(1.0, (source_prior - 1.0) / 4.0))
        return max(base, 0.8) if in_featured else base

    # Rated: Bayesian smoothing with 50-vote prior at the source mean
    prior = source_prior if source_prior is not None else rating
    bayes = (rating * count + prior * 50) / (count + 50)
    score = max(0.0, min(1.0, (bayes - 1.0) / 4.0))
    return max(score, 0.8) if in_featured else score


def is_card_blocked(card, keys: set[str], user) -> bool:
    """
    Return True when the card should be blocked for this user.

    Blocked when any key appears in taste_preferences with level "never", or when the
    user has any allergy and the card's ingredient_keys is None (ingredients unknown),
    or when the card's known ingredients match a user allergy group.
    """
    prefs = user.taste_preferences or {}
    for key in keys:
        if prefs.get(key) == "never":
            return True

    # "Has allergies" is what the user typed, not what resolves to an allergen
    # group: "garlic" or "lactose" maps to no group, and that user must still
    # not be shown a card whose ingredients are unknown.
    if not any(str(a).strip() for a in (user.allergies or [])):
        return False

    # Unknown ingredients are not safe for allergic users
    if card.ingredient_keys is None:
        return True

    user_allergies: set[str] = set()
    for a in (user.allergies or []):
        user_allergies.update(_allergy_groups(str(a)))

    ingredient_key_set = {k[len("ingredient:"):] for k in keys if k.startswith("ingredient:")}
    return bool(allergens_for(ingredient_key_set) & user_allergies)
