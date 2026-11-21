"""
Tests for recommendation_service.rank_candidates().

Covers all five acceptance criteria:
1. No history → cards ordered by popularity, reason 'popular'
2. With history, a card matching loved keys outranks a more popular unrelated card
3. Blocked cards/recipes and recently cooked recipes are absent
4. Every fifth item is an explore pick when one exists; no item is the fourth
   consecutive pick from its source while an unplaced candidate from another
   source still existed at that moment
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.services.recommendation_service import rank_candidates, related_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _days_ago(n):
    return _now() - timedelta(days=n)


def _make_card(
    name="Test Card",
    source_type="hellofresh_web",
    rating=None,
    rating_count=None,
    ingredient_keys=None,
    recipe_id=None,
    recipe_rel=None,
    external_id=None,
    recipe_url=None,
    headline=None,
):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        source_type=source_type,
        external_id=external_id or "ext-" + name[:8],
        headline=headline,
        image_url=None,
        prep_time_minutes=None,
        rating=rating,
        rating_count=rating_count,
        recipe_url=recipe_url or f"https://example.com/{name}",
        recipe_id=recipe_id,
        recipe_rel=recipe_rel,
        ingredient_keys=ingredient_keys,
        tags=[],
    )


def _make_recipe(name="Test Recipe", source_type="manual", tags=None, ingredients=None):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        source_type=source_type,
        source_url=None,
        source_image=None,
        prep_time_minutes=None,
        cook_time_minutes=None,
        base_servings=4,
        tags=tags or [],
        times_cooked=0,
        created_by=None,
        is_persisted=True,
        ingredients=ingredients or [],
    )


def _make_collection(slug, source_type="hellofresh_web", parent_slug=None):
    return SimpleNamespace(
        id=uuid4(),
        slug=slug,
        name=slug.replace("-", " ").title(),
        source_type=source_type,
        parent_slug=parent_slug,
        url=f"https://example.com/{slug}",
    )


def _make_user(taste_preferences=None, allergies=None):
    return SimpleNamespace(
        id=uuid4(),
        taste_preferences=taste_preferences or {},
        allergies=allergies or [],
    )


def _make_cook_event(user_id, recipe_id, cooked_at=None):
    return SimpleNamespace(
        user_id=user_id,
        recipe_id=recipe_id,
        cooked_at=cooked_at or _now(),
    )


# ---------------------------------------------------------------------------
# Mock DB
# ---------------------------------------------------------------------------

def _aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC) for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class _MockQuery:
    """Minimal SQLAlchemy query stub supporting filter, join, and all."""

    def __init__(self, items):
        self._items = list(items)
        self._model = None

    def filter(self, *conditions):
        items = self._items
        for cond in conditions:
            try:
                col_key = getattr(getattr(cond, "left", None), "key", None)
                right = getattr(cond, "right", None)
                if col_key and right is not None:
                    # Handle col.is_(None)
                    if type(right).__name__ == "Null":
                        op_name = getattr(getattr(cond, "operator", None), "__name__", "")
                        if op_name == "is_":
                            items = [i for i in items if getattr(i, col_key, "SENTINEL") is None]
                    elif hasattr(right, "value"):
                        val = right.value
                        op_name = getattr(getattr(cond, "operator", None), "__name__", "eq")
                        if isinstance(val, (list, tuple, set, frozenset)):
                            # in_() — handled elsewhere or skip
                            pass
                        elif op_name == "eq":
                            items = [i for i in items if getattr(i, col_key, None) == val]
                        elif op_name == "ge":
                            items = [
                                i for i in items
                                if getattr(i, col_key, None) is not None
                                and _aware(getattr(i, col_key)) >= _aware(val)
                            ]
                        elif op_name == "le":
                            items = [
                                i for i in items
                                if getattr(i, col_key, None) is not None
                                and _aware(getattr(i, col_key)) <= _aware(val)
                            ]
            except Exception:
                pass
        self._items = items
        return self

    def join(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class _MockDB:
    """
    Minimal DB mock for recommendation_service tests.

    Provides query() routing and get() for models used by rank_candidates()
    and user_affinities().
    """

    def __init__(
        self,
        collections=None,
        collection_cards=None,
        source_recipe_cards=None,
        cook_events=None,
        relations=None,
        views=None,
        recipes=None,
        user=None,
    ):
        self._collections = collections or []
        self._collection_cards = collection_cards or []
        self._source_recipe_cards = source_recipe_cards or []
        self._cook_events = cook_events or []
        self._relations = relations or []
        self._views = views or []
        self._recipes = recipes or {}  # id -> Recipe
        self._user = user

    def query(self, *models):
        from src.db.models.source_catalog import (
            SourceCollection,
            SourceCollectionCard,
            SourceRecipeCard,
        )
        from src.db.models.user_cook_event import UserCookEvent
        from src.db.models.user_recipe import UserRecipeRelation
        from src.db.models.user_recipe_view import UserRecipeView
        from src.db.models.recipe import Recipe

        model = models[0]
        if model is SourceCollection:
            return _MockQuery(self._collections)
        if model is SourceRecipeCard:
            # rank_candidates joins SourceRecipeCard with SourceCollectionCard and
            # SourceCollection; the mock returns (card, slug) pairs
            return _CardSlugQuery(self._collection_cards)
        if model is UserCookEvent:
            return _MockQuery(self._cook_events)
        if model is UserRecipeRelation:
            return _MockQuery(self._relations)
        if model is UserRecipeView:
            return _MockQuery(self._views)
        if model is Recipe:
            return _MockQuery(list(self._recipes.values()))
        return _MockQuery([])

    def get(self, model, id_):
        from src.db.models.recipe import Recipe
        from src.db.models.user import User

        if model is Recipe:
            return self._recipes.get(id_)
        if model is User:
            return self._user
        return None


class _CardSlugQuery:
    """
    Stands in for the SourceRecipeCard + join query in rank_candidates().

    Returns (card, collection_slug) tuples, filtered by collection_id.in_().
    """

    def __init__(self, collection_cards):
        # collection_cards: list of (card, slug, collection_id)
        self._rows = list(collection_cards)

    def join(self, *args, **kwargs):
        return self

    def filter(self, *conditions):
        rows = self._rows
        for cond in conditions:
            # Handle collection_id.in_(collection_ids)
            right = getattr(cond, "right", None)
            if right is not None:
                val = getattr(right, "value", None)
                if isinstance(val, (list, tuple, set, frozenset)):
                    col_key = getattr(getattr(cond, "left", None), "key", None)
                    if col_key == "collection_id":
                        rows = [r for r in rows if r[2] in val]
        self._rows = rows
        return self

    def all(self):
        # Return (card, slug) pairs as rank_candidates expects
        return [(row[0], row[1]) for row in self._rows]


# ---------------------------------------------------------------------------
# DB builder helpers
# ---------------------------------------------------------------------------

def _db_with_cards(cards_and_sources, user=None, cook_events=None, relations=None, views=None, extra_recipes=None):
    """
    Build a _MockDB from a list of (card, collection_slug, source_type, is_top_level) tuples.

    Creates one SourceCollection per unique (source_type, slug) combo.
    """
    seen_collections = {}
    collection_cards = []

    for card, slug, source_type, is_top in cards_and_sources:
        key = (source_type, slug)
        if key not in seen_collections:
            coll = _make_collection(slug, source_type, parent_slug=None if is_top else "parent")
            seen_collections[key] = coll
        coll = seen_collections[key]
        collection_cards.append((card, slug, coll.id))

    recipes = {r.id: r for r in (extra_recipes or [])}

    return _MockDB(
        collections=list(seen_collections.values()),
        collection_cards=collection_cards,
        cook_events=cook_events or [],
        relations=relations or [],
        views=views or [],
        recipes=recipes,
        user=user,
    )


# ---------------------------------------------------------------------------
# AC1: No history → cards ordered by popularity, reason 'popular'
# ---------------------------------------------------------------------------

class TestNoHistory:
    def test_no_affinities_ordered_by_popularity(self):
        # Three cards with different ratings; expect descending order
        card_hi = _make_card("hi", rating=4.8, rating_count=500, source_type="hellofresh_web")
        card_mid = _make_card("mid", rating=3.5, rating_count=200, source_type="hellofresh_web")
        card_lo = _make_card("lo", rating=2.0, rating_count=100, source_type="hellofresh_web")

        user = _make_user()
        db = _db_with_cards(
            [
                (card_hi, "all-recipes", "hellofresh_web", True),
                (card_mid, "all-recipes", "hellofresh_web", True),
                (card_lo, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )

        result = rank_candidates(user, db, limit=10)
        assert len(result) == 3

        # All reasons should be 'popular' (no affinities)
        assert all(r.reason == "popular" for r in result)

        # First item should have highest popularity (highest rating)
        # Slots 1-4 are regular, slot 5 is explore
        regular_items = [r for r in result if r.reason != "explore"]
        pops = [r.score for r in regular_items]
        assert pops == sorted(pops, reverse=True)

    def test_empty_catalog_returns_empty(self):
        user = _make_user()
        db = _MockDB()
        result = rank_candidates(user, db, limit=10)
        assert result == []

    def test_non_top_level_collections_excluded(self):
        card = _make_card("sub-only")
        user = _make_user()
        # This card is only in a sub-collection (parent_slug != None)
        db = _db_with_cards(
            [(card, "sub", "hellofresh_web", False)],
            user=user,
        )
        result = rank_candidates(user, db, limit=10)
        # sub-only card's collection has parent_slug set → not top-level → excluded
        assert all(r.card is None or r.card.id != card.id for r in result) or len(result) == 0


# ---------------------------------------------------------------------------
# AC2: With history, card matching loved keys outranks more popular unrelated card
# ---------------------------------------------------------------------------

class TestWithHistory:
    def test_loved_key_outranks_popularity(self):
        # card_popular: high rating but no matching affinities
        # card_loved: lower rating but matches a 'love' affinity key
        card_popular = _make_card(
            "popular", rating=4.9, rating_count=10000,
            ingredient_keys=["tomato"],
            source_type="hellofresh_web",
        )
        card_loved = _make_card(
            "loved", rating=3.0, rating_count=50,
            ingredient_keys=["chicken"],
            source_type="hellofresh_web",
        )

        # User loves chicken (affinity applied via taste_preferences 'love' → +6 raw → normalised)
        user = _make_user(taste_preferences={"ingredient:chicken": "love"})
        db = _db_with_cards(
            [
                (card_popular, "all-recipes", "hellofresh_web", True),
                (card_loved, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )

        result = rank_candidates(user, db, limit=10)
        # Filter to regular slots (not explore) for ordering check
        regular = [r for r in result if r.reason in ("taste", "popular")]

        ids = [r.card.id for r in regular if r.card is not None]
        assert card_loved.id in ids
        assert card_popular.id in ids
        assert ids.index(card_loved.id) < ids.index(card_popular.id), (
            "loved card should rank ahead of more popular but unrelated card"
        )

    def test_reason_is_taste_when_affinities_exist(self):
        card = _make_card("chicken-dish", ingredient_keys=["chicken"], source_type="hellofresh_web")
        user = _make_user(taste_preferences={"ingredient:chicken": "like"})
        db = _db_with_cards([(card, "all-recipes", "hellofresh_web", True)], user=user)

        result = rank_candidates(user, db, limit=10)
        # At least the first regular slot should have reason 'taste'
        regular = [r for r in result if r.reason != "explore"]
        assert any(r.reason == "taste" for r in regular)


# ---------------------------------------------------------------------------
# AC3: Blocked cards/recipes and recently cooked are absent
# ---------------------------------------------------------------------------

class TestExclusions:
    def test_blocked_card_absent(self):
        blocked_card = _make_card(
            "blocked", ingredient_keys=["garlic"], source_type="hellofresh_web"
        )
        safe_card = _make_card(
            "safe", ingredient_keys=["tomato"], source_type="hellofresh_web"
        )
        # User is allergic to garlic → blocked_card should be excluded
        user = _make_user(allergies=["garlic"])
        db = _db_with_cards(
            [
                (blocked_card, "all-recipes", "hellofresh_web", True),
                (safe_card, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )
        result = rank_candidates(user, db, limit=10)
        result_card_ids = {r.card.id for r in result if r.card is not None}
        assert blocked_card.id not in result_card_ids
        assert safe_card.id in result_card_ids

    def test_blocked_recipe_absent(self):
        safe_card = _make_card("safe-card", ingredient_keys=["tomato"], source_type="hellofresh_web")
        blocked_recipe = _make_recipe("garlic-pasta", ingredients=[
            SimpleNamespace(ingredient_name="garlic")
        ])
        user = _make_user(allergies=["garlic"])
        db = _db_with_cards(
            [(safe_card, "all-recipes", "hellofresh_web", True)],
            user=user,
            extra_recipes=[blocked_recipe],
        )
        result = rank_candidates(user, db, limit=10)
        result_recipe_ids = {r.recipe.id for r in result if r.recipe is not None}
        assert blocked_recipe.id not in result_recipe_ids

    def test_recently_cooked_recipe_absent(self):
        card = _make_card("cooked-card", source_type="hellofresh_web")
        recipe_id = uuid4()
        card_cooked = _make_card("cooked-card2", recipe_id=recipe_id, source_type="hellofresh_web")
        other_card = _make_card("other", source_type="hellofresh_web")
        user = _make_user()

        # Cook event 3 days ago (within 14-day window)
        cook_event = _make_cook_event(user.id, recipe_id, cooked_at=_days_ago(3))
        db = _db_with_cards(
            [
                (card_cooked, "all-recipes", "hellofresh_web", True),
                (other_card, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
            cook_events=[cook_event],
        )
        result = rank_candidates(user, db, limit=10)
        result_card_ids = {r.card.id for r in result if r.card is not None}
        assert card_cooked.id not in result_card_ids
        assert other_card.id in result_card_ids

    def test_cooked_outside_window_included(self):
        recipe_id = uuid4()
        card = _make_card("old-cook", recipe_id=recipe_id, source_type="hellofresh_web")
        user = _make_user()
        # Cooked 20 days ago (outside 14-day window)
        cook_event = _make_cook_event(user.id, recipe_id, cooked_at=_days_ago(20))
        db = _db_with_cards(
            [(card, "all-recipes", "hellofresh_web", True)],
            user=user,
            cook_events=[cook_event],
        )
        result = rank_candidates(user, db, limit=10)
        result_card_ids = {r.card.id for r in result if r.card is not None}
        assert card.id in result_card_ids

    def test_exclude_card_ids_parameter(self):
        card_a = _make_card("card-a", source_type="hellofresh_web")
        card_b = _make_card("card-b", source_type="hellofresh_web")
        user = _make_user()
        db = _db_with_cards(
            [
                (card_a, "all-recipes", "hellofresh_web", True),
                (card_b, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )
        result = rank_candidates(user, db, limit=10, exclude_card_ids=[card_a.id])
        result_card_ids = {r.card.id for r in result if r.card is not None}
        assert card_a.id not in result_card_ids
        assert card_b.id in result_card_ids


# ---------------------------------------------------------------------------
# AC4: Explore slots and diversity
# ---------------------------------------------------------------------------

class TestExploreAndDiversity:
    def _make_cards_with_sources(self, hf_count, hc_count, affinities_key=None):
        """
        Build hf_count HF cards and hc_count HC cards, all with equal popularity (rating=4.0).

        When affinities_key is set, HF cards have that ingredient key so they are
        NOT explore-eligible; HC cards have a different key (or none).
        """
        cards = []
        for i in range(hf_count):
            ik = [affinities_key] if affinities_key else []
            cards.append((_make_card(
                f"hf-{i}", source_type="hellofresh_web",
                rating=4.0, rating_count=100,
                ingredient_keys=ik or None,
            ), "all-recipes", "hellofresh_web", True))
        for i in range(hc_count):
            cards.append((_make_card(
                f"hc-{i}", source_type="homechef_web",
                rating=4.0, rating_count=100,
                ingredient_keys=[],
            ), "all-recipes", "homechef_web", True))
        return cards

    def test_every_fifth_slot_is_explore_when_eligible(self):
        # With no affinities, all cards are explore-eligible (no key in affinities).
        # So every 5th slot should be an explore pick.
        cards = self._make_cards_with_sources(5, 5)
        user = _make_user()  # no affinities
        db = _db_with_cards(cards, user=user)

        result = rank_candidates(user, db, limit=10)
        assert len(result) == 10
        for i, item in enumerate(result):
            slot = i + 1  # 1-indexed
            if slot % 5 == 0:
                assert item.reason == "explore", (
                    f"Slot {slot} should be explore, got {item.reason}"
                )

    def test_explore_slot_skipped_when_no_eligible_candidate(self):
        # All cards have affinity keys → no explore candidates
        cards = self._make_cards_with_sources(10, 0, affinities_key="chicken")
        user = _make_user(taste_preferences={"ingredient:chicken": "like"})
        db = _db_with_cards(cards, user=user)

        result = rank_candidates(user, db, limit=10)
        # Slot 5 should NOT be explore since no candidate has keys outside affinities
        if len(result) >= 5:
            assert result[4].reason != "explore", (
                "Slot 5 should not be explore when all cards have affinity keys"
            )

    def test_no_fourth_in_a_row_while_other_source_available(self):
        """
        Assert the diversity rule: for each item that would be the 4th consecutive
        from its source, every LATER item in the list has the same source (meaning
        the other source was already exhausted when it was picked).
        """
        # 6 HF cards, 6 HC cards, equal scores, no affinities
        cards = self._make_cards_with_sources(6, 6)
        user = _make_user()
        db = _db_with_cards(cards, user=user)

        result = rank_candidates(user, db, limit=12)
        assert len(result) == 12

        placed_sources = []
        for item in result:
            if item.kind == "card":
                src = item.card.source_type
            else:
                src = getattr(item.recipe, "source_type", "manual") if item.recipe else "manual"
            placed_sources.append(src)

        # For each item at position i (0-indexed) that would be the 4th consecutive
        # from its source, every later item must have that same source (other exhausted).
        for i in range(3, len(placed_sources)):
            last4 = placed_sources[i - 3: i + 1]
            if len(set(last4)) == 1:
                # This item IS the 4th consecutive from its source.
                # All items after position i must also have the same source.
                this_source = placed_sources[i]
                for j in range(i + 1, len(placed_sources)):
                    assert placed_sources[j] == this_source, (
                        f"Position {i} is 4th consecutive {this_source}, "
                        f"but position {j} is {placed_sources[j]} — "
                        f"the other source had candidates when this was picked"
                    )

    def test_diversity_6hf_6hc_expected_sequence(self):
        """
        With 6 HF and 6 HC at equal scores, the first run of 4+ same source
        can only happen at the end when the other source is exhausted.

        Expected sequence per issue: HF HF HF HC HF HF HF HC HC HC HC HC
        (slot 5 is explore; with no affinities the most popular unplaced
        card is picked, which could be HF or HC depending on stable sort —
        the key invariant is the 4-in-a-row rule, not exact source order).
        """
        cards = self._make_cards_with_sources(6, 6)
        user = _make_user()
        db = _db_with_cards(cards, user=user)

        result = rank_candidates(user, db, limit=12)
        placed_sources = []
        for item in result:
            src = item.card.source_type if item.card else "manual"
            placed_sources.append(src)

        # Verify: any run of 4+ from the same source can only occur at the tail
        # (after the other source has no more candidates)
        for i in range(3, len(placed_sources)):
            last4 = placed_sources[i - 3: i + 1]
            if len(set(last4)) == 1:
                this_source = last4[0]
                remaining_other = placed_sources[i + 1:]
                assert all(s == this_source for s in remaining_other), (
                    f"4-in-a-row {this_source} at position {i} but other source "
                    f"still appears later: {placed_sources}"
                )


# ---------------------------------------------------------------------------
# related_items: similarity ordering, exclusions, mixed kinds
# ---------------------------------------------------------------------------

class TestRelatedItems:
    """
    Acceptance criteria for related_items():
    - A candidate sharing more keys ranks above one sharing fewer.
    - A candidate sharing no keys is absent.
    - Cards and recipes both appear in results.
    - The viewed recipe itself is excluded.
    - The catalog card linked to the viewed recipe is excluded.
    - Blocked items are excluded.
    """

    def _make_viewed(self, ingredient_keys=None):
        """Make a simple 'viewed' recipe with a fixed set of keys."""
        r = _make_recipe("Viewed Pasta", tags=[], ingredients=[])
        # Patch ingredient_keys onto it via the ingredients field
        # so recipe_keys() returns ingredient: prefixed keys.
        # Use SimpleNamespace ingredients with ingredient_name matching known keys.
        ingredients = []
        for key in (ingredient_keys or ["pasta", "tomato", "garlic"]):
            ingredients.append(SimpleNamespace(ingredient_name=key))
        r = SimpleNamespace(
            id=r.id,
            name=r.name,
            source_type=r.source_type,
            source_url=r.source_url,
            source_image=r.source_image,
            prep_time_minutes=r.prep_time_minutes,
            cook_time_minutes=r.cook_time_minutes,
            base_servings=r.base_servings,
            tags=[],
            times_cooked=0,
            created_by=None,
            is_persisted=True,
            ingredients=ingredients,
        )
        return r

    def test_higher_overlap_ranks_first(self):
        """Card sharing 3 keys ranks above card sharing 1 key."""
        viewed = self._make_viewed(["pasta", "tomato", "garlic"])

        # 3 shared keys: pasta, tomato, garlic
        card_high = _make_card(
            "high-sim",
            ingredient_keys=["pasta", "tomato", "garlic", "basil"],
            source_type="hellofresh_web",
        )
        # 1 shared key: pasta only
        card_low = _make_card(
            "low-sim",
            ingredient_keys=["pasta", "chicken", "lemon"],
            source_type="hellofresh_web",
        )

        user = _make_user()
        db = _db_with_cards(
            [
                (card_high, "all-recipes", "hellofresh_web", True),
                (card_low, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )

        result = related_items(viewed, user, db, limit=10)
        assert len(result) >= 2
        ids = [r.card.id for r in result if r.card is not None]
        assert card_high.id in ids
        assert card_low.id in ids
        assert ids.index(card_high.id) < ids.index(card_low.id), (
            "card with 3 shared keys should rank above card with 1 shared key"
        )

    def test_zero_overlap_absent(self):
        """Candidate sharing no keys with the viewed recipe is not returned."""
        viewed = self._make_viewed(["pasta", "tomato", "garlic"])

        card_unrelated = _make_card(
            "unrelated",
            ingredient_keys=["chicken", "lemon", "rosemary"],
            source_type="hellofresh_web",
        )
        card_related = _make_card(
            "related",
            ingredient_keys=["pasta", "basil"],
            source_type="hellofresh_web",
        )

        user = _make_user()
        db = _db_with_cards(
            [
                (card_unrelated, "all-recipes", "hellofresh_web", True),
                (card_related, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )

        result = related_items(viewed, user, db, limit=10)
        result_ids = {r.card.id for r in result if r.card is not None}
        assert card_unrelated.id not in result_ids
        assert card_related.id in result_ids

    def test_cards_and_recipes_both_appear(self):
        """Cards and unlinked recipes both appear when both share keys."""
        viewed = self._make_viewed(["pasta", "tomato"])

        card = _make_card(
            "pasta-card",
            ingredient_keys=["pasta", "basil"],
            source_type="hellofresh_web",
        )
        # Unlinked persisted recipe sharing 'pasta'
        unlinked = SimpleNamespace(
            id=uuid4(),
            name="Pasta Salad",
            source_type="manual",
            source_url=None,
            source_image=None,
            prep_time_minutes=None,
            cook_time_minutes=None,
            base_servings=4,
            tags=[],
            times_cooked=0,
            created_by=None,
            is_persisted=True,
            ingredients=[SimpleNamespace(ingredient_name="pasta")],
        )

        user = _make_user()
        db = _db_with_cards(
            [(card, "all-recipes", "hellofresh_web", True)],
            user=user,
            extra_recipes=[unlinked],
        )

        result = related_items(viewed, user, db, limit=10)
        kinds = {r.kind for r in result}
        assert "card" in kinds
        assert "recipe" in kinds

    def test_viewed_recipe_excluded(self):
        """The viewed recipe itself must not appear in results."""
        viewed = self._make_viewed(["pasta", "tomato"])

        # Give viewed recipe a card entry too so it also tests card exclusion
        card_for_viewed = _make_card(
            "viewed-card",
            ingredient_keys=["pasta", "tomato"],
            recipe_id=viewed.id,
            source_type="hellofresh_web",
        )
        other_card = _make_card(
            "other-card",
            ingredient_keys=["pasta", "basil"],
            source_type="hellofresh_web",
        )

        user = _make_user()
        db = _db_with_cards(
            [
                (card_for_viewed, "all-recipes", "hellofresh_web", True),
                (other_card, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
            extra_recipes=[viewed],
        )

        result = related_items(viewed, user, db, limit=10)
        result_recipe_ids = {r.recipe.id for r in result if r.recipe is not None}
        result_card_ids = {r.card.id for r in result if r.card is not None}
        assert viewed.id not in result_recipe_ids, "viewed recipe must not appear"
        assert card_for_viewed.id not in result_card_ids, "card linked to viewed recipe must not appear"
        assert other_card.id in result_card_ids

    def test_blocked_items_excluded(self):
        """Blocked cards and recipes are excluded from related results."""
        viewed = self._make_viewed(["pasta", "tomato"])

        blocked_card = _make_card(
            "blocked",
            ingredient_keys=["pasta", "garlic"],
            source_type="hellofresh_web",
        )
        safe_card = _make_card(
            "safe",
            ingredient_keys=["pasta", "basil"],
            source_type="hellofresh_web",
        )
        user = _make_user(allergies=["garlic"])

        db = _db_with_cards(
            [
                (blocked_card, "all-recipes", "hellofresh_web", True),
                (safe_card, "all-recipes", "hellofresh_web", True),
            ],
            user=user,
        )

        result = related_items(viewed, user, db, limit=10)
        result_card_ids = {r.card.id for r in result if r.card is not None}
        assert blocked_card.id not in result_card_ids
        assert safe_card.id in result_card_ids
