"""Tests for the taste scoring service."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.services.taste_service import (
    is_blocked,
    recipe_keys,
    score_recipe,
    user_affinities,
)


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _make_ingredient(name: str):
    return SimpleNamespace(ingredient_name=name)


def _make_recipe(ingredient_names: list[str] = None, tags: list[str] = None):
    return SimpleNamespace(
        id=uuid4(),
        ingredients=[_make_ingredient(n) for n in (ingredient_names or [])],
        tags=tags or [],
    )


def _make_user(taste_preferences=None, allergies=None):
    return SimpleNamespace(
        id=uuid4(),
        taste_preferences=taste_preferences or {},
        allergies=allergies or [],
    )


def _now():
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


# ---------------------------------------------------------------------------
# Minimal mock DB
# ---------------------------------------------------------------------------

class _MockQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class _MockDB:
    def __init__(self, cook_events=None, relations=None, views=None, recipes=None, user=None):
        self._cook_events = cook_events or []
        self._relations = relations or []
        self._views = views or []
        self._recipes = recipes or {}
        self._user = user

    def query(self, model):
        from src.db.models.user_cook_event import UserCookEvent
        from src.db.models.user_recipe import UserRecipeRelation
        from src.db.models.user_recipe_view import UserRecipeView

        if model is UserCookEvent:
            return _MockQuery(self._cook_events)
        if model is UserRecipeRelation:
            return _MockQuery(self._relations)
        if model is UserRecipeView:
            return _MockQuery(self._views)
        return _MockQuery([])

    def get(self, model, id):
        from src.db.models.recipe import Recipe
        from src.db.models.user import User

        if model is Recipe:
            return self._recipes.get(id)
        if model is User:
            return self._user
        return None


def _cook_event(user_id, recipe_id, cooked_at=None):
    return SimpleNamespace(
        user_id=user_id,
        recipe_id=recipe_id,
        cooked_at=cooked_at or _now(),
    )


def _relation(user_id, recipe_id, rating=None, is_liked=False, is_bookmarked=False, updated_at=None):
    return SimpleNamespace(
        user_id=user_id,
        recipe_id=recipe_id,
        rating=rating,
        is_liked=is_liked,
        is_bookmarked=is_bookmarked,
        updated_at=updated_at or _now(),
    )


def _view(user_id, recipe_id, viewed_at=None):
    return SimpleNamespace(
        user_id=user_id,
        recipe_id=recipe_id,
        viewed_at=viewed_at or _now(),
    )


# ---------------------------------------------------------------------------
# recipe_keys
# ---------------------------------------------------------------------------


class TestRecipeKeys:
    def test_ingredient_keys_have_prefix(self):
        recipe = _make_recipe(ingredient_names=["chicken breast"])
        keys = recipe_keys(recipe)
        assert "ingredient:chicken" in keys

    def test_cuisine_tag_produces_prefixed_key(self):
        recipe = _make_recipe(tags=["Italian"])
        keys = recipe_keys(recipe)
        assert "cuisine:italian" in keys

    def test_dish_tag_produces_prefixed_key(self):
        recipe = _make_recipe(tags=["tacos"])
        keys = recipe_keys(recipe)
        assert "dish:tacos" in keys

    def test_diet_tag_produces_prefixed_key(self):
        recipe = _make_recipe(tags=["vegetarian"])
        keys = recipe_keys(recipe)
        assert "diet:vegetarian" in keys

    def test_ingredient_type_tag_not_duplicated_as_theme(self):
        # "chicken" is both an ingredient and an ingredient-theme tag —
        # the tag produces ingredient:chicken from TAG_INDEX's "ingredient" theme
        # but the issue only maps cuisine/dish/diet from tags, so "ingredient:chicken"
        # still appears (via keys_for_recipe), and nothing else unexpected appears.
        recipe = _make_recipe(ingredient_names=["chicken"], tags=["chicken"])
        keys = recipe_keys(recipe)
        assert "ingredient:chicken" in keys

    def test_unknown_tag_ignored(self):
        recipe = _make_recipe(tags=["mystery-tag-xyz"])
        keys = recipe_keys(recipe)
        assert all(not k.startswith("mystery") for k in keys)

    def test_empty_recipe_returns_empty_set(self):
        recipe = _make_recipe()
        assert recipe_keys(recipe) == set()

    def test_non_string_tag_ignored(self):
        recipe = _make_recipe(tags=[None, 42, "italian"])
        keys = recipe_keys(recipe)
        assert "cuisine:italian" in keys


# ---------------------------------------------------------------------------
# user_affinities — signal weights
# ---------------------------------------------------------------------------


class TestUserAffinitiesSignals:
    def test_no_signals_returns_empty(self):
        user = _make_user()
        db = _MockDB(user=user)
        assert user_affinities(user.id, db) == {}

    def test_cook_raises_affinity(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["chicken"])
        db = _MockDB(
            cook_events=[_cook_event(user.id, recipe.id)],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:chicken", 0) > 0

    def test_high_rating_raises_affinity(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["salmon"])
        db = _MockDB(
            relations=[_relation(user.id, recipe.id, rating=5)],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:salmon", 0) > 0

    def test_low_rating_lowers_affinity(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["pork"])
        db = _MockDB(
            relations=[_relation(user.id, recipe.id, rating=1)],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:pork", 0) < 0

    def test_like_raises_affinity(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["beef"])
        db = _MockDB(
            relations=[_relation(user.id, recipe.id, is_liked=True)],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:beef", 0) > 0

    def test_bookmark_raises_affinity(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["tofu"])
        db = _MockDB(
            relations=[_relation(user.id, recipe.id, is_bookmarked=True)],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:tofu", 0) > 0

    def test_view_raises_affinity(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["shrimp"])
        db = _MockDB(
            views=[_view(user.id, recipe.id)],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:shrimp", 0) > 0

    def test_cook_capped_at_three(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["chicken"])
        recipe_ref = _make_recipe(ingredient_names=["beef"])
        # 5 cooks on chicken — cap means only 3 count, raw = 9
        events = [_cook_event(user.id, recipe.id) for _ in range(5)]
        # Reference: 1 high rating on beef, raw = 2
        rel = _relation(user.id, recipe_ref.id, rating=5)
        db = _MockDB(
            cook_events=events,
            relations=[rel],
            recipes={recipe.id: recipe, recipe_ref.id: recipe_ref},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        # Cap enforced: chicken raw = 3*3 = 9 (not 5*3 = 15); beef raw = 2; max = 9
        # If the cap were absent, beef would be 2/15 ≈ 0.133 instead of 2/9 ≈ 0.222
        assert affinities.get("ingredient:chicken", 0) == pytest.approx(1.0)
        assert affinities.get("ingredient:beef", 0) == pytest.approx(2.0 / 9.0)

    def test_views_capped_at_two(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["salmon"])
        recipe_ref = _make_recipe(ingredient_names=["beef"])
        views_list = [_view(user.id, recipe.id) for _ in range(5)]
        # Reference: 1 high rating on beef, raw = 2
        rel = _relation(user.id, recipe_ref.id, rating=5)
        db = _MockDB(
            views=views_list,
            relations=[rel],
            recipes={recipe.id: recipe, recipe_ref.id: recipe_ref},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        # Cap enforced: salmon raw = 2*0.5 = 1.0 (not 5*0.5 = 2.5); beef raw = 2; max = 2
        # If the cap were absent, salmon would be 2.5/2.5 = 1.0 and beef 2/2.5 = 0.8
        assert affinities.get("ingredient:beef", 0) == pytest.approx(1.0)
        assert affinities.get("ingredient:salmon", 0) == pytest.approx(0.5)

    def test_affinities_normalised_to_minus_one_to_one(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["chicken"])
        # 3 cooks (max raw = 9) + high rating (raw += 2) → max raw = 11
        events = [_cook_event(user.id, recipe.id) for _ in range(3)]
        rel = _relation(user.id, recipe.id, rating=5)
        db = _MockDB(
            cook_events=events,
            relations=[rel],
            recipes={recipe.id: recipe},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        for v in affinities.values():
            assert -1.0 <= v <= 1.0

    def test_weight_ordering_cook_gt_rating_gt_bookmark(self):
        """3 cooks (9) > rating-5 (2) > bookmark (1)."""
        user = _make_user()
        r_cooked = _make_recipe(ingredient_names=["chicken"])
        r_rated = _make_recipe(ingredient_names=["beef"])
        r_bookmarked = _make_recipe(ingredient_names=["tofu"])

        cook_events = [_cook_event(user.id, r_cooked.id) for _ in range(3)]
        rel_rated = _relation(user.id, r_rated.id, rating=5)
        rel_bookmarked = _relation(user.id, r_bookmarked.id, is_bookmarked=True)

        db = _MockDB(
            cook_events=cook_events,
            relations=[rel_rated, rel_bookmarked],
            recipes={
                r_cooked.id: r_cooked,
                r_rated.id: r_rated,
                r_bookmarked.id: r_bookmarked,
            },
            user=user,
        )
        affinities = user_affinities(user.id, db)
        chicken_score = affinities["ingredient:chicken"]
        beef_score = affinities["ingredient:beef"]
        tofu_score = affinities["ingredient:tofu"]
        assert chicken_score > beef_score > tofu_score > 0


# ---------------------------------------------------------------------------
# user_affinities — old signals count half
# ---------------------------------------------------------------------------


class TestUserAffinitiesAgeHalfWeight:
    def test_old_cook_counts_half(self):
        """A single cook 91 days ago should produce exactly half the weight of a fresh one."""
        user = _make_user()
        recipe_fresh = _make_recipe(ingredient_names=["chicken"])
        recipe_old = _make_recipe(ingredient_names=["beef"])

        events_fresh = [_cook_event(user.id, recipe_fresh.id, cooked_at=_now())]
        events_old = [_cook_event(user.id, recipe_old.id, cooked_at=_days_ago(91))]

        db = _MockDB(
            cook_events=events_fresh + events_old,
            recipes={recipe_fresh.id: recipe_fresh, recipe_old.id: recipe_old},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        # fresh cook raw = 3.0; old cook raw = 1.5; normalised by max (3.0)
        assert affinities["ingredient:chicken"] == pytest.approx(1.0)
        assert affinities["ingredient:beef"] == pytest.approx(0.5)

    def test_old_rating_counts_half(self):
        user = _make_user()
        recipe_fresh = _make_recipe(ingredient_names=["salmon"])
        recipe_old = _make_recipe(ingredient_names=["pork"])

        rel_fresh = _relation(user.id, recipe_fresh.id, rating=5, updated_at=_now())
        rel_old = _relation(user.id, recipe_old.id, rating=5, updated_at=_days_ago(91))

        db = _MockDB(
            relations=[rel_fresh, rel_old],
            recipes={recipe_fresh.id: recipe_fresh, recipe_old.id: recipe_old},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        # fresh raw = 2.0; old raw = 1.0; normalised by 2.0
        assert affinities["ingredient:salmon"] == pytest.approx(1.0)
        assert affinities["ingredient:pork"] == pytest.approx(0.5)

    def test_exactly_90_days_not_halved(self):
        """Signal exactly 90 days old is NOT halved — only strictly older than 90."""
        user = _make_user()
        recipe_at_90 = _make_recipe(ingredient_names=["chicken"])
        recipe_at_91 = _make_recipe(ingredient_names=["beef"])
        event_at_90 = _cook_event(user.id, recipe_at_90.id, cooked_at=_days_ago(90))
        event_at_91 = _cook_event(user.id, recipe_at_91.id, cooked_at=_days_ago(91))
        db = _MockDB(
            cook_events=[event_at_90, event_at_91],
            recipes={recipe_at_90.id: recipe_at_90, recipe_at_91.id: recipe_at_91},
            user=user,
        )
        affinities = user_affinities(user.id, db)
        # 90 days: full weight raw=3.0 (max denominator); 91 days: half weight raw=1.5
        # chicken=1.0 confirms the 90-day boundary is not halved; beef=0.5 confirms 91 is
        assert affinities["ingredient:chicken"] == pytest.approx(1.0)
        assert affinities["ingredient:beef"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# user_affinities — explicit priors
# ---------------------------------------------------------------------------


class TestUserAffinitiesExplicitPriors:
    def test_love_adds_prior(self):
        user = _make_user(taste_preferences={"ingredient:chicken": "love"})
        db = _MockDB(user=user)
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:chicken", 0) == pytest.approx(1.0)

    def test_like_adds_prior(self):
        user = _make_user(taste_preferences={"cuisine:italian": "like"})
        db = _MockDB(user=user)
        affinities = user_affinities(user.id, db)
        assert affinities.get("cuisine:italian", 0) == pytest.approx(1.0)

    def test_less_lowers_prior(self):
        user = _make_user(taste_preferences={"ingredient:pork": "less"})
        db = _MockDB(user=user)
        affinities = user_affinities(user.id, db)
        assert affinities.get("ingredient:pork", 0) < 0

    def test_never_adds_no_affinity(self):
        """never preference creates no entry in affinities (only used for blocking)."""
        user = _make_user(taste_preferences={"ingredient:peanut": "never"})
        db = _MockDB(user=user)
        affinities = user_affinities(user.id, db)
        assert "ingredient:peanut" not in affinities

    def test_love_weight_greater_than_like(self):
        user = _make_user(taste_preferences={
            "ingredient:chicken": "love",
            "ingredient:beef": "like",
        })
        db = _MockDB(user=user)
        affinities = user_affinities(user.id, db)
        # love=6, like=3; max_abs=6; chicken=1.0, beef=0.5
        assert affinities["ingredient:chicken"] > affinities["ingredient:beef"]

    def test_less_does_not_block(self):
        """less lowers affinity but is_blocked must return False for a less key."""
        user = _make_user(taste_preferences={"ingredient:pork": "less"})
        recipe = _make_recipe(ingredient_names=["pork loin"])
        assert not is_blocked(recipe, user)


# ---------------------------------------------------------------------------
# is_blocked
# ---------------------------------------------------------------------------


class TestIsBlocked:
    def test_never_preference_blocks(self):
        user = _make_user(taste_preferences={"ingredient:pork": "never"})
        recipe = _make_recipe(ingredient_names=["pork chop"])
        assert is_blocked(recipe, user)

    def test_never_cuisine_blocks(self):
        user = _make_user(taste_preferences={"cuisine:italian": "never"})
        recipe = _make_recipe(tags=["Italian"])
        assert is_blocked(recipe, user)

    def test_no_matching_never_not_blocked(self):
        user = _make_user(taste_preferences={"ingredient:pork": "never"})
        recipe = _make_recipe(ingredient_names=["chicken breast"])
        assert not is_blocked(recipe, user)

    def test_allergy_blocks_via_allergen_group(self):
        """Peanut allergy blocks a recipe containing peanut butter."""
        user = _make_user(allergies=["peanut"])
        recipe = _make_recipe(ingredient_names=["peanut butter"])
        assert is_blocked(recipe, user)

    def test_allergy_case_insensitive(self):
        user = _make_user(allergies=["PEANUT"])
        recipe = _make_recipe(ingredient_names=["peanut butter"])
        assert is_blocked(recipe, user)

    def test_allergy_dairy_blocks_cream(self):
        user = _make_user(allergies=["milk"])
        recipe = _make_recipe(ingredient_names=["heavy cream"])
        assert is_blocked(recipe, user)

    def test_allergy_wheat_blocks_pasta(self):
        user = _make_user(allergies=["wheat"])
        recipe = _make_recipe(ingredient_names=["penne pasta"])
        assert is_blocked(recipe, user)

    def test_allergy_dairy_alias_blocks_cream(self):
        """'dairy' is an alias for the 'milk' allergen group and should block milk/cream."""
        user = _make_user(allergies=["dairy"])
        recipe = _make_recipe(ingredient_names=["heavy cream"])
        assert is_blocked(recipe, user)

    def test_allergy_tree_nut_alias_blocks_almond(self):
        """'tree nut' (with space) maps to 'tree-nut' allergen group."""
        user = _make_user(allergies=["tree nut"])
        recipe = _make_recipe(ingredient_names=["almond"])
        assert is_blocked(recipe, user)

    def test_allergy_peanuts_plural_blocks_peanut_butter(self):
        """'peanuts' (plural) maps to the 'peanut' allergen group."""
        user = _make_user(allergies=["peanuts"])
        recipe = _make_recipe(ingredient_names=["peanut butter"])
        assert is_blocked(recipe, user)

    def test_allergy_almonds_plural_blocks_tree_nut_recipe(self):
        """'almonds' resolves through keys_for() to tree-nut group."""
        user = _make_user(allergies=["almonds"])
        recipe = _make_recipe(ingredient_names=["almond"])
        assert is_blocked(recipe, user)

    def test_allergy_cashews_plural_blocks_tree_nut_recipe(self):
        """'cashews' resolves through keys_for() to tree-nut group."""
        user = _make_user(allergies=["cashews"])
        recipe = _make_recipe(ingredient_names=["cashew cream"])
        assert is_blocked(recipe, user)

    def test_allergy_prawns_plural_blocks_shellfish_recipe(self):
        """'prawns' (plural of a shellfish ingredient) resolves to shellfish group."""
        user = _make_user(allergies=["prawns"])
        recipe = _make_recipe(ingredient_names=["shrimp"])
        assert is_blocked(recipe, user)

    def test_allergy_salmon_ingredient_name_blocks_fish_recipe(self):
        """'salmon' (ingredient name, not a slug) resolves to fish group."""
        user = _make_user(allergies=["salmon"])
        recipe = _make_recipe(ingredient_names=["salmon"])
        assert is_blocked(recipe, user)

    def test_allergy_tuna_ingredient_name_blocks_fish_recipe(self):
        """'tuna' (ingredient name, not a slug) resolves to fish group."""
        user = _make_user(allergies=["tuna"])
        recipe = _make_recipe(ingredient_names=["tuna"])
        assert is_blocked(recipe, user)

    def test_no_allergy_not_blocked(self):
        user = _make_user(allergies=[])
        recipe = _make_recipe(ingredient_names=["peanut butter"])
        assert not is_blocked(recipe, user)

    def test_less_does_not_block(self):
        user = _make_user(taste_preferences={"ingredient:pork": "less"})
        recipe = _make_recipe(ingredient_names=["pork chop"])
        assert not is_blocked(recipe, user)

    def test_no_prefs_no_allergy_not_blocked(self):
        user = _make_user()
        recipe = _make_recipe(ingredient_names=["chicken"], tags=["Italian"])
        assert not is_blocked(recipe, user)


# ---------------------------------------------------------------------------
# score_recipe
# ---------------------------------------------------------------------------


class TestScoreRecipe:
    def test_no_affinities_returns_zero(self):
        recipe = _make_recipe(ingredient_names=["chicken"])
        assert score_recipe(recipe, {}) == pytest.approx(0.0)

    def test_no_matching_keys_returns_zero(self):
        recipe = _make_recipe(ingredient_names=["chicken"])
        affinities = {"ingredient:beef": 1.0}
        assert score_recipe(recipe, affinities) == pytest.approx(0.0)

    def test_single_matching_key(self):
        recipe = _make_recipe(ingredient_names=["chicken"])
        affinities = {"ingredient:chicken": 0.8}
        assert score_recipe(recipe, affinities) == pytest.approx(0.8)

    def test_mean_over_matched_keys(self):
        recipe = _make_recipe(ingredient_names=["chicken"], tags=["italian"])
        affinities = {"ingredient:chicken": 1.0, "cuisine:italian": 0.6}
        # mean = (1.0 + 0.6) / 2 = 0.8
        assert score_recipe(recipe, affinities) == pytest.approx(0.8)

    def test_unmatched_keys_excluded_from_mean(self):
        recipe = _make_recipe(ingredient_names=["chicken", "garlic"])
        # Only chicken has an affinity; garlic does not.
        affinities = {"ingredient:chicken": 0.8}
        # mean = 0.8 / 1 = 0.8
        assert score_recipe(recipe, affinities) == pytest.approx(0.8)

    def test_negative_affinity_drags_score_down(self):
        recipe = _make_recipe(ingredient_names=["pork"])
        affinities = {"ingredient:pork": -1.0}
        assert score_recipe(recipe, affinities) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# End-to-end: no signals + no prefs → {} and 0.0
# ---------------------------------------------------------------------------


class TestColdStart:
    def test_empty_affinities(self):
        user = _make_user()
        db = _MockDB(user=user)
        assert user_affinities(user.id, db) == {}

    def test_all_recipes_score_zero(self):
        user = _make_user()
        db = _MockDB(user=user)
        affinities = user_affinities(user.id, db)
        for recipe in [
            _make_recipe(ingredient_names=["chicken"]),
            _make_recipe(tags=["Italian"]),
            _make_recipe(ingredient_names=["salmon"], tags=["vegetarian"]),
        ]:
            assert score_recipe(recipe, affinities) == pytest.approx(0.0)
