"""Integration tests for GET /recommendations."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.db import models
from src.db.database import Base, get_db
from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.db.models.user import User, UserRole
from src.routers.recommendations import router as recommendations_router
from src.services.auth_service import create_access_token, hash_password

TEST_DATABASE_URL = "sqlite:///:memory:"

app = FastAPI(title="FreshUp")
app.include_router(recommendations_router)


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
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid4(),
        email="rec-router@example.com",
        hashed_password=hash_password("password123"),
        name="Rec Router User",
        role=UserRole.member.value,
        taste_preferences={},
        allergies=[],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_collection(db, source_type="hellofresh_web", slug="all-recs"):
    coll = SourceCollection(
        id=uuid4(), source_type=source_type, slug=slug, name=slug,
        url=f"https://example.com/{slug}", parent_slug=None,
    )
    db.add(coll)
    db.flush()
    return coll


def _add_card(db, coll, name="Card", source_type="hellofresh_web"):
    card = SourceRecipeCard(
        id=uuid4(), source_type=source_type, external_id=str(uuid4()),
        name=name, recipe_url=f"https://example.com/{uuid4()}",
        rating=4.0, rating_count=100,
    )
    db.add(card)
    db.flush()
    db.add(SourceCollectionCard(collection_id=coll.id, card_id=card.id, position=0))
    db.flush()
    return card


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuth:
    def test_requires_authentication(self, client):
        response = client.get("/recommendations")
        assert response.status_code == 401

    def test_authenticated_request_succeeds(self, client, auth_headers, db_session):
        db_session.commit()
        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200

    def test_returns_list(self, client, auth_headers, db_session):
        db_session.commit()
        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

class TestResponseShape:
    def test_card_items_have_required_fields(self, client, auth_headers, db_session):
        """Card items include kind, card, score, reason."""
        coll = _add_collection(db_session)
        _add_card(db_session, coll)
        db_session.commit()

        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        card_items = [d for d in data if d["kind"] == "card"]
        assert len(card_items) >= 1

        item = card_items[0]
        assert item["kind"] == "card"
        assert item["card"] is not None
        assert item["recipe"] is None
        assert "score" in item
        assert item["reason"] in ("taste", "popular", "explore")

    def test_card_response_has_expected_fields(self, client, auth_headers, db_session):
        """Card sub-object has id, name, source_type, recipe_url, etc."""
        coll = _add_collection(db_session)
        _add_card(db_session, coll, name="Test Card")
        db_session.commit()

        response = client.get("/recommendations", headers=auth_headers)
        data = response.json()
        card_items = [d for d in data if d["kind"] == "card"]
        assert len(card_items) >= 1

        card = card_items[0]["card"]
        for field in ("id", "name", "source_type", "recipe_url", "is_persisted", "tags"):
            assert field in card, f"Missing field: {field}"

    def test_recipe_items_have_required_fields(self, client, auth_headers, db_session):
        """Unlinked recipe items include kind=recipe, recipe object, score, reason."""
        # Add an unlinked recipe (no card pointing to it)
        recipe = Recipe(
            id=uuid4(), name="Unlinked Recipe", source_type="url_import",
            is_persisted=True, times_cooked=0, tags=[], steps=[],
        )
        db_session.add(recipe)
        db_session.commit()

        response = client.get("/recommendations", headers=auth_headers)
        data = response.json()
        recipe_items = [d for d in data if d["kind"] == "recipe"]
        assert len(recipe_items) >= 1

        item = recipe_items[0]
        assert item["kind"] == "recipe"
        assert item["recipe"] is not None
        assert item["card"] is None
        assert "score" in item
        assert item["reason"] in ("taste", "popular", "explore")

    def test_cold_start_reasons_are_popular_or_explore(self, client, auth_headers, db_session):
        """Cold-start user (no history) sees reason=popular or explore, not taste."""
        coll = _add_collection(db_session)
        for i in range(6):
            _add_card(db_session, coll, name=f"Card {i}")
        db_session.commit()

        response = client.get("/recommendations", headers=auth_headers)
        data = response.json()
        for item in data:
            assert item["reason"] in ("popular", "explore")


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------

class TestLimitParameter:
    def test_limit_respected(self, client, auth_headers, db_session):
        """The limit query parameter caps the response length."""
        coll = _add_collection(db_session)
        for i in range(10):
            _add_card(db_session, coll, name=f"Card {i}")
        db_session.commit()

        response = client.get("/recommendations?limit=3", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) <= 3

    def test_default_limit_is_twenty(self, client, auth_headers, db_session):
        """Default limit is 20."""
        coll = _add_collection(db_session)
        for i in range(25):
            _add_card(db_session, coll, name=f"Card {i}")
        db_session.commit()

        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) <= 20

    def test_invalid_limit_returns_422(self, client, auth_headers):
        response = client.get("/recommendations?limit=0", headers=auth_headers)
        assert response.status_code == 422

    def test_empty_catalog_returns_empty_list(self, client, auth_headers, db_session):
        """When there are no catalog cards or recipes, the response is an empty list."""
        db_session.commit()
        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
