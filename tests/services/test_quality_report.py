"""
Tests for quality_report.extraction_report() and quality_report.recommendation_report().

Acceptance criteria covered:
- extraction: coverage numbers correct on a fixture DB
- recommendation: source-skew, low-variety, ingredient-dominance warnings fire
  on fixtures built to trigger each; stay quiet on a balanced fixture
- no writes: session has no new/dirty objects after both calls
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.services.quality_report import (
    extraction_report,
    recommendation_report,
    ExtractionReport,
    RecommendationReport,
)


# ---------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------

def _card(
    source_type="src_a",
    image_url="https://img.example.com/x.jpg",
    prep_time_minutes=30,
    ingredient_keys=None,
    name="Card",
):
    return SimpleNamespace(
        id=uuid4(),
        source_type=source_type,
        name=name,
        headline=None,
        image_url=image_url,
        prep_time_minutes=prep_time_minutes,
        ingredient_keys=ingredient_keys,
        rating=None,
        rating_count=None,
        recipe_id=None,
        recipe_url=f"https://example.com/{name}",
        external_id="ext-" + name[:8],
        tags=[],
    )


def _ingredient(recipe_id, name):
    return SimpleNamespace(
        id=uuid4(),
        recipe_id=recipe_id,
        ingredient_name=name,
        quantity=1.0,
        unit="unit",
    )


def _collection(source_type="src_a", slug="main", parent_slug=None):
    return SimpleNamespace(
        id=uuid4(),
        source_type=source_type,
        slug=slug,
        name=slug.replace("-", " ").title(),
        parent_slug=parent_slug,
        url=f"https://example.com/{slug}",
    )


def _user(email="user@test.com", taste_preferences=None, allergies=None):
    return SimpleNamespace(
        id=uuid4(),
        email=email,
        taste_preferences=taste_preferences or {},
        allergies=allergies or [],
    )


# ---------------------------------------------------------------------------
# Minimal mock DB
# ---------------------------------------------------------------------------

class _MockQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *conditions):
        items = self._items
        for cond in conditions:
            try:
                col_key = getattr(getattr(cond, "left", None), "key", None)
                right = getattr(cond, "right", None)
                if col_key and right is not None:
                    if type(right).__name__ == "Null":
                        op_name = getattr(getattr(cond, "operator", None), "__name__", "")
                        if op_name == "is_":
                            items = [i for i in items if getattr(i, col_key, "SENTINEL") is None]
                    elif hasattr(right, "value"):
                        val = right.value
                        op_name = getattr(getattr(cond, "operator", None), "__name__", "eq")
                        if isinstance(val, (list, tuple, set, frozenset)):
                            if op_name == "in_op":
                                items = [i for i in items if getattr(i, col_key, None) in val]
                            elif op_name == "not_in_op":
                                items = [i for i in items if getattr(i, col_key, None) not in val]
                        elif op_name == "eq":
                            items = [i for i in items if getattr(i, col_key, None) == val]
                        elif op_name == "ne":
                            items = [i for i in items if getattr(i, col_key, None) != val]
            except Exception:
                pass
        self._items = items
        return self

    def join(self, *args, **kwargs):
        return self

    def options(self, *args):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def count(self):
        return len(self._items)


class _CardSlugQuery:
    """Returns (card, slug) pairs for the multi-join query in rank_candidates."""

    def __init__(self, collection_cards):
        # collection_cards: list of (card, slug, collection_id)
        self._rows = list(collection_cards)

    def join(self, *args, **kwargs):
        return self

    def filter(self, *conditions):
        rows = self._rows
        for cond in conditions:
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
        return [(row[0], row[1]) for row in self._rows]


class _MockDB:
    def __init__(
        self,
        cards=None,
        ingredients=None,
        collections=None,
        collection_cards=None,
        cook_events=None,
        relations=None,
        views=None,
        recipes=None,
        users=None,
    ):
        self._cards = cards or []
        self._ingredients = ingredients or []
        self._collections = collections or []
        self._collection_cards = collection_cards or []  # (card, slug, collection_id)
        self._cook_events = cook_events or []
        self._relations = relations or []
        self._views = views or []
        self._recipes = recipes or {}  # id -> recipe
        self._users = users or []
        # Track any objects added during the session (should stay empty).
        self._added: list = []
        self._dirty: list = []

    def query(self, *models):
        from src.db.models.source_catalog import (
            SourceCollection,
            SourceCollectionCard,
            SourceRecipeCard,
        )
        from src.db.models.recipe_ingredient import RecipeIngredient
        from src.db.models.user_cook_event import UserCookEvent
        from src.db.models.user_recipe import UserRecipeRelation
        from src.db.models.user_recipe_view import UserRecipeView
        from src.db.models.recipe import Recipe
        from src.db.models.user import User

        model = models[0]
        if model is SourceRecipeCard:
            return _CardSlugQuery(self._collection_cards)
        if model is RecipeIngredient:
            return _MockQuery(self._ingredients)
        if model is SourceCollection:
            return _MockQuery(self._collections)
        if model is UserCookEvent:
            return _MockQuery(self._cook_events)
        if model is UserRecipeRelation:
            return _MockQuery(self._relations)
        if model is UserRecipeView:
            return _MockQuery(self._views)
        if model is Recipe:
            return _MockQuery(list(self._recipes.values()))
        if model is User:
            return _MockQuery(self._users)
        return _MockQuery([])

    def get(self, model, id_):
        from src.db.models.recipe import Recipe
        from src.db.models.user import User

        if model is Recipe:
            return self._recipes.get(id_)
        if model is User:
            for u in self._users:
                if u.id == id_:
                    return u
        return None

    def add(self, obj):
        self._added.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def refresh(self, obj):
        pass

    def close(self):
        pass

    def new_object_count(self):
        return len(self._added)


def _build_db(cards_per_source, ingredient_names=None, users=None):
    """
    Build a _MockDB from a dict of source_type -> list of card namespaces.

    Creates one top-level SourceCollection per source_type with slug "main".
    """
    all_cards = []
    collections = []
    collection_cards = []

    for source_type, cards in cards_per_source.items():
        coll = _collection(source_type=source_type)
        collections.append(coll)
        for card in cards:
            all_cards.append(card)
            collection_cards.append((card, "main", coll.id))

    ingredients = []
    for name in (ingredient_names or []):
        ingredients.append(SimpleNamespace(
            id=uuid4(),
            recipe_id=uuid4(),
            ingredient_name=name,
            quantity=1.0,
            unit="unit",
        ))

    return _MockDB(
        cards=all_cards,
        ingredients=ingredients,
        collections=collections,
        collection_cards=collection_cards,
        users=users or [],
    )


# ---------------------------------------------------------------------------
# AC1 extraction: coverage numbers correct
# ---------------------------------------------------------------------------

class TestExtraction:
    def test_coverage_percentages_correct(self):
        """4 cards: 3 with image, 2 with prep_time, 2 with ingredient_keys, 1 with 3+ keys."""
        cards = [
            _card(image_url="https://img.example.com/a.jpg", prep_time_minutes=20,
                  ingredient_keys=["chicken", "garlic", "onion"], name="Card1"),
            _card(image_url="https://img.example.com/b.jpg", prep_time_minutes=None,
                  ingredient_keys=["beef"], name="Card2"),
            _card(image_url="https://img.example.com/c.jpg", prep_time_minutes=30,
                  ingredient_keys=None, name="Card3"),
            _card(image_url=None, prep_time_minutes=None,
                  ingredient_keys=None, name="Card4"),
        ]
        db = _build_db({"src_a": cards})
        report = extraction_report(db)

        assert isinstance(report, ExtractionReport)
        assert len(report.sources) == 1
        s = report.sources[0]
        assert s.source_type == "src_a"
        assert s.card_count == 4
        assert abs(s.pct_image - 75.0) < 0.1       # 3/4
        assert abs(s.pct_prep_time - 50.0) < 0.1   # 2/4
        assert abs(s.pct_ingredient_keys - 50.0) < 0.1  # 2/4
        assert abs(s.pct_3plus_keys - 25.0) < 0.1  # 1/4

    def test_multiple_sources_reported_separately(self):
        cards_a = [_card(source_type="src_a", image_url="x", prep_time_minutes=10, ingredient_keys=["beef", "garlic", "onion"])]
        cards_b = [
            _card(source_type="src_b", image_url=None, prep_time_minutes=None, ingredient_keys=None),
            _card(source_type="src_b", image_url=None, prep_time_minutes=None, ingredient_keys=None),
        ]
        db = _build_db({"src_a": cards_a, "src_b": cards_b})
        report = extraction_report(db)

        source_map = {s.source_type: s for s in report.sources}
        assert "src_a" in source_map
        assert "src_b" in source_map
        assert source_map["src_a"].card_count == 1
        assert source_map["src_b"].card_count == 2

    def test_unmapped_words_appear_in_report(self):
        """
        Ingredient names containing unknown words surface in top_unmapped_words.
        'zarble' is not in the INGREDIENTS vocabulary and should appear.
        """
        cards = [_card(ingredient_keys=["chicken"])]
        db = _build_db({"src_a": cards}, ingredient_names=[
            "zarble powder",
            "zarble sauce",
            "chicken breast",
        ])
        report = extraction_report(db)
        words = [w for w, _ in report.sources[0].top_unmapped_words]
        assert "zarble" in words

    def test_known_ingredient_word_not_in_unmapped(self):
        """'chicken' resolves to a key → it must NOT appear in unmapped words."""
        db = _build_db({"src_a": [_card()]}, ingredient_names=["chicken breast", "chicken thigh"])
        report = extraction_report(db)
        words = [w for w, _ in report.sources[0].top_unmapped_words]
        assert "chicken" not in words

    def test_low_coverage_warning_fires(self):
        """A source with 0% image coverage triggers a warning."""
        cards = [
            _card(image_url=None, prep_time_minutes=None, ingredient_keys=None)
            for _ in range(5)
        ]
        db = _build_db({"src_a": cards})
        report = extraction_report(db)
        s = report.sources[0]
        warning_text = " ".join(s.warnings)
        assert "image_url" in warning_text

    def test_full_coverage_no_warnings(self):
        """A source where every field is populated has no warnings."""
        cards = [
            _card(image_url="https://img.example.com/x.jpg", prep_time_minutes=20,
                  ingredient_keys=["chicken", "garlic", "onion", "tomato"])
            for _ in range(5)
        ]
        db = _build_db({"src_a": cards})
        report = extraction_report(db)
        assert report.sources[0].warnings == []

    def test_empty_source_zero_coverage(self):
        """Empty source list produces no source entries (not a crash)."""
        db = _build_db({})
        report = extraction_report(db)
        assert report.sources == []


# ---------------------------------------------------------------------------
# AC2 recommendation: warnings fire / stay quiet
# ---------------------------------------------------------------------------

def _card_for_rec(source_type, cuisine_tag=None, ingredient_key=None, rating=4.5, name=None):
    """Make a card suitable for recommendation fixture with preset cuisine/ingredient."""
    # Encode cuisine in tags and ingredient in ingredient_keys
    tags_list = []
    if cuisine_tag:
        tags_list.append(cuisine_tag)
    ingredient_keys_list = None
    if ingredient_key:
        ingredient_keys_list = [ingredient_key]
    card = SimpleNamespace(
        id=uuid4(),
        source_type=source_type,
        name=name or f"{source_type}-{cuisine_tag or ''}-{ingredient_key or ''}",
        headline=None,
        image_url="https://img.example.com/x.jpg",
        prep_time_minutes=20,
        ingredient_keys=ingredient_keys_list,
        rating=rating,
        rating_count=200,
        recipe_id=None,
        recipe_url=f"https://example.com/{uuid4()}",
        external_id=str(uuid4())[:8],
        tags=tags_list,
    )
    return card


def _build_rec_db(cards_per_source, users=None):
    """Build a DB for recommendation tests with one top-level collection per source."""
    return _build_db(cards_per_source, users=users)


class TestRecommendation:
    def test_source_skew_warning_fires(self):
        """
        One source has 100% of the top 20 while another source has 20+ candidates →
        source-skew warning must appear.
        """
        # 25 cards from src_a (all rated 5.0 → dominate top 20)
        src_a_cards = [
            _card_for_rec("src_a", cuisine_tag="Italian", ingredient_key="chicken",
                          rating=5.0, name=f"a{i}")
            for i in range(25)
        ]
        # 25 cards from src_b (rated low so they fall outside top 20)
        src_b_cards = [
            _card_for_rec("src_b", cuisine_tag="Mexican", ingredient_key="beef",
                          rating=1.0, name=f"b{i}")
            for i in range(25)
        ]
        user = _user()
        db = _build_rec_db({"src_a": src_a_cards, "src_b": src_b_cards}, users=[user])
        report = recommendation_report(user, db)

        # Find the stats for the real user
        real_stats = next((s for s in report.users if s.label == user.email), None)
        assert real_stats is not None
        warning_text = " ".join(real_stats.warnings)
        assert "source skew" in warning_text or "skew" in warning_text.lower()

    def test_source_skew_quiet_when_balanced(self):
        """Equal split between two sources → no source-skew warning."""
        src_a_cards = [
            _card_for_rec("src_a", cuisine_tag="Italian", ingredient_key="chicken",
                          rating=4.5, name=f"a{i}")
            for i in range(10)
        ]
        src_b_cards = [
            _card_for_rec("src_b", cuisine_tag="Mexican", ingredient_key="beef",
                          rating=4.5, name=f"b{i}")
            for i in range(10)
        ]
        user = _user()
        db = _build_rec_db({"src_a": src_a_cards, "src_b": src_b_cards}, users=[user])
        report = recommendation_report(user, db)

        real_stats = next((s for s in report.users if s.label == user.email), None)
        assert real_stats is not None
        for w in real_stats.warnings:
            assert "skew" not in w.lower()

    def test_low_variety_warning_fires(self):
        """All top 20 from one cuisine → fewer-than-3-cuisines warning."""
        # 25 cards, all Italian
        cards = [
            _card_for_rec("src_a", cuisine_tag="Italian", ingredient_key="chicken",
                          rating=4.5, name=f"card{i}")
            for i in range(25)
        ]
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        report = recommendation_report(user, db)

        real_stats = next((s for s in report.users if s.label == user.email), None)
        assert real_stats is not None
        warning_text = " ".join(real_stats.warnings)
        assert "cuisine" in warning_text.lower()

    def test_low_variety_quiet_when_diverse(self):
        """3+ distinct cuisines in top 20 → no low-variety warning."""
        cuisines = ["Italian", "Mexican", "Asian", "Indian", "Mediterranean"]
        cards = []
        for i, cuisine in enumerate(cuisines):
            for _ in range(5):
                cards.append(
                    _card_for_rec("src_a", cuisine_tag=cuisine,
                                  ingredient_key="chicken", rating=4.5,
                                  name=f"card-{cuisine}-{_}")
                )
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        report = recommendation_report(user, db)

        real_stats = next((s for s in report.users if s.label == user.email), None)
        assert real_stats is not None
        for w in real_stats.warnings:
            assert "cuisine" not in w.lower()

    def test_ingredient_dominance_warning_fires(self):
        """Single ingredient in >40% of top 20 → dominance warning."""
        # 20 chicken cards + 5 beef cards; chicken will dominate
        cards = [
            _card_for_rec("src_a", cuisine_tag="Italian", ingredient_key="chicken",
                          rating=5.0, name=f"chicken-{i}")
            for i in range(20)
        ]
        cards += [
            _card_for_rec("src_a", cuisine_tag="Mexican", ingredient_key="beef",
                          rating=1.0, name=f"beef-{i}")
            for i in range(5)
        ]
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        report = recommendation_report(user, db)

        real_stats = next((s for s in report.users if s.label == user.email), None)
        assert real_stats is not None
        warning_text = " ".join(real_stats.warnings)
        assert "ingredient dominance" in warning_text.lower() or "dominance" in warning_text.lower()

    def test_ingredient_dominance_quiet_when_balanced(self):
        """Different ingredient per card → no dominance warning."""
        ing_keys = ["chicken", "beef", "salmon", "tofu", "pork",
                    "shrimp", "lamb", "tuna", "turkey", "duck",
                    "chicken", "beef", "salmon", "tofu", "pork",
                    "shrimp", "lamb", "tuna", "turkey", "duck",
                    "crab", "lobster", "rice", "pasta", "beans-legumes"]
        cards = [
            _card_for_rec("src_a", cuisine_tag=f"cuisine{i % 5}",
                          ingredient_key=k, rating=4.5, name=f"card{i}")
            for i, k in enumerate(ing_keys)
        ]
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        report = recommendation_report(user, db)

        real_stats = next((s for s in report.users if s.label == user.email), None)
        assert real_stats is not None
        for w in real_stats.warnings:
            assert "dominance" not in w.lower()

    def test_synthetic_user_always_present(self):
        """recommendation_report always includes a 'synthetic' user entry."""
        cards = [_card_for_rec("src_a", cuisine_tag="Italian", name=f"card{i}") for i in range(5)]
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        report = recommendation_report(user, db)

        labels = [s.label for s in report.users]
        assert "synthetic" in labels

    def test_top20_does_not_exceed_limit(self):
        """top20 list never has more than 20 items."""
        cards = [_card_for_rec("src_a", cuisine_tag=f"cuisine{i}", name=f"card{i}") for i in range(30)]
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        report = recommendation_report(user, db)

        for stats in report.users:
            assert len(stats.top20) <= 20


# ---------------------------------------------------------------------------
# AC3: no writes — session has no new or dirty objects after both calls
# ---------------------------------------------------------------------------

class TestNoWrites:
    def test_extraction_makes_no_writes(self):
        cards = [_card(ingredient_keys=["chicken", "garlic"])]
        db = _build_db({"src_a": cards}, ingredient_names=["chicken breast"])
        extraction_report(db)
        assert db.new_object_count() == 0

    def test_recommendation_makes_no_writes(self):
        cards = [
            _card_for_rec("src_a", cuisine_tag="Italian", ingredient_key="chicken",
                          rating=4.5, name=f"card{i}")
            for i in range(5)
        ]
        user = _user()
        db = _build_rec_db({"src_a": cards}, users=[user])
        recommendation_report(user, db)
        assert db.new_object_count() == 0

    def test_both_calls_together_make_no_writes(self):
        cards = [
            _card_for_rec("src_a", cuisine_tag="Italian", ingredient_key="chicken",
                          rating=4.5, name=f"card{i}")
            for i in range(5)
        ]
        user = _user()
        db = _build_db(
            {"src_a": cards},
            ingredient_names=["chicken breast"],
            users=[user],
        )
        # Wire up collection_cards for rec report to work
        coll = _collection(source_type="src_a")
        db._collections = [coll]
        db._collection_cards = [(c, "main", coll.id) for c in cards]

        extraction_report(db)
        recommendation_report(user, db)
        assert db.new_object_count() == 0
