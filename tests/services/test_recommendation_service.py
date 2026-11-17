"""Tests for the recommendation ranking service."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db import models
from src.db.database import Base, get_db
from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.db.models.user import User, UserRole
from src.db.models.user_cook_event import UserCookEvent
from src.services.auth_service import hash_password
from src.services.recommendation_service import rank_candidates

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    _ = models
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid4(),
        email="rec@example.com",
        hashed_password=hash_password("password123"),
        name="Rec User",
        role=UserRole.member.value,
        taste_preferences={},
        allergies=[],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_collection(db, source_type="hellofresh_web", slug="all-recipes", parent_slug=None):
    coll = SourceCollection(
        id=uuid4(),
        source_type=source_type,
        slug=slug,
        name=slug,
        url=f"https://example.com/{slug}",
        parent_slug=parent_slug,
    )
    db.add(coll)
    db.flush()
    return coll


def _add_card(db, coll, name="Chicken Stir Fry", source_type="hellofresh_web",
              rating=4.0, rating_count=100, ingredient_keys=None, recipe=None):
    card = SourceRecipeCard(
        id=uuid4(),
        source_type=source_type,
        external_id=str(uuid4()),
        name=name,
        recipe_url=f"https://example.com/{uuid4()}",
        rating=rating,
        rating_count=rating_count,
        ingredient_keys=ingredient_keys,
        recipe_id=recipe.id if recipe else None,
    )
    db.add(card)
    db.flush()
    link = SourceCollectionCard(collection_id=coll.id, card_id=card.id, position=0)
    db.add(link)
    db.flush()
    if recipe:
        card.recipe_rel = recipe
    return card


def _add_recipe(db, name="Imported Recipe", source_type="url_import",
                tags=None, ingredient_names=None):
    recipe = Recipe(
        id=uuid4(),
        name=name,
        source_type=source_type,
        is_persisted=True,
        times_cooked=0,
        tags=tags or [],
        steps=[],
    )
    db.add(recipe)
    db.flush()
    if ingredient_names:
        from src.db.models.recipe_ingredient import RecipeIngredient
        for ing_name in ingredient_names:
            db.add(RecipeIngredient(
                id=uuid4(), recipe_id=recipe.id,
                ingredient_name=ing_name, quantity=1.0, unit="piece",
            ))
        db.flush()
    return recipe


def _cook_event(db, user, recipe, cooked_at=None):
    ev = UserCookEvent(
        id=uuid4(),
        user_id=user.id,
        recipe_id=recipe.id,
        cooked_at=cooked_at or datetime.now(timezone.utc),
    )
    db.add(ev)
    db.flush()
    return ev


# ---------------------------------------------------------------------------
# Cold start: no history → popularity-ordered cards, reason "popular"
# ---------------------------------------------------------------------------

class TestColdStart:
    def test_cold_start_cards_ordered_by_popularity(self, db_session, test_user):
        """With no history, cards are ordered by popularity and reason is popular."""
        db_session.commit()
        coll = _add_collection(db_session)
        # card_low has lower rating/count
        card_low = _add_card(db_session, coll, name="Low Card", rating=3.0, rating_count=10)
        card_high = _add_card(db_session, coll, name="High Card", rating=4.5, rating_count=500)
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10)

        assert len(result) >= 2
        reasons = {r.reason for r in result}
        # In cold start no affinities, reason must be "popular" or "explore"
        assert "popular" in reasons or all(r.reason in ("popular", "explore") for r in result)
        # High card should rank above low card
        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert names.index("High Card") < names.index("Low Card")

    def test_cold_start_all_reasons_popular_or_explore(self, db_session, test_user):
        """Cold start: no taste reasons."""
        db_session.commit()
        coll = _add_collection(db_session)
        for i in range(6):
            _add_card(db_session, coll, name=f"Card {i}", rating=3.0 + i * 0.1, rating_count=100)
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=6)
        for item in result:
            assert item.reason in ("popular", "explore")


# ---------------------------------------------------------------------------
# With history: taste outranks popularity
# ---------------------------------------------------------------------------

class TestWithHistory:
    def test_loved_key_outranks_more_popular_card(self, db_session, test_user):
        """A card matching a loved ingredient key beats a more popular unrelated card."""
        # Give the user a "love" preference for chicken
        test_user.taste_preferences = {"ingredient:chicken": "love"}
        db_session.commit()

        coll = _add_collection(db_session)
        # Popular card with no matching key
        card_popular = _add_card(
            db_session, coll, name="Beef Burger",
            rating=4.8, rating_count=5000, ingredient_keys=["beef"],
        )
        # Less popular card but matches user's loved key
        card_taste = _add_card(
            db_session, coll, name="Chicken Stir Fry",
            rating=3.5, rating_count=50, ingredient_keys=["chicken"],
        )
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10)

        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert names.index("Chicken Stir Fry") < names.index("Beef Burger")

    def test_taste_reason_set_when_affinities_present(self, db_session, test_user):
        """When a user has history, non-explore items get reason=taste."""
        test_user.taste_preferences = {"ingredient:chicken": "love"}
        db_session.commit()

        coll = _add_collection(db_session)
        _add_card(db_session, coll, name="Chicken Dish", rating=4.0, rating_count=100,
                  ingredient_keys=["chicken"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10)
        chicken = next(r for r in result if r.card and r.card.name == "Chicken Dish")
        assert chicken.reason == "taste"


# ---------------------------------------------------------------------------
# Blocking and recency exclusion
# ---------------------------------------------------------------------------

class TestBlockingAndRecency:
    def test_blocked_card_absent(self, db_session, test_user):
        """A card whose key is marked never is excluded."""
        test_user.taste_preferences = {"ingredient:pork": "never"}
        db_session.commit()

        coll = _add_collection(db_session)
        _add_card(db_session, coll, name="Pork Chop", ingredient_keys=["pork"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=20)
        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert "Pork Chop" not in names

    def test_blocked_recipe_absent(self, db_session, test_user):
        """An unlinked recipe matching a never preference is excluded."""
        test_user.taste_preferences = {"ingredient:pork": "never"}
        db_session.commit()

        _add_recipe(db_session, name="Pork Ramen", ingredient_names=["pork loin"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=20)
        names = [r.recipe.name if r.recipe else r.card.name for r in result]
        assert "Pork Ramen" not in names

    def test_recently_cooked_card_absent(self, db_session, test_user):
        """A card whose linked recipe was cooked 3 days ago is excluded."""
        db_session.commit()
        recipe = _add_recipe(db_session, name="Cooked Recipe")
        coll = _add_collection(db_session)
        _add_card(db_session, coll, name="Card for Cooked", recipe=recipe)
        _cook_event(db_session, test_user, recipe,
                    cooked_at=datetime.now(timezone.utc) - timedelta(days=3))
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=20)
        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert "Card for Cooked" not in names

    def test_recently_cooked_recipe_absent(self, db_session, test_user):
        """An unlinked recipe cooked 3 days ago is excluded."""
        db_session.commit()
        recipe = _add_recipe(db_session, name="Cooked Unlinked")
        _cook_event(db_session, test_user, recipe,
                    cooked_at=datetime.now(timezone.utc) - timedelta(days=3))
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=20)
        names = [r.recipe.name if r.recipe else r.card.name for r in result]
        assert "Cooked Unlinked" not in names

    def test_cooked_15_days_ago_is_included(self, db_session, test_user):
        """A recipe cooked 15 days ago (> 14-day window) reappears."""
        db_session.commit()
        recipe = _add_recipe(db_session, name="Old Cook")
        coll = _add_collection(db_session)
        _add_card(db_session, coll, name="Card Old Cook", recipe=recipe)
        _cook_event(db_session, test_user, recipe,
                    cooked_at=datetime.now(timezone.utc) - timedelta(days=15))
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=20)
        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert "Card Old Cook" in names


# ---------------------------------------------------------------------------
# Exploration and source diversity
# ---------------------------------------------------------------------------

class TestExploreAndDiversity:
    def test_explore_slot_at_index_four(self, db_session, test_user):
        """With affinities, the item at index 4 is an explore pick when one exists."""
        # Love chicken so there are items with matching affinities
        test_user.taste_preferences = {"ingredient:chicken": "love"}
        db_session.commit()

        coll = _add_collection(db_session)
        # 4 cards that match the affinity
        for i in range(4):
            _add_card(db_session, coll, name=f"Chicken Card {i}",
                      rating=4.0, rating_count=100, ingredient_keys=["chicken"])
        # 3 cards with no affinity match (candidates for explore pool)
        _add_card(db_session, coll, name="Explore Card A",
                  rating=4.5, rating_count=200, ingredient_keys=["beef"])
        _add_card(db_session, coll, name="Explore Card B",
                  rating=3.0, rating_count=50, ingredient_keys=["tofu"])
        _add_card(db_session, coll, name="Explore Card C",
                  rating=3.5, rating_count=80, ingredient_keys=["fish"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=6)

        assert len(result) >= 5
        # Index 4 (5th item) must be an explore pick
        assert result[4].reason == "explore"

    def test_explore_slot_skipped_when_pool_empty(self, db_session, test_user):
        """When all candidates share affinity keys, slot 4 falls back to main pool."""
        test_user.taste_preferences = {"ingredient:chicken": "love"}
        db_session.commit()

        coll = _add_collection(db_session)
        for i in range(6):
            _add_card(db_session, coll, name=f"Chicken Only {i}",
                      rating=4.0, rating_count=100, ingredient_keys=["chicken"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=6)
        assert len(result) == 6
        # Slot 4 falls back to main pool — reason is "taste", not "explore"
        assert result[4].reason == "taste"

    def test_no_four_consecutive_same_source(self, db_session, test_user):
        """No 4 consecutive items share a source when two sources have candidates."""
        db_session.commit()
        # Create two top-level collections from different sources
        coll_hf = _add_collection(db_session, source_type="hellofresh_web", slug="hf-top")
        coll_hc = _add_collection(db_session, source_type="homechef_web", slug="hc-top")

        # 6 HF cards and 6 HC cards, all similar scores
        for i in range(6):
            _add_card(db_session, coll_hf, name=f"HF Card {i}",
                      source_type="hellofresh_web", rating=4.0, rating_count=100 + i)
        for i in range(6):
            _add_card(db_session, coll_hc, name=f"HC Card {i}",
                      source_type="homechef_web", rating=4.0, rating_count=100 + i)
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=12)

        # Count max consecutive from the same source
        max_consecutive = 1
        current = 1
        for i in range(1, len(result)):
            prev_src = result[i - 1]._source_type
            curr_src = result[i]._source_type
            if curr_src == prev_src:
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 1

        assert max_consecutive <= 3

    def test_explore_reason_set_on_explore_slot(self, db_session, test_user):
        """Items placed in explore slots carry reason=explore."""
        test_user.taste_preferences = {"ingredient:chicken": "love"}
        db_session.commit()

        coll = _add_collection(db_session)
        for i in range(4):
            _add_card(db_session, coll, name=f"Chicken {i}",
                      rating=4.0, rating_count=100, ingredient_keys=["chicken"])
        _add_card(db_session, coll, name="Beef Explore",
                  rating=4.0, rating_count=120, ingredient_keys=["beef"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=5)
        explore_items = [r for r in result if r.reason == "explore"]
        assert len(explore_items) >= 1

    def test_diversity_and_explore_slot_coexist(self, db_session, test_user):
        """Multi-source: diversity (<=3 consecutive) and explore slot at index 4 both hold."""
        test_user.taste_preferences = {"ingredient:chicken": "love"}
        db_session.commit()

        coll_hf = _add_collection(db_session, source_type="hellofresh_web", slug="hf-top2")
        coll_hc = _add_collection(db_session, source_type="homechef_web", slug="hc-top2")

        # 4 chicken cards per source (match affinity)
        for i in range(4):
            _add_card(db_session, coll_hf, name=f"HF Chicken {i}",
                      source_type="hellofresh_web", rating=4.0, rating_count=100,
                      ingredient_keys=["chicken"])
            _add_card(db_session, coll_hc, name=f"HC Chicken {i}",
                      source_type="homechef_web", rating=4.0, rating_count=100,
                      ingredient_keys=["chicken"])
        # 1 explore card per source (no affinity match)
        _add_card(db_session, coll_hf, name="HF Beef Explore",
                  source_type="hellofresh_web", rating=4.5, rating_count=200,
                  ingredient_keys=["beef"])
        _add_card(db_session, coll_hc, name="HC Beef Explore",
                  source_type="homechef_web", rating=4.5, rating_count=200,
                  ingredient_keys=["beef"])
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10)

        # Explore guarantee: slot 4 is an explore pick
        assert len(result) >= 5
        assert result[4].reason == "explore"

        # Diversity guarantee: no 4 consecutive from same source
        max_consecutive = 1
        current = 1
        for i in range(1, len(result)):
            if result[i]._source_type == result[i - 1]._source_type:
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 1
        assert max_consecutive <= 3


# ---------------------------------------------------------------------------
# Exclude parameters
# ---------------------------------------------------------------------------

class TestExcludeParameters:
    def test_exclude_card_ids(self, db_session, test_user):
        """Cards in exclude_card_ids are absent from the result."""
        db_session.commit()
        coll = _add_collection(db_session)
        card = _add_card(db_session, coll, name="Excluded Card")
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10,
                                  exclude_card_ids=[card.id])
        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert "Excluded Card" not in names

    def test_exclude_recipe_ids(self, db_session, test_user):
        """Recipes in exclude_recipe_ids are absent from the result."""
        db_session.commit()
        recipe = _add_recipe(db_session, name="Excluded Recipe")
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10,
                                  exclude_recipe_ids=[recipe.id])
        names = [r.recipe.name if r.recipe else r.card.name for r in result]
        assert "Excluded Recipe" not in names


# ---------------------------------------------------------------------------
# Subcollection cards not included
# ---------------------------------------------------------------------------

class TestTopLevelOnly:
    def test_subcollection_card_excluded(self, db_session, test_user):
        """Cards only in a subcollection (parent_slug set) are not candidates."""
        db_session.commit()
        # Top-level collection
        parent = _add_collection(db_session, slug="parent-coll")
        # Subcollection (child of parent)
        child = _add_collection(db_session, slug="child-coll", parent_slug="parent-coll")
        # Card only in the child collection
        card_child = _add_card(db_session, child, name="Child Only Card")
        # Card in the parent (top-level) collection
        card_parent = _add_card(db_session, parent, name="Parent Card")
        db_session.commit()

        result = rank_candidates(test_user, db_session, limit=10)
        names = [r.card.name if r.card else r.recipe.name for r in result]
        assert "Parent Card" in names
        assert "Child Only Card" not in names
