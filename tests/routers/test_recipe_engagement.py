"""
Tests for the recipe engagement toggles: bookmark and like.

These endpoints exist because POST /recipes/{id}/rate is a whole-relation
upsert — it dumps every field of UserRecipeRelationCreate onto the row, so a
request that sets only is_bookmarked also writes is_liked=False and
rating=None, silently destroying the user's other state. The toggles below
touch exactly one field each, which is what a quick-action button on a recipe
card needs.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models  # noqa: F401  — registers models with Base.metadata
from src.db.models.recipe import Recipe
from src.db.models.user import User, UserRole
from src.db.models.user_recipe import UserRecipeRelation
from src.db.models.menu import Menu
from src.main import app
from src.services.auth_service import create_access_token


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-engagement-tests")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
    # TestClient is constructed without its context manager on purpose: entering
    # it would run the app lifespan, which migrates and seeds the real database
    # rather than this in-memory one. Matches tests/routers/test_recipes.py.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid4(),
        name="Engagement Tester",
        email="engagement@freshup.test",
        hashed_password="x",
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def recipe(db_session, test_user):
    r = Recipe(
        id=uuid4(),
        name="Engagement Test Recipe",
        source_type="manual",
        created_by=test_user.id,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture
def browse_cache_recipe(db_session):
    """A scraped recipe, not yet persisted — the browse-cache case."""
    r = Recipe(
        id=uuid4(),
        name="Scraped Recipe",
        source_type="hellofresh_web",
        is_persisted=False,
        created_by=None,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


def _relation(db_session, user, recipe):
    return (
        db_session.query(UserRecipeRelation)
        .filter(
            UserRecipeRelation.user_id == user.id,
            UserRecipeRelation.recipe_id == recipe.id,
        )
        .first()
    )


class TestBookmarkToggle:
    def test_bookmark_creates_relation(self, client, auth_headers, recipe, db_session, test_user):
        response = client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["is_bookmarked"] is True
        db_session.expire_all()
        assert _relation(db_session, test_user, recipe).is_bookmarked is True

    def test_bookmark_is_idempotent(self, client, auth_headers, recipe):
        client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)
        second = client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)

        assert second.status_code == 200
        assert second.json()["is_bookmarked"] is True

    def test_unbookmark_clears_flag(self, client, auth_headers, recipe):
        client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)
        response = client.delete(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["is_bookmarked"] is False

    def test_unbookmark_is_idempotent_when_never_bookmarked(self, client, auth_headers, recipe):
        response = client.delete(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["is_bookmarked"] is False

    def test_bookmark_accepts_menu_assignment(self, client, auth_headers, recipe, db_session, test_user):
        menu = Menu(id=uuid4(), user_id=test_user.id, name="Weeknight")
        db_session.add(menu)
        db_session.commit()

        response = client.post(
            f"/recipes/{recipe.id}/bookmark",
            json={"menu_id": str(menu.id)},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["menu_id"] == str(menu.id)

    def test_bookmark_unknown_recipe_is_404(self, client, auth_headers):
        response = client.post(f"/recipes/{uuid4()}/bookmark", headers=auth_headers)
        assert response.status_code == 404

    def test_bookmark_requires_auth(self, client, recipe):
        assert client.post(f"/recipes/{recipe.id}/bookmark").status_code == 401


class TestLikeToggle:
    def test_like_creates_relation(self, client, auth_headers, recipe, db_session, test_user):
        response = client.post(f"/recipes/{recipe.id}/like", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["is_liked"] is True
        db_session.expire_all()
        assert _relation(db_session, test_user, recipe).is_liked is True

    def test_unlike_clears_flag(self, client, auth_headers, recipe):
        client.post(f"/recipes/{recipe.id}/like", headers=auth_headers)
        response = client.delete(f"/recipes/{recipe.id}/like", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["is_liked"] is False

    def test_like_unknown_recipe_is_404(self, client, auth_headers):
        assert client.post(f"/recipes/{uuid4()}/like", headers=auth_headers).status_code == 404

    def test_like_requires_auth(self, client, recipe):
        assert client.post(f"/recipes/{recipe.id}/like").status_code == 401


class TestTogglesDoNotClobberEachOther:
    """
    The reason these endpoints exist.

    A card has independent bookmark and like buttons. Tapping one must never
    change the other, and neither may discard a rating the user has left.
    """

    def test_like_preserves_bookmark(self, client, auth_headers, recipe):
        client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)
        response = client.post(f"/recipes/{recipe.id}/like", headers=auth_headers)

        body = response.json()
        assert body["is_liked"] is True
        assert body["is_bookmarked"] is True, "liking a recipe cleared its bookmark"

    def test_bookmark_preserves_like(self, client, auth_headers, recipe):
        client.post(f"/recipes/{recipe.id}/like", headers=auth_headers)
        response = client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)

        body = response.json()
        assert body["is_bookmarked"] is True
        assert body["is_liked"] is True, "bookmarking a recipe cleared its like"

    def test_unbookmark_preserves_like(self, client, auth_headers, recipe):
        client.post(f"/recipes/{recipe.id}/like", headers=auth_headers)
        client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)
        response = client.delete(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)

        body = response.json()
        assert body["is_bookmarked"] is False
        assert body["is_liked"] is True, "removing a bookmark cleared the like"

    def test_toggles_preserve_an_existing_rating(self, client, auth_headers, recipe, db_session, test_user):
        db_session.add(
            UserRecipeRelation(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=recipe.id,
                rating=4.5,
                rating_comment="Great with extra chili",
            )
        )
        db_session.commit()

        client.post(f"/recipes/{recipe.id}/bookmark", headers=auth_headers)
        response = client.post(f"/recipes/{recipe.id}/like", headers=auth_headers)

        body = response.json()
        assert body["rating"] == 4.5, "toggling engagement discarded the rating"
        assert body["rating_comment"] == "Great with extra chili"


class TestPersistenceTrigger:
    """Engaging with a browse-cache recipe makes it permanent."""

    def test_bookmark_persists_browse_cache_recipe(
        self, client, auth_headers, browse_cache_recipe, db_session
    ):
        assert browse_cache_recipe.is_persisted is False

        client.post(f"/recipes/{browse_cache_recipe.id}/bookmark", headers=auth_headers)

        db_session.expire_all()
        refreshed = db_session.query(Recipe).filter_by(id=browse_cache_recipe.id).one()
        assert refreshed.is_persisted is True

    def test_like_persists_browse_cache_recipe(
        self, client, auth_headers, browse_cache_recipe, db_session
    ):
        client.post(f"/recipes/{browse_cache_recipe.id}/like", headers=auth_headers)

        db_session.expire_all()
        refreshed = db_session.query(Recipe).filter_by(id=browse_cache_recipe.id).one()
        assert refreshed.is_persisted is True

    def test_unbookmark_does_not_reverse_persistence(
        self, client, auth_headers, browse_cache_recipe, db_session
    ):
        """
        Persistence is one-way: another user may hold their own relation, and a
        recipe that vanished after an accidental un-bookmark would be worse than
        a slightly larger table.
        """
        client.post(f"/recipes/{browse_cache_recipe.id}/bookmark", headers=auth_headers)
        client.delete(f"/recipes/{browse_cache_recipe.id}/bookmark", headers=auth_headers)

        db_session.expire_all()
        refreshed = db_session.query(Recipe).filter_by(id=browse_cache_recipe.id).one()
        assert refreshed.is_persisted is True


class TestMyRelationsBulkFetch:
    """
    One request for every relation the user holds.

    A browse grid renders ~20 cards at once; fetching each card's relation
    separately would be 20 round trips to paint one screen.
    """

    def test_returns_empty_list_for_new_user(self, client, auth_headers):
        response = client.get("/recipes/my-relations", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_all_relations_for_user(self, client, auth_headers, db_session, test_user):
        recipes = []
        for i in range(3):
            r = Recipe(id=uuid4(), name=f"Recipe {i}", source_type="manual", created_by=test_user.id)
            db_session.add(r)
            recipes.append(r)
        db_session.commit()

        client.post(f"/recipes/{recipes[0].id}/bookmark", headers=auth_headers)
        client.post(f"/recipes/{recipes[1].id}/like", headers=auth_headers)

        response = client.get("/recipes/my-relations", headers=auth_headers)

        assert response.status_code == 200
        by_recipe = {r["recipe_id"]: r for r in response.json()}
        assert len(by_recipe) == 2
        assert by_recipe[str(recipes[0].id)]["is_bookmarked"] is True
        assert by_recipe[str(recipes[1].id)]["is_liked"] is True
        assert str(recipes[2].id) not in by_recipe

    def test_does_not_leak_other_users_relations(
        self, client, auth_headers, db_session, test_user, recipe
    ):
        other = User(
            id=uuid4(),
            name="Housemate",
            email="housemate@freshup.test",
            hashed_password="x",
            role=UserRole.member.value,
        )
        db_session.add(other)
        db_session.add(
            UserRecipeRelation(
                id=uuid4(), user_id=other.id, recipe_id=recipe.id, is_liked=True
            )
        )
        db_session.commit()

        response = client.get("/recipes/my-relations", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == [], "another user's relations were returned"

    def test_route_is_not_shadowed_by_recipe_id_param(self, client, auth_headers):
        """
        Regression guard on route ordering.

        /recipes/my-relations must be declared before /recipes/{recipe_id}; if it
        slips below, FastAPI parses "my-relations" as a recipe_id and answers 422
        instead of a relation list.
        """
        response = client.get("/recipes/my-relations", headers=auth_headers)
        assert response.status_code == 200, (
            "GET /recipes/my-relations was captured by the /{recipe_id} route — "
            "move its declaration above that route."
        )

    def test_requires_auth(self, client):
        assert client.get("/recipes/my-relations").status_code == 401
