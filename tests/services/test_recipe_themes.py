"""Tests for recipe themes: classifying whole lists into theme values."""

from datetime import datetime, timezone
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
from src.routers import themes as themes_router_module
from src.services.auth_service import create_access_token, hash_password
from src.services.recipe_themes import (
    COLLECTION_THEMES,
    HELLOFRESH_COLLECTION_THEMES,
    HELLOFRESH_SOURCE,
    VALUE_LABELS,
    build_themes,
    normalize_tag,
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    _ = models
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _recipe(db, name, tags, source_type="hellofresh_web"):
    db.add(Recipe(id=uuid4(), name=name, source_type=source_type, tags=tags, steps=[]))
    db.commit()


def _collection(db, slug, name, n_cards=0, fetched=False, parent=None):
    coll = SourceCollection(
        source_type="hellofresh_web",
        slug=slug,
        name=name,
        url=f"https://www.hellofresh.com/recipes/{slug}",
        parent_slug=parent,
        last_fetched_at=datetime.now(timezone.utc) if fetched else None,
    )
    db.add(coll)
    db.flush()
    for i in range(n_cards):
        card = SourceRecipeCard(
            source_type="hellofresh_web",
            recipe_url=f"https://www.hellofresh.com/recipes/{slug}-{i}-{'a' * 24}",
            external_id=f"{slug}-{i}",
            name=f"{name} {i}",
            image_url="https://img.hellofresh.com/x.jpg",
        )
        db.add(card)
        db.flush()
        db.add(SourceCollectionCard(collection_id=coll.id, card_id=card.id, position=i))
    db.commit()
    return coll


def _theme(themes, key):
    return next(t for t in themes if t.key == key)


def _value(themes, key, value):
    return next(v for v in _theme(themes, key).values if v.value == value)


class TestVocabulary:
    def test_every_classified_collection_points_at_a_known_value(self):
        for theme, value in HELLOFRESH_COLLECTION_THEMES.values():
            assert value in VALUE_LABELS[theme], (theme, value)

    def test_normalize_tag(self):
        assert normalize_tag("Latin-American") == "latin american"
        assert normalize_tag("Breakfast & Brunch") == "breakfast and brunch"
        assert normalize_tag("  stir_fry ") == "stir fry"


class TestBuildThemes:
    def test_themes_come_back_in_bar_order(self, db_session):
        keys = [t.key for t in build_themes(db_session)]
        assert keys == ["cuisine", "ingredient", "dish", "diet", "meal_type", "source"]

    def test_library_and_collection_are_separate_lists_under_one_value(self, db_session):
        """Italian HelloFresh and your Italian recipes stay two lists, each naming its source."""
        _recipe(db_session, "Flatbread", ["main course", "Italian"])
        _collection(db_session, "italian-recipes", "Italian Recipes", n_cards=3, fetched=True)

        italian = _value(build_themes(db_session), "cuisine", "italian")

        assert italian.label == "Italian"
        assert italian.library_tag == "italian"
        assert italian.library_count == 1
        assert [c.slug for c in italian.collections] == ["italian-recipes"]
        assert italian.collections[0].card_count == 3

    def test_tag_spellings_map_to_one_value(self, db_session):
        _recipe(db_session, "A", ["latin american"])
        _recipe(db_session, "B", ["Latin-American"])

        latin = _value(build_themes(db_session), "cuisine", "latin-american")

        assert latin.match_tags == ["latin american", "latin-american"]
        # The row queries one exact tag, so the count is that tag's count
        assert latin.library_count == 1

    def test_unknown_tags_are_ignored(self, db_session):
        _recipe(db_session, "A", ["weeknight", "family favorite"])
        themes = build_themes(db_session)
        assert all(v.library_count == 0 for t in themes if t.key != "source" for v in t.values)

    def test_fetched_empty_collections_are_left_out_but_unfetched_kept(self, db_session):
        _collection(db_session, "thai-recipes", "Thai Recipes", n_cards=0, fetched=True)
        _collection(db_session, "korean-recipes", "Korean Recipes", n_cards=0, fetched=False)

        cuisine_values = {v.value for v in _theme(build_themes(db_session), "cuisine").values}

        assert "thai" not in cuisine_values
        assert "korean" in cuisine_values

    def test_sub_collections_are_not_lists_on_the_page(self, db_session):
        _collection(db_session, "chicken", "Chicken", n_cards=4, fetched=True, parent="chicken-recipes")
        ingredient_values = _theme(build_themes(db_session), "ingredient").values
        assert ingredient_values == []

    def test_source_theme_gathers_library_and_catalog_lists(self, db_session):
        _recipe(db_session, "A", [], source_type="hellofresh_web")
        _recipe(db_session, "B", [], source_type="kitchen_sanctuary")
        _collection(db_session, "italian-recipes", "Italian Recipes", n_cards=2, fetched=True)

        themes = build_themes(db_session)
        hellofresh = _value(themes, "source", "hellofresh")
        sanctuary = _value(themes, "source", "kitchen_sanctuary")

        assert hellofresh.library_source_type == "hellofresh_web"
        assert hellofresh.library_count == 1
        assert [c.slug for c in hellofresh.collections] == ["italian-recipes"]
        assert sanctuary.label == "Kitchen Sanctuary"
        assert sanctuary.collections == []

    def test_collection_contains_values_its_cards_share(self, db_session):
        """A card in both Italian and Vegetarian makes each collection 'contain' the other."""
        italian = _collection(db_session, "italian-recipes", "Italian Recipes", n_cards=2, fetched=True)
        vegetarian = _collection(db_session, "vegetarian-recipes", "Vegetarian Recipes", n_cards=1, fetched=True)
        _collection(db_session, "thai-recipes", "Thai Recipes", n_cards=1, fetched=True)
        shared_card = db_session.query(SourceCollectionCard).filter_by(collection_id=italian.id).first().card_id
        db_session.add(SourceCollectionCard(collection_id=vegetarian.id, card_id=shared_card, position=1))
        db_session.commit()

        themes = build_themes(db_session)
        italian_list = _value(themes, "cuisine", "italian").collections[0]
        vegetarian_list = _value(themes, "diet", "vegetarian").collections[0]
        thai_list = _value(themes, "cuisine", "thai").collections[0]

        assert italian_list.contains == ["diet:vegetarian"]
        assert vegetarian_list.contains == ["cuisine:italian"]
        assert thai_list.contains == []

    def test_values_sorted_fullest_first(self, db_session):
        _collection(db_session, "african-recipes", "African Recipes", n_cards=1, fetched=True)
        _collection(db_session, "american-recipes", "American Recipes", n_cards=3, fetched=True)

        cuisine = [v.value for v in _theme(build_themes(db_session), "cuisine").values]

        assert cuisine == ["american", "african"]


class TestThemesEndpoint:
    def test_returns_themes_for_an_authenticated_user(self, db_session):
        app = FastAPI()
        app.include_router(themes_router_module.router)
        app.dependency_overrides[get_db] = lambda: db_session
        user = User(id=uuid4(), email="m@example.com", hashed_password=hash_password("pw123456789"),
                    name="M", role=UserRole.member.value)
        db_session.add(user)
        db_session.commit()
        _collection(db_session, "italian-recipes", "Italian Recipes", n_cards=2, fetched=True)
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}

        response = TestClient(app).get("/themes", headers=headers)

        assert response.status_code == 200
        cuisine = next(t for t in response.json() if t["key"] == "cuisine")
        assert cuisine["values"][0]["collections"][0]["slug"] == "italian-recipes"

    def test_requires_auth(self, db_session):
        app = FastAPI()
        app.include_router(themes_router_module.router)
        app.dependency_overrides[get_db] = lambda: db_session
        assert TestClient(app).get("/themes").status_code in (401, 403)


