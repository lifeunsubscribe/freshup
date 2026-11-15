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
from src.services.ingredient_keys import allergens_for, keys_for_recipe
from src.services.recipe_themes import TAG_INDEX, normalize_tag

_SIGNAL_CUTOFF_DAYS = 90

# Explicit prior weights by taste level (never has no weight — it only blocks)
_PRIOR_WEIGHTS: dict[str, float] = {"love": 6.0, "like": 3.0, "less": -4.0}


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
    user_allergies = {str(a).lower() for a in (user.allergies or [])}
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
