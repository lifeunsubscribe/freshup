"""
Integration tests for meal plan endpoints.

Tests cover:
- POST /plan/draft/generate: Auto-draft meal plan generation
- GET /plan/week: Weekly plan viewing with status separation
- PUT /plan/entries/{id}/confirm: Entry confirmation with grocery list propagation
- Authentication requirements
- Validation scenarios
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from datetime import date, timedelta, datetime

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.inventory_item import InventoryItem
from src.db.models.meal_plan import MealPlanEntry, MealPlanStatus, MealType
from src.db.models.grocery_list import GroceryListItem
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import plan as plan_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the plan router
app.include_router(plan_router.router)


# Create an in-memory SQLite database for testing
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
    """Create a fresh database session for each test."""
    from sqlalchemy.pool import StaticPool

    # Import models to ensure all SQLAlchemy model classes are registered
    # with Base.metadata before create_all() is called
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
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate auth headers with valid token."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def recipes_pool(db_session, test_user):
    """Create a pool of recipes for meal planning."""
    recipes = []
    for i in range(10):
        recipe = Recipe(
            id=uuid4(),
            name=f"Test Recipe {i}",
            source_type="manual",
            base_servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            times_cooked=i,  # Varying popularity
            is_persisted=True,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        recipes.append(recipe)

    db_session.commit()
    for recipe in recipes:
        db_session.refresh(recipe)

    # Add ingredients to first recipe for grocery list propagation
    ingredient = RecipeIngredient(
        id=uuid4(),
        recipe_id=recipes[0].id,
        ingredient_name="Test Ingredient",
        quantity=2.0,
        unit="cups",
        is_optional=False,
    )
    db_session.add(ingredient)
    db_session.commit()

    return recipes


def test_generate_draft_creates_seven_entries(client, db_session, auth_headers, recipes_pool):
    """Test that draft generation creates 7 dinner entries."""
    # Use fixed Monday date to avoid flakiness around week boundaries
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["entries_created"] == 7
    assert data["week_start"] == week_start.isoformat()
    assert len(data["entries"]) == 7

    # Verify all entries are drafts for dinner
    for entry in data["entries"]:
        assert entry["status"] == MealPlanStatus.draft.value
        assert entry["meal_type"] == MealType.dinner.value


def test_generate_draft_requires_monday(client, auth_headers, recipes_pool):
    """Test that draft generation requires week_start to be a Monday."""
    # Use fixed Tuesday date to avoid flakiness
    week_start = date(2025, 6, 3)  # Tuesday, June 3, 2025

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 422  # Validation error


def test_generate_draft_fails_without_enough_recipes(client, db_session, auth_headers, test_user):
    """Test that draft generation fails if fewer than 7 recipes available."""
    # Create only 3 recipes
    for i in range(3):
        recipe = Recipe(
            id=uuid4(),
            name=f"Test Recipe {i}",
            source_type="manual",
            base_servings=4,
            is_persisted=True,
            created_by=test_user.id,
        )
        db_session.add(recipe)
    db_session.commit()

    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Insufficient recipes" in response.json()["detail"]


def test_get_week_returns_empty_for_new_week(client, auth_headers):
    """Test that getting a week with no entries returns empty lists."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["week_start"] == week_start.isoformat()
    assert data["confirmed_entries"] == []
    assert data["draft_entries"] == []


def test_get_week_separates_by_status(client, db_session, auth_headers, recipes_pool):
    """Test that week view separates entries by status."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    # Create draft entry
    draft_entry = MealPlanEntry(
        id=uuid4(),
        date=week_start,
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(draft_entry)

    # Create confirmed entry
    confirmed_entry = MealPlanEntry(
        id=uuid4(),
        date=week_start + timedelta(days=1),
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[1].id,
        planned_servings=4,
        status=MealPlanStatus.approved.value,
    )
    db_session.add(confirmed_entry)
    db_session.commit()

    response = client.get(
        f"/plan/week?week_start={week_start.isoformat()}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["draft_entries"]) == 1
    assert len(data["confirmed_entries"]) == 1
    assert data["draft_entries"][0]["status"] == MealPlanStatus.draft.value
    assert data["confirmed_entries"][0]["status"] == MealPlanStatus.approved.value


def test_confirm_entry_transitions_to_approved(client, db_session, auth_headers, recipes_pool):
    """Test that confirming an entry transitions it to approved status."""
    # Create a draft entry with a recipe that has ingredients
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Fixed date to avoid flakiness
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,  # Has ingredient from fixture
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()

    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["entry"]["status"] == MealPlanStatus.approved.value
    assert data["grocery_items_added"] > 0  # At least one ingredient added


def test_confirm_entry_adds_ingredients_to_grocery_list(client, db_session, auth_headers, recipes_pool, test_user):
    """Test that confirming an entry adds recipe ingredients to grocery list."""
    # Create a draft entry
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Fixed date to avoid flakiness
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.draft.value,
    )
    db_session.add(entry)
    db_session.commit()

    # Verify no grocery items exist before confirmation
    grocery_count_before = db_session.query(GroceryListItem).count()
    assert grocery_count_before == 0

    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 200

    # Verify grocery items were created
    grocery_items = db_session.query(GroceryListItem).all()
    assert len(grocery_items) > 0
    assert grocery_items[0].source == "meal_plan"


def test_confirm_entry_fails_for_nonexistent_entry(client, auth_headers):
    """Test that confirming a non-existent entry returns 404."""
    fake_id = uuid4()
    response = client.put(
        f"/plan/entries/{fake_id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_confirm_entry_fails_for_already_confirmed(client, db_session, auth_headers, recipes_pool):
    """Test that confirming an already-confirmed entry fails."""
    # Create an already-confirmed entry
    entry = MealPlanEntry(
        id=uuid4(),
        date=date(2025, 6, 2),  # Fixed date to avoid flakiness
        meal_type=MealType.dinner.value,
        recipe_id=recipes_pool[0].id,
        planned_servings=4,
        status=MealPlanStatus.approved.value,
    )
    db_session.add(entry)
    db_session.commit()

    response = client.put(
        f"/plan/entries/{entry.id}/confirm",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Only draft entries can be confirmed" in response.json()["detail"]


def test_endpoints_require_authentication(client):
    """Test that all endpoints require authentication."""
    # Use fixed Monday date to avoid flakiness
    week_start = date(2025, 6, 2)  # Monday, June 2, 2025

    # Test draft generation
    response = client.post(
        "/plan/draft/generate",
        json={"week_start": week_start.isoformat()},
    )
    assert response.status_code == 401

    # Test week view
    response = client.get(f"/plan/week?week_start={week_start.isoformat()}")
    assert response.status_code == 401

    # Test confirm entry
    fake_id = uuid4()
    response = client.put(f"/plan/entries/{fake_id}/confirm")
    assert response.status_code == 401
