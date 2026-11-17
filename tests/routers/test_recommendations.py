"""
Integration tests for the GET /recommendations endpoint.

Covers:
- Authentication required (401 without token)
- Returns list of RecommendedItem with correct shape
- Empty catalog → empty list
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.source_catalog import SourceCollection, SourceRecipeCard, SourceCollectionCard
from src.services.auth_service import hash_password, create_access_token

from src.routers import recommendations as recommendations_module

TEST_DATABASE_URL = "sqlite:///:memory:"

app = FastAPI(title="FreshUp", version="0.1.0")
app.include_router(recommendations_module.router)


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
    _ = models  # ensure all models are registered with Base.metadata
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid4(),
        email="rec-test@example.com",
        hashed_password=hash_password("password123"),
        name="Rec Test User",
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


class TestRecommendationsAuth:
    def test_requires_authentication(self, client):
        response = client.get("/recommendations")
        assert response.status_code == 401

    def test_authenticated_request_succeeds(self, client, auth_headers):
        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200


class TestRecommendationsResponse:
    def test_empty_catalog_returns_empty_list(self, client, auth_headers):
        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_returns_recommended_item_shape(self, client, auth_headers, db_session):
        # Seed one top-level collection and one card
        collection = SourceCollection(
            id=uuid4(),
            source_type="hellofresh_web",
            slug="all-recipes",
            name="All Recipes",
            parent_slug=None,
            url="https://www.hellofresh.com/recipes",
        )
        db_session.add(collection)
        db_session.flush()

        card = SourceRecipeCard(
            id=uuid4(),
            source_type="hellofresh_web",
            external_id="ext-001",
            name="Lemon Herb Chicken",
            recipe_url="https://www.hellofresh.com/recipes/lemon-herb-chicken",
            rating=4.5,
            rating_count=200,
        )
        db_session.add(card)
        db_session.flush()

        link = SourceCollectionCard(
            collection_id=collection.id,
            card_id=card.id,
            position=0,
        )
        db_session.add(link)
        db_session.commit()

        response = client.get("/recommendations?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        item = data[0]
        assert "kind" in item
        assert "score" in item
        assert "reason" in item
        assert item["kind"] in ("card", "recipe")
        assert item["reason"] in ("taste", "popular", "explore")
        if item["kind"] == "card":
            assert item["card"] is not None
            assert item["recipe"] is None
            assert "id" in item["card"]
            assert "name" in item["card"]
        else:
            assert item["recipe"] is not None
            assert item["card"] is None

    def test_limit_parameter_respected(self, client, auth_headers, db_session):
        # Seed 5 cards
        collection = SourceCollection(
            id=uuid4(),
            source_type="hellofresh_web",
            slug="big-collection",
            name="Big Collection",
            parent_slug=None,
            url="https://www.hellofresh.com/recipes",
        )
        db_session.add(collection)
        db_session.flush()

        for i in range(5):
            card = SourceRecipeCard(
                id=uuid4(),
                source_type="hellofresh_web",
                external_id=f"ext-{i:03d}",
                name=f"Recipe {i}",
                recipe_url=f"https://www.hellofresh.com/recipes/recipe-{i}",
                rating=float(3 + i % 2),
                rating_count=100,
            )
            db_session.add(card)
            db_session.flush()
            db_session.add(SourceCollectionCard(collection_id=collection.id, card_id=card.id, position=i))
        db_session.commit()

        response = client.get("/recommendations?limit=3", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_limit_defaults_to_20(self, client, auth_headers, db_session):
        # Seed 25 cards
        collection = SourceCollection(
            id=uuid4(),
            source_type="hellofresh_web",
            slug="default-limit-coll",
            name="Default Limit Collection",
            parent_slug=None,
            url="https://www.hellofresh.com/recipes",
        )
        db_session.add(collection)
        db_session.flush()

        for i in range(25):
            card = SourceRecipeCard(
                id=uuid4(),
                source_type="hellofresh_web",
                external_id=f"dl-{i:03d}",
                name=f"Default Recipe {i}",
                recipe_url=f"https://www.hellofresh.com/recipes/default-{i}",
                rating=4.0,
                rating_count=100,
            )
            db_session.add(card)
            db_session.flush()
            db_session.add(SourceCollectionCard(collection_id=collection.id, card_id=card.id, position=i))
        db_session.commit()

        response = client.get("/recommendations", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 20