# ---------------------------------------------------------------------------
# Per-source COLLECTION_THEMES map (#599)
# ---------------------------------------------------------------------------


class TestCollectionThemesRegistry:
    def test_hellofresh_web_key_exists_in_collection_themes(self):
        assert HELLOFRESH_SOURCE in COLLECTION_THEMES

    def test_alias_equals_hellofresh_entry(self):
        assert HELLOFRESH_COLLECTION_THEMES is COLLECTION_THEMES[HELLOFRESH_SOURCE]

    def test_every_hellofresh_slug_points_at_known_value(self):
        for slug, (theme, value) in COLLECTION_THEMES[HELLOFRESH_SOURCE].items():
            assert value in VALUE_LABELS[theme], (slug, theme, value)

    def test_unknown_source_returns_empty_map(self):
        assert COLLECTION_THEMES.get("unknown_source", {}) == {}

    def test_non_hellofresh_collection_not_classified(self, db_session):
        """A collection from an unknown source is not classified into any theme."""
        other = SourceCollection(
            source_type="other_source",
            slug="italian-recipes",
            name="Italian Recipes",
            url="https://other.example.com/recipes/italian",
            last_fetched_at=datetime.now(timezone.utc),
        )
        db_session.add(other)
        db_session.flush()
        for i in range(3):
            c = SourceRecipeCard(
                source_type="other_source",
                recipe_url=f"https://other.example.com/r{i}-" + "a" * 24,
                external_id=f"o{i}",
                name=f"R{i}",
                image_url="x",
            )
            db_session.add(c)
            db_session.flush()
            db_session.add(SourceCollectionCard(collection_id=other.id, card_id=c.id, position=i))
        db_session.commit()

        themes = build_themes(db_session)
        cuisine = next(t for t in themes if t.key == "cuisine")
        # The other_source collection carries the slug "italian-recipes" but is NOT classified.
        classified_slugs = [c.slug for v in cuisine.values for c in v.collections]
        assert "italian-recipes" not in classified_slugs
