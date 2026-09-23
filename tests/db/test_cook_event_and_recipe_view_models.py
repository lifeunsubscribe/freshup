"""
Model tests for UserCookEvent and UserRecipeView.

Tests cover:
- Creating rows and reading them back
- FK relationships resolve (user_rel, recipe_rel)
- CASCADE delete: deleting a user removes their cook events and views
- CASCADE delete: deleting a recipe removes associated cook events and views
- SET NULL on meal_plan_entry_id: deleting a MealPlanEntry nullifies the link
  without deleting the cook event
- Multiple cook events and views for the same user/recipe are allowed (no
  unique constraint)
"""

import pytest
from uuid import uuid4
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models  # noqa: F401 — registers all models with Base.metadata
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.db.models.meal_plan import MealPlanEntry, MealType, MealPlanStatus
from src.db.models.user_cook_event import UserCookEvent
from src.db.models.user_recipe_view import UserRecipeView


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
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
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
    """A persisted User for FK tests."""
    user = User(
        id=uuid4(),
        name="Cook Tester",
        email="cooktester@example.com",
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_recipe(db_session, test_user):
    """A persisted Recipe for FK tests."""
    recipe = Recipe(
        id=uuid4(),
        name="Test Recipe",
        source_type="manual",
        is_persisted=True,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def test_meal_plan_entry(db_session):
    """A persisted MealPlanEntry for FK tests."""
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2026, 10, 1),
        meal_type=MealType.dinner.value,
        status=MealPlanStatus.approved.value,
        planned_servings=2,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# UserCookEvent tests
# ---------------------------------------------------------------------------

class TestUserCookEventModel:
    """Round-trip and relationship tests for UserCookEvent."""

    def test_create_and_read_back(self, db_session, test_user, test_recipe):
        """Create a cook event, read it back, verify fields."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            notes="Delicious!",
        )
        db_session.add(event)
        db_session.commit()

        loaded = db_session.get(UserCookEvent, event.id)
        assert loaded is not None
        assert loaded.user_id == test_user.id
        assert loaded.recipe_id == test_recipe.id
        assert loaded.notes == "Delicious!"
        assert loaded.meal_plan_entry_id is None
        assert loaded.cooked_at is not None

    def test_user_rel_resolves(self, db_session, test_user, test_recipe):
        """user_rel relationship traverses correctly."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.user_rel.id == test_user.id
        assert event.user_rel.name == test_user.name

    def test_recipe_rel_resolves(self, db_session, test_user, test_recipe):
        """recipe_rel relationship traverses correctly."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.recipe_rel.id == test_recipe.id
        assert event.recipe_rel.name == test_recipe.name

    def test_meal_plan_entry_rel_resolves(self, db_session, test_user, test_recipe, test_meal_plan_entry):
        """meal_plan_entry_rel resolves when meal_plan_entry_id is set."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            meal_plan_entry_id=test_meal_plan_entry.id,
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.meal_plan_entry_rel.id == test_meal_plan_entry.id

    def test_user_cook_events_backref(self, db_session, test_user, test_recipe):
        """User.cook_events back-reference includes the event."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(test_user)

        assert any(e.id == event.id for e in test_user.cook_events)

    def test_recipe_cook_events_backref(self, db_session, test_user, test_recipe):
        """Recipe.cook_events back-reference includes the event."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(test_recipe)

        assert any(e.id == event.id for e in test_recipe.cook_events)

    def test_multiple_cook_events_allowed(self, db_session, test_user, test_recipe):
        """No unique constraint — multiple cook events per user/recipe are allowed."""
        for _ in range(3):
            db_session.add(UserCookEvent(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=test_recipe.id,
            ))
        db_session.commit()

        count = db_session.query(UserCookEvent).filter_by(
            user_id=test_user.id, recipe_id=test_recipe.id
        ).count()
        assert count == 3

    def test_cascade_delete_on_user(self, db_session, test_user, test_recipe):
        """Deleting a user cascades to their cook events."""
        event_id = uuid4()
        db_session.add(UserCookEvent(
            id=event_id,
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        ))
        db_session.commit()

        db_session.delete(test_user)
        db_session.commit()

        assert db_session.get(UserCookEvent, event_id) is None

    def test_cascade_delete_on_recipe(self, db_session, test_user, test_recipe):
        """Deleting a recipe cascades to its cook events."""
        event_id = uuid4()
        db_session.add(UserCookEvent(
            id=event_id,
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        ))
        db_session.commit()

        db_session.delete(test_recipe)
        db_session.commit()

        assert db_session.get(UserCookEvent, event_id) is None

    def test_set_null_on_meal_plan_entry_delete(self, db_session, test_user, test_recipe, test_meal_plan_entry):
        """Deleting a MealPlanEntry sets meal_plan_entry_id to NULL, event survives."""
        event = UserCookEvent(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            meal_plan_entry_id=test_meal_plan_entry.id,
        )
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        db_session.delete(test_meal_plan_entry)
        db_session.commit()

        loaded = db_session.get(UserCookEvent, event_id)
        assert loaded is not None, "Cook event must survive after MealPlanEntry is deleted"
        assert loaded.meal_plan_entry_id is None


# ---------------------------------------------------------------------------
# UserRecipeView tests
# ---------------------------------------------------------------------------

class TestUserRecipeViewModel:
    """Round-trip and relationship tests for UserRecipeView."""

    def test_create_and_read_back(self, db_session, test_user, test_recipe):
        """Create a view event, read it back, verify fields."""
        view = UserRecipeView(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            source="browse",
        )
        db_session.add(view)
        db_session.commit()

        loaded = db_session.get(UserRecipeView, view.id)
        assert loaded is not None
        assert loaded.user_id == test_user.id
        assert loaded.recipe_id == test_recipe.id
        assert loaded.source == "browse"
        assert loaded.viewed_at is not None

    def test_user_rel_resolves(self, db_session, test_user, test_recipe):
        """user_rel relationship traverses correctly."""
        view = UserRecipeView(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(view)
        db_session.commit()
        db_session.refresh(view)

        assert view.user_rel.id == test_user.id

    def test_recipe_rel_resolves(self, db_session, test_user, test_recipe):
        """recipe_rel relationship traverses correctly."""
        view = UserRecipeView(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(view)
        db_session.commit()
        db_session.refresh(view)

        assert view.recipe_rel.id == test_recipe.id

    def test_user_recipe_views_backref(self, db_session, test_user, test_recipe):
        """User.recipe_views back-reference includes the view."""
        view = UserRecipeView(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            source="search",
        )
        db_session.add(view)
        db_session.commit()
        db_session.refresh(test_user)

        assert any(v.id == view.id for v in test_user.recipe_views)

    def test_recipe_views_backref(self, db_session, test_user, test_recipe):
        """Recipe.views back-reference includes the view."""
        view = UserRecipeView(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        )
        db_session.add(view)
        db_session.commit()
        db_session.refresh(test_recipe)

        assert any(v.id == view.id for v in test_recipe.views)

    def test_multiple_views_allowed(self, db_session, test_user, test_recipe):
        """No unique constraint — multiple views per user/recipe are allowed."""
        for source in ["browse", "search", "feed"]:
            db_session.add(UserRecipeView(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=test_recipe.id,
                source=source,
            ))
        db_session.commit()

        count = db_session.query(UserRecipeView).filter_by(
            user_id=test_user.id, recipe_id=test_recipe.id
        ).count()
        assert count == 3

    def test_source_nullable(self, db_session, test_user, test_recipe):
        """source field is nullable."""
        view = UserRecipeView(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            source=None,
        )
        db_session.add(view)
        db_session.commit()

        loaded = db_session.get(UserRecipeView, view.id)
        assert loaded.source is None

    def test_cascade_delete_on_user(self, db_session, test_user, test_recipe):
        """Deleting a user cascades to their recipe views."""
        view_id = uuid4()
        db_session.add(UserRecipeView(
            id=view_id,
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        ))
        db_session.commit()

        db_session.delete(test_user)
        db_session.commit()

        assert db_session.get(UserRecipeView, view_id) is None

    def test_cascade_delete_on_recipe(self, db_session, test_user, test_recipe):
        """Deleting a recipe cascades to its view records.

        This is load-bearing: browse-cache recipes (is_persisted=False) are pruned
        by cleanup_service. Without CASCADE the delete would either fail or orphan
        view rows.
        """
        view_id = uuid4()
        db_session.add(UserRecipeView(
            id=view_id,
            user_id=test_user.id,
            recipe_id=test_recipe.id,
        ))
        db_session.commit()

        db_session.delete(test_recipe)
        db_session.commit()

        assert db_session.get(UserRecipeView, view_id) is None


# ---------------------------------------------------------------------------
# Registration / metadata tests
# ---------------------------------------------------------------------------

class TestModelsRegistered:
    """Both tables must be visible in Base.metadata."""

    def test_both_tables_in_metadata(self):
        """user_cook_events and user_recipe_views appear in Base.metadata.tables."""
        assert "user_cook_events" in Base.metadata.tables
        assert "user_recipe_views" in Base.metadata.tables
