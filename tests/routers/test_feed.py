"""
Integration tests for feed endpoints.

Tests cover:
- GET /feed/home: personalized home feed with make_now and on_repeat sections
- Make This Right Now: inventory-aware recipe recommendations
- On Repeat: behavioral signal-based recommendations
- Authentication requirements
- Cold start scenarios (empty results)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from datetime import datetime, timedelta

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.inventory_item import InventoryItem
from src.db.models.user_recipe import UserRecipeRating
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import feed as feed_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the feed router
app.include_router(feed_router.router)


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
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        name="Test User",
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate authorization headers for test user."""
    access_token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {access_token}"}


class TestHomeFeed:
    """Test home feed endpoint."""

    def test_home_feed_requires_authentication(self, client):
        """Test that home feed endpoint requires authentication."""
        response = client.get("/feed/home")
        assert response.status_code == 401

    def test_home_feed_empty_cold_start(self, client, auth_headers, test_user, db_session):
        """Test home feed returns empty sections when user has no data (cold start)."""
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have both sections
        assert "make_now" in data
        assert "on_repeat" in data

        # Sections should have titles and empty recipe lists
        assert data["make_now"]["title"] == "Make This Right Now"
        assert data["make_now"]["recipes"] == []

        assert data["on_repeat"]["title"] == "On Repeat"
        assert data["on_repeat"]["recipes"] == []

    def test_make_now_returns_recipes_with_full_inventory(self, client, auth_headers, test_user, db_session):
        """Test Make This Right Now returns recipes where user has 100% of ingredients."""
        # Create a persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Pasta Carbonara",
            source_type="manual",
            is_persisted=True,
            times_cooked=5,
            created_by=test_user.id
        )
        db_session.add(recipe)
        db_session.commit()

        # Add required ingredients to recipe
        ingredient1 = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Spaghetti",
            quantity=200,
            unit="g",
            is_optional=False
        )
        ingredient2 = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Bacon",
            quantity=100,
            unit="g",
            is_optional=False
        )
        db_session.add_all([ingredient1, ingredient2])
        db_session.commit()

        # Add matching inventory items for user
        inventory1 = InventoryItem(
            id=uuid4(),
            name="Spaghetti",
            quantity=500,
            unit="g",
            category="grain",
            storage_location="pantry",
            added_by=test_user.id
        )
        inventory2 = InventoryItem(
            id=uuid4(),
            name="Bacon",
            quantity=200,
            unit="g",
            category="protein",
            storage_location="fridge",
            added_by=test_user.id
        )
        db_session.add_all([inventory1, inventory2])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have the recipe in make_now section
        assert len(data["make_now"]["recipes"]) == 1
        assert data["make_now"]["recipes"][0]["name"] == "Pasta Carbonara"
        assert data["make_now"]["recipes"][0]["times_cooked"] == 5

    def test_make_now_excludes_recipes_with_partial_inventory(self, client, auth_headers, test_user, db_session):
        """Test Make This Right Now excludes recipes when user is missing ingredients."""
        # Create a persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Incomplete Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=3,
            created_by=test_user.id
        )
        db_session.add(recipe)
        db_session.commit()

        # Add required ingredients to recipe
        ingredient1 = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Ingredient A",
            quantity=100,
            unit="g",
            is_optional=False
        )
        ingredient2 = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Ingredient B",
            quantity=100,
            unit="g",
            is_optional=False
        )
        db_session.add_all([ingredient1, ingredient2])
        db_session.commit()

        # Only add ONE inventory item (missing Ingredient B)
        inventory1 = InventoryItem(
            id=uuid4(),
            name="Ingredient A",
            quantity=200,
            unit="g",
            category="pantry_staple",
            storage_location="pantry",
            added_by=test_user.id
        )
        db_session.add(inventory1)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Recipe should NOT appear in make_now (missing ingredient)
        assert len(data["make_now"]["recipes"]) == 0

    def test_make_now_ignores_optional_ingredients(self, client, auth_headers, test_user, db_session):
        """Test Make This Right Now only checks required ingredients, not optional ones."""
        # Create a persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Recipe with Optional",
            source_type="manual",
            is_persisted=True,
            times_cooked=2,
            created_by=test_user.id
        )
        db_session.add(recipe)
        db_session.commit()

        # Add required and optional ingredients
        required_ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Required Item",
            quantity=100,
            unit="g",
            is_optional=False
        )
        optional_ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Optional Garnish",
            quantity=10,
            unit="g",
            is_optional=True
        )
        db_session.add_all([required_ingredient, optional_ingredient])
        db_session.commit()

        # Only add the required ingredient to inventory (skip optional)
        inventory = InventoryItem(
            id=uuid4(),
            name="Required Item",
            quantity=200,
            unit="g",
            category="pantry_staple",
            storage_location="pantry",
            added_by=test_user.id
        )
        db_session.add(inventory)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Recipe SHOULD appear (has all required ingredients)
        assert len(data["make_now"]["recipes"]) == 1
        assert data["make_now"]["recipes"][0]["name"] == "Recipe with Optional"

    def test_make_now_sorts_by_freshness_then_popularity(self, client, auth_headers, test_user, db_session):
        """Test Make This Right Now sorts by ingredient freshness (expiration) then times_cooked."""
        # Create two persisted recipes
        recipe1 = Recipe(
            id=uuid4(),
            name="Fresh Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=1,
            created_by=test_user.id
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Popular Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=10,
            created_by=test_user.id
        )
        db_session.add_all([recipe1, recipe2])
        db_session.commit()

        # Recipe 1: ingredient expiring soon
        ingredient1 = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe1.id,
            ingredient_name="Milk",
            quantity=100,
            unit="ml",
            is_optional=False
        )
        # Recipe 2: ingredient not expiring
        ingredient2 = RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe2.id,
            ingredient_name="Rice",
            quantity=100,
            unit="g",
            is_optional=False
        )
        db_session.add_all([ingredient1, ingredient2])
        db_session.commit()

        # Add inventory with expiration dates
        inventory1 = InventoryItem(
            id=uuid4(),
            name="Milk",
            quantity=500,
            unit="ml",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
            expiration_date=datetime.now() + timedelta(days=2)  # Expires soon
        )
        inventory2 = InventoryItem(
            id=uuid4(),
            name="Rice",
            quantity=1000,
            unit="g",
            category="grain",
            storage_location="pantry",
            added_by=test_user.id,
            expiration_date=None  # No expiration
        )
        db_session.add_all([inventory1, inventory2])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have both recipes
        assert len(data["make_now"]["recipes"]) == 2

        # Fresh Recipe should come first (earlier expiration)
        assert data["make_now"]["recipes"][0]["name"] == "Fresh Recipe"
        # Popular Recipe should come second
        assert data["make_now"]["recipes"][1]["name"] == "Popular Recipe"

    def test_on_repeat_returns_recently_rated_recipes(self, client, auth_headers, test_user, db_session):
        """Test On Repeat returns recipes based on recent ratings."""
        # Create persisted recipes
        recipe1 = Recipe(
            id=uuid4(),
            name="Recently Rated Recipe",
            source_type="manual",
            is_persisted=True,
            created_by=test_user.id
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Older Rated Recipe",
            source_type="manual",
            is_persisted=True,
            created_by=test_user.id
        )
        db_session.add_all([recipe1, recipe2])
        db_session.commit()

        # Add ratings with different timestamps
        rating1 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe1.id,
            rating=5.0,
            created_at=datetime.now() - timedelta(days=1),
            updated_at=datetime.now() - timedelta(hours=1)  # Updated recently
        )
        rating2 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe2.id,
            rating=4.0,
            created_at=datetime.now() - timedelta(days=10),
            updated_at=datetime.now() - timedelta(days=10)  # Updated long ago
        )
        db_session.add_all([rating1, rating2])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have both recipes in on_repeat
        assert len(data["on_repeat"]["recipes"]) == 2

        # Recently rated should come first
        assert data["on_repeat"]["recipes"][0]["name"] == "Recently Rated Recipe"
        assert data["on_repeat"]["recipes"][1]["name"] == "Older Rated Recipe"

    def test_on_repeat_empty_when_no_ratings(self, client, auth_headers, test_user, db_session):
        """Test On Repeat returns empty when user has no ratings (cold start)."""
        # Create a persisted recipe but no ratings
        recipe = Recipe(
            id=uuid4(),
            name="Unrated Recipe",
            source_type="manual",
            is_persisted=True,
            created_by=test_user.id
        )
        db_session.add(recipe)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # On Repeat should be empty (no ratings yet)
        assert len(data["on_repeat"]["recipes"]) == 0
