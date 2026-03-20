"""
Integration tests for recipe endpoints.

Tests cover:
- POST /recipes: create recipes with nested ingredients
- GET /recipes: list all recipes with pagination (global read)
- GET /recipes/{id}: get single recipe with ingredients (global read)
- PUT /recipes/{id}: update recipes with ownership validation
- DELETE /recipes/{id}: delete recipes with ownership validation
- Cross-user access prevention (returns 404 for non-owned recipes)
- System recipe protection (created_by=NULL cannot be edited/deleted)
- Authentication requirements
- Validation (source_type, quantities, etc.)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from datetime import datetime, timezone

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import recipes_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the recipes router
app.include_router(recipes_router)


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
def test_user2(db_session):
    """Create a second test user for cross-user access tests."""
    user = User(
        id=uuid4(),
        email="test2@example.com",
        hashed_password=hash_password("testpassword123"),
        name="Test User 2",
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


@pytest.fixture
def auth_headers2(test_user2):
    """Generate authorization headers for test user 2."""
    access_token = create_access_token({"sub": str(test_user2.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_recipe(db_session, test_user):
    """Create a test recipe owned by test_user."""
    recipe = Recipe(
        id=uuid4(),
        name="Test Recipe",
        source_type="manual",
        base_servings=4,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def test_recipe_with_ingredients(db_session, test_user):
    """Create a test recipe with ingredients owned by test_user."""
    recipe = Recipe(
        id=uuid4(),
        name="Pasta Carbonara",
        source_type="manual",
        base_servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.flush()

    ingredients = [
        RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Pasta",
            quantity=400,
            unit="g",
        ),
        RecipeIngredient(
            id=uuid4(),
            recipe_id=recipe.id,
            ingredient_name="Eggs",
            quantity=4,
            unit="whole",
        ),
    ]
    for ing in ingredients:
        db_session.add(ing)

    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def system_recipe(db_session):
    """Create a system recipe (created_by=NULL)."""
    recipe = Recipe(
        id=uuid4(),
        name="System Recipe",
        source_type="hellofresh_card",
        base_servings=2,
        created_by=None,  # System recipe
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


class TestCreateRecipe:
    """Tests for POST /recipes (create recipe)."""

    def test_create_recipe_success(self, client, auth_headers, test_user, db_session):
        """Should create recipe with nested ingredients and auto-set created_by."""
        payload = {
            "name": "Test Recipe",
            "source_type": "manual",
            "base_servings": 4,
            "ingredients": [
                {"ingredient_name": "Flour", "quantity": 500, "unit": "g"},
                {"ingredient_name": "Sugar", "quantity": 200, "unit": "g"},
            ]
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Recipe"
        assert data["source_type"] == "manual"
        assert data["base_servings"] == 4
        assert data["created_by"] == str(test_user.id)
        assert len(data["ingredients"]) == 2
        assert data["ingredients"][0]["ingredient_name"] == "Flour"
        assert data["ingredients"][0]["quantity"] == 500
        assert data["ingredients"][1]["ingredient_name"] == "Sugar"

    def test_create_recipe_without_ingredients(self, client, auth_headers, test_user):
        """Should create recipe without ingredients."""
        payload = {
            "name": "Simple Recipe",
            "source_type": "manual",
            "ingredients": []
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Simple Recipe"
        assert len(data["ingredients"]) == 0

    def test_create_recipe_with_optional_fields(self, client, auth_headers, test_user):
        """Should create recipe with all optional fields."""
        payload = {
            "name": "Complex Recipe",
            "source_type": "manual",
            "source_url": "https://example.com/recipe",
            "source_image": "https://example.com/image.jpg",
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "base_servings": 6,
            "steps": ["Step 1", "Step 2"],
            "tags": ["italian", "pasta"],
            "notes": "My favorite recipe",
            "ingredients": []
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["source_url"] == "https://example.com/recipe"
        assert data["prep_time_minutes"] == 15
        assert data["cook_time_minutes"] == 30
        assert data["base_servings"] == 6
        assert data["steps"] == ["Step 1", "Step 2"]
        assert data["tags"] == ["italian", "pasta"]
        assert data["notes"] == "My favorite recipe"

    def test_create_recipe_invalid_source_type(self, client, auth_headers):
        """Should reject invalid source_type."""
        payload = {
            "name": "Test Recipe",
            "source_type": "invalid_source",
            "ingredients": []
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_recipe_negative_prep_time(self, client, auth_headers):
        """Should reject negative prep_time_minutes."""
        payload = {
            "name": "Test Recipe",
            "source_type": "manual",
            "prep_time_minutes": -10,
            "ingredients": []
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_recipe_zero_servings(self, client, auth_headers):
        """Should reject zero base_servings."""
        payload = {
            "name": "Test Recipe",
            "source_type": "manual",
            "base_servings": 0,
            "ingredients": []
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_recipe_zero_quantity_ingredient(self, client, auth_headers):
        """Should reject ingredient with zero quantity."""
        payload = {
            "name": "Test Recipe",
            "source_type": "manual",
            "ingredients": [
                {"ingredient_name": "Flour", "quantity": 0, "unit": "g"}
            ]
        }

        response = client.post("/recipes", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_recipe_unauthenticated(self, client):
        """Should reject unauthenticated request."""
        payload = {
            "name": "Test Recipe",
            "source_type": "manual",
            "ingredients": []
        }

        response = client.post("/recipes", json=payload)

        assert response.status_code == 401


class TestListRecipes:
    """Tests for GET /recipes (list recipes)."""

    def test_list_recipes_empty(self, client):
        """Should return empty list when no recipes exist."""
        response = client.get("/recipes")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_recipes_no_auth_required(self, client, db_session, test_user):
        """Should return recipes without authentication (global read)."""
        recipe = Recipe(
            id=uuid4(),
            name="Public Recipe",
            source_type="manual",
            base_servings=4,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()

        response = client.get("/recipes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Public Recipe"

    def test_list_recipes_pagination(self, client, db_session, test_user):
        """Should paginate results with limit and offset."""
        # Create 5 recipes
        for i in range(5):
            recipe = Recipe(
                id=uuid4(),
                name=f"Recipe {i}",
                source_type="manual",
                base_servings=4,
                created_by=test_user.id,
            )
            db_session.add(recipe)
        db_session.commit()

        # Get first 2
        response = client.get("/recipes?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Get next 2
        response = client.get("/recipes?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_recipes_respects_limit(self, client, db_session, test_user):
        """Should respect limit parameter."""
        # Create 10 recipes
        for i in range(10):
            recipe = Recipe(
                id=uuid4(),
                name=f"Recipe {i}",
                source_type="manual",
                base_servings=4,
                created_by=test_user.id,
            )
            db_session.add(recipe)
        db_session.commit()

        response = client.get("/recipes?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5


class TestGetRecipe:
    """Tests for GET /recipes/{id} (get single recipe)."""

    def test_get_recipe_success(self, client, test_recipe_with_ingredients):
        """Should return recipe with nested ingredients (no auth required)."""
        response = client.get(f"/recipes/{test_recipe_with_ingredients.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Pasta Carbonara"
        assert data["source_type"] == "manual"
        assert data["prep_time_minutes"] == 10
        assert data["cook_time_minutes"] == 20
        assert len(data["ingredients"]) == 2
        assert data["ingredients"][0]["ingredient_name"] == "Pasta"
        assert data["ingredients"][0]["quantity"] == 400

    def test_get_recipe_not_found(self, client):
        """Should return 404 for non-existent recipe."""
        fake_id = uuid4()
        response = client.get(f"/recipes/{fake_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_get_system_recipe(self, client, system_recipe):
        """Should return system recipe (created_by=NULL)."""
        response = client.get(f"/recipes/{system_recipe.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "System Recipe"
        assert data["created_by"] is None


class TestUpdateRecipe:
    """Tests for PUT /recipes/{id} (update recipe)."""

    def test_update_recipe_success(self, client, auth_headers, test_recipe):
        """Should update recipe owned by current user."""
        payload = {
            "name": "Updated Recipe Name",
            "prep_time_minutes": 15
        }

        response = client.put(f"/recipes/{test_recipe.id}", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Recipe Name"
        assert data["prep_time_minutes"] == 15

    def test_update_recipe_partial(self, client, auth_headers, test_recipe):
        """Should support partial updates."""
        original_name = test_recipe.name

        payload = {"prep_time_minutes": 20}

        response = client.put(f"/recipes/{test_recipe.id}", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == original_name  # Unchanged
        assert data["prep_time_minutes"] == 20

    def test_update_recipe_cross_user_returns_404(self, client, auth_headers2, test_recipe):
        """Should return 404 when trying to update another user's recipe."""
        payload = {"name": "Hacked Recipe"}

        response = client.put(f"/recipes/{test_recipe.id}", json=payload, headers=auth_headers2)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_update_system_recipe_returns_404(self, client, auth_headers, system_recipe):
        """Should return 404 when trying to update system recipe."""
        payload = {"name": "Hacked System Recipe"}

        response = client.put(f"/recipes/{system_recipe.id}", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_update_recipe_not_found(self, client, auth_headers):
        """Should return 404 for non-existent recipe."""
        fake_id = uuid4()
        payload = {"name": "Updated"}

        response = client.put(f"/recipes/{fake_id}", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_update_recipe_unauthenticated(self, client, test_recipe):
        """Should reject unauthenticated update request."""
        payload = {"name": "Hacked"}

        response = client.put(f"/recipes/{test_recipe.id}", json=payload)

        assert response.status_code == 401

    def test_update_recipe_invalid_source_type(self, client, auth_headers, test_recipe):
        """Should reject invalid source_type."""
        payload = {"source_type": "invalid_source"}

        response = client.put(f"/recipes/{test_recipe.id}", json=payload, headers=auth_headers)

        assert response.status_code == 422


class TestDeleteRecipe:
    """Tests for DELETE /recipes/{id} (delete recipe)."""

    def test_delete_recipe_success(self, client, auth_headers, test_recipe, db_session):
        """Should delete recipe owned by current user."""
        recipe_id = test_recipe.id

        response = client.delete(f"/recipes/{recipe_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify recipe is deleted
        deleted_recipe = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert deleted_recipe is None

    def test_delete_recipe_with_ingredients(self, client, auth_headers, test_recipe_with_ingredients, db_session):
        """Should delete recipe and cascade delete ingredients."""
        recipe_id = test_recipe_with_ingredients.id

        # Verify ingredients exist before deletion
        ingredients_before = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        assert len(ingredients_before) == 2

        response = client.delete(f"/recipes/{recipe_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify recipe is deleted
        deleted_recipe = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert deleted_recipe is None

        # Verify ingredients are cascade deleted
        ingredients_after = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        assert len(ingredients_after) == 0

    def test_delete_recipe_cross_user_returns_404(self, client, auth_headers2, test_recipe, db_session):
        """Should return 404 when trying to delete another user's recipe."""
        recipe_id = test_recipe.id

        response = client.delete(f"/recipes/{recipe_id}", headers=auth_headers2)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

        # Verify recipe still exists
        recipe = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert recipe is not None

    def test_delete_system_recipe_returns_404(self, client, auth_headers, system_recipe, db_session):
        """Should return 404 when trying to delete system recipe."""
        recipe_id = system_recipe.id

        response = client.delete(f"/recipes/{recipe_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

        # Verify system recipe still exists
        recipe = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert recipe is not None

    def test_delete_recipe_not_found(self, client, auth_headers):
        """Should return 404 for non-existent recipe."""
        fake_id = uuid4()

        response = client.delete(f"/recipes/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_delete_recipe_unauthenticated(self, client, test_recipe):
        """Should reject unauthenticated delete request."""
        response = client.delete(f"/recipes/{test_recipe.id}")

        assert response.status_code == 401
