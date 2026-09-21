"""
Model-level tests for UserCookEvent and UserRecipeView.

Covers:
- Create a row, read it back, confirm column values
- FK relationships resolve (user_rel, recipe_rel)
- Multiple rows per user/recipe (no unique constraint)
- meal_plan_entry_id is nullable on UserCookEvent
- source is nullable on UserRecipeView
"""

import pytest
from uuid import uuid4
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models  # noqa: F401 — registers all models with Base.metadata
from src.db.models.user import User
from src.db.models.recipe import Recipe
from src.db.models.user_cook_event import UserCookEvent
from src.db.models.user_recipe_view import UserRecipeView


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a fresh in-memory database with all tables for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def user_and_recipe(db_session):
    """Create a minimal User and Recipe for FK references."""
    user = User(
        id=uuid4(),
        name="Test User",
        role="member",
        dietary_profile=[],
        allergies=[],
        disliked_ingredients=[],
        favorite_ingredients=[],
    )
    recipe = Recipe(
        id=uuid4(),
        name="Test Recipe",
        source_type="manual",
        steps=[],
        tags=[],
        base_servings=4,
        times_cooked=0,
        is_persisted=True,
    )
    db_session.add(user)
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(recipe)
    return user, recipe


class TestUserCookEvent:
    def test_create_and_read_back(self, db_session, user_and_recipe):
        """Create a UserCookEvent row and confirm it round-trips correctly."""
        user, recipe = user_and_recipe

        event = UserCookEvent(
            id=uuid4(),
            user_id=user.id,
            recipe_id=recipe.id,
            notes="Doubled the spices",
        )
        db_session.add(event)
        db_session.commit()

        fetched = db_session.get(UserCookEvent, event.id)
        assert fetched is not None
        assert fetched.user_id == user.id
        assert fetched.recipe_id == recipe.id
        assert fetched.notes == "Doubled the spices"
        # cooked_at is populated by server_default; SQLite returns it as a string
        # or datetime depending on driver — just verify it's truthy
        assert fetched.cooked_at is not None
        # meal_plan_entry_id is nullable
        assert fetched.meal_plan_entry_id is None

    def test_fk_relationships_resolve(self, db_session, user_and_recipe):
        """FK relationships on UserCookEvent load the correct related objects."""
        user, recipe = user_and_recipe

        event = UserCookEvent(
            id=uuid4(),
            user_id=user.id,
            recipe_id=recipe.id,
        )
        db_session.add(event)
        db_session.commit()
        db_session.expire_all()  # force relationship reload from DB

        fetched = db_session.get(UserCookEvent, event.id)
        assert fetched.user_rel.id == user.id
        assert fetched.user_rel.name == "Test User"
        assert fetched.recipe_rel.id == recipe.id
        assert fetched.recipe_rel.name == "Test Recipe"

    def test_multiple_cook_events_allowed(self, db_session, user_and_recipe):
        """No unique constraint — same user/recipe pair can have many rows."""
        user, recipe = user_and_recipe

        event_1 = UserCookEvent(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        event_2 = UserCookEvent(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        event_3 = UserCookEvent(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        db_session.add_all([event_1, event_2, event_3])
        db_session.commit()

        rows = db_session.execute(
            select(UserCookEvent).where(
                UserCookEvent.user_id == user.id,
                UserCookEvent.recipe_id == recipe.id,
            )
        ).scalars().all()
        assert len(rows) == 3

    def test_cook_events_visible_via_user_relationship(self, db_session, user_and_recipe):
        """cook_events relationship on User loads all cook events for that user."""
        user, recipe = user_and_recipe

        event_a = UserCookEvent(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        event_b = UserCookEvent(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        db_session.add_all([event_a, event_b])
        db_session.commit()
        db_session.expire_all()

        fetched_user = db_session.get(User, user.id)
        assert len(fetched_user.cook_events) == 2

    def test_cook_events_visible_via_recipe_relationship(self, db_session, user_and_recipe):
        """cook_events relationship on Recipe loads all cook events for that recipe."""
        user, recipe = user_and_recipe

        event = UserCookEvent(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        db_session.add(event)
        db_session.commit()
        db_session.expire_all()

        fetched_recipe = db_session.get(Recipe, recipe.id)
        assert len(fetched_recipe.cook_events) == 1
        assert fetched_recipe.cook_events[0].id == event.id


class TestUserRecipeView:
    def test_create_and_read_back(self, db_session, user_and_recipe):
        """Create a UserRecipeView row and confirm it round-trips correctly."""
        user, recipe = user_and_recipe

        view = UserRecipeView(
            id=uuid4(),
            user_id=user.id,
            recipe_id=recipe.id,
            source="browse",
        )
        db_session.add(view)
        db_session.commit()

        fetched = db_session.get(UserRecipeView, view.id)
        assert fetched is not None
        assert fetched.user_id == user.id
        assert fetched.recipe_id == recipe.id
        assert fetched.source == "browse"
        assert fetched.viewed_at is not None

    def test_source_is_nullable(self, db_session, user_and_recipe):
        """source column accepts NULL."""
        user, recipe = user_and_recipe

        view = UserRecipeView(
            id=uuid4(),
            user_id=user.id,
            recipe_id=recipe.id,
            # source intentionally omitted
        )
        db_session.add(view)
        db_session.commit()

        fetched = db_session.get(UserRecipeView, view.id)
        assert fetched.source is None

    def test_fk_relationships_resolve(self, db_session, user_and_recipe):
        """FK relationships on UserRecipeView load the correct related objects."""
        user, recipe = user_and_recipe

        view = UserRecipeView(
            id=uuid4(),
            user_id=user.id,
            recipe_id=recipe.id,
            source="feed",
        )
        db_session.add(view)
        db_session.commit()
        db_session.expire_all()

        fetched = db_session.get(UserRecipeView, view.id)
        assert fetched.user_rel.id == user.id
        assert fetched.recipe_rel.id == recipe.id

    def test_multiple_views_allowed(self, db_session, user_and_recipe):
        """No unique constraint — same user/recipe pair can have many view rows."""
        user, recipe = user_and_recipe

        views = [
            UserRecipeView(id=uuid4(), user_id=user.id, recipe_id=recipe.id, source="browse"),
            UserRecipeView(id=uuid4(), user_id=user.id, recipe_id=recipe.id, source="search"),
            UserRecipeView(id=uuid4(), user_id=user.id, recipe_id=recipe.id, source="feed"),
        ]
        db_session.add_all(views)
        db_session.commit()

        rows = db_session.execute(
            select(UserRecipeView).where(
                UserRecipeView.user_id == user.id,
                UserRecipeView.recipe_id == recipe.id,
            )
        ).scalars().all()
        assert len(rows) == 3

    def test_views_visible_via_user_relationship(self, db_session, user_and_recipe):
        """recipe_views relationship on User loads all view events for that user."""
        user, recipe = user_and_recipe

        view_1 = UserRecipeView(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        view_2 = UserRecipeView(id=uuid4(), user_id=user.id, recipe_id=recipe.id)
        db_session.add_all([view_1, view_2])
        db_session.commit()
        db_session.expire_all()

        fetched_user = db_session.get(User, user.id)
        assert len(fetched_user.recipe_views) == 2

    def test_views_visible_via_recipe_relationship(self, db_session, user_and_recipe):
        """views relationship on Recipe loads all view events for that recipe."""
        user, recipe = user_and_recipe

        view = UserRecipeView(id=uuid4(), user_id=user.id, recipe_id=recipe.id, source="menu")
        db_session.add(view)
        db_session.commit()
        db_session.expire_all()

        fetched_recipe = db_session.get(Recipe, recipe.id)
        assert len(fetched_recipe.views) == 1
        assert fetched_recipe.views[0].source == "menu"
