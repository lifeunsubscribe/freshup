"""
Integration tests for recipe endpoints.

Tests cover:
- POST /recipes: create recipes with validation
- GET /recipes: list user recipes with filtering and pagination
- GET /recipes/{id}: get single recipe
- PUT /recipes/{id}: update recipes with partial data
- DELETE /recipes/{id}: delete recipe
- Filtering: source_type, tag, max_cook_time, max_prep_time, search, has_variation
- Cross-user access prevention
- Authentication requirements
- Validation (source_type, times, servings, etc.)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import recipes as recipes_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the recipes router
app.include_router(recipes_router.router)


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


class TestRecipeCRUD:
    """Test basic recipe CRUD operations."""

    def test_create_recipe_success(self, client, auth_headers, test_user, db_session):
        """Test creating a recipe successfully."""
        recipe_data = {
            "name": "Spaghetti Carbonara",
            "source_type": "manual",
            "prep_time_minutes": 10,
            "cook_time_minutes": 20,
            "base_servings": 4,
            "tags": ["italian", "pasta"],
            "steps": ["Cook pasta", "Make sauce", "Combine"],
        }

        response = client.post("/recipes", json=recipe_data, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Spaghetti Carbonara"
        assert data["source_type"] == "manual"
        assert data["prep_time_minutes"] == 10
        assert data["cook_time_minutes"] == 20
        assert data["base_servings"] == 4
        assert data["tags"] == ["italian", "pasta"]
        assert data["created_by"] == str(test_user.id)
        assert "id" in data

    def test_create_recipe_invalid_source_type(self, client, auth_headers):
        """Test creating recipe with invalid source_type fails."""
        recipe_data = {
            "name": "Test Recipe",
            "source_type": "invalid_source",
        }

        response = client.post("/recipes", json=recipe_data, headers=auth_headers)

        assert response.status_code == 422

    def test_create_recipe_unauthenticated(self, client):
        """Test creating recipe without auth fails."""
        recipe_data = {
            "name": "Test Recipe",
            "source_type": "manual",
        }

        response = client.post("/recipes", json=recipe_data)

        assert response.status_code == 401

    def test_list_recipes_empty(self, client, auth_headers):
        """Test listing recipes when user has none."""
        response = client.get("/recipes", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_recipes_with_data(self, client, auth_headers, test_user, db_session):
        """Test listing recipes returns user's recipes."""
        # Create test recipes
        recipe1 = Recipe(
            id=uuid4(),
            name="Recipe 1",
            source_type="manual",
            created_by=test_user.id,
            tags=["tag1"],
            steps=[],
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Recipe 2",
            source_type="hellofresh_card",
            created_by=test_user.id,
            tags=["tag2"],
            steps=[],
        )
        db_session.add_all([recipe1, recipe2])
        db_session.commit()

        response = client.get("/recipes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(r["name"] == "Recipe 1" for r in data)
        assert any(r["name"] == "Recipe 2" for r in data)

    def test_get_recipe_success(self, client, auth_headers, test_user, db_session):
        """Test getting a single recipe by ID."""
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            created_by=test_user.id,
            prep_time_minutes=15,
            cook_time_minutes=30,
            tags=["test"],
            steps=["step1"],
        )
        db_session.add(recipe)
        db_session.commit()

        response = client.get(f"/recipes/{recipe.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(recipe.id)
        assert data["name"] == "Test Recipe"
        assert data["prep_time_minutes"] == 15
        assert data["cook_time_minutes"] == 30

    def test_get_recipe_not_found(self, client, auth_headers):
        """Test getting non-existent recipe returns 404."""
        fake_id = uuid4()
        response = client.get(f"/recipes/{fake_id}", headers=auth_headers)

        assert response.status_code == 404

    def test_get_recipe_cross_user_access_denied(self, client, auth_headers, auth_headers2, test_user2, db_session):
        """Test user cannot access another user's recipe."""
        # Create recipe for user2
        recipe = Recipe(
            id=uuid4(),
            name="User2 Recipe",
            source_type="manual",
            created_by=test_user2.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()

        # Try to access with user1's token
        response = client.get(f"/recipes/{recipe.id}", headers=auth_headers)

        assert response.status_code == 404

    def test_update_recipe_success(self, client, auth_headers, test_user, db_session):
        """Test updating a recipe."""
        recipe = Recipe(
            id=uuid4(),
            name="Original Name",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()

        update_data = {
            "name": "Updated Name",
            "prep_time_minutes": 20,
        }

        response = client.put(f"/recipes/{recipe.id}", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["prep_time_minutes"] == 20

    def test_delete_recipe_success(self, client, auth_headers, test_user, db_session):
        """Test deleting a recipe."""
        recipe = Recipe(
            id=uuid4(),
            name="To Delete",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()
        recipe_id = recipe.id

        response = client.delete(f"/recipes/{recipe_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify recipe is deleted
        deleted_recipe = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert deleted_recipe is None


class TestRecipeFiltering:
    """Test recipe list filtering functionality."""

    @pytest.fixture
    def sample_recipes(self, test_user, db_session):
        """Create sample recipes for filtering tests."""
        recipes = [
            Recipe(
                id=uuid4(),
                name="Quick Tacos",
                source_type="manual",
                created_by=test_user.id,
                prep_time_minutes=10,
                cook_time_minutes=15,
                tags=["mexican", "quick"],
                steps=["step1"],
            ),
            Recipe(
                id=uuid4(),
                name="Slow Curry",
                source_type="hellofresh_card",
                created_by=test_user.id,
                prep_time_minutes=20,
                cook_time_minutes=60,
                tags=["indian", "curry"],
                steps=["step1"],
            ),
            Recipe(
                id=uuid4(),
                name="Fast Pasta",
                source_type="manual",
                created_by=test_user.id,
                prep_time_minutes=5,
                cook_time_minutes=10,
                tags=["italian", "pasta", "quick"],
                steps=["step1"],
            ),
            Recipe(
                id=uuid4(),
                name="Curry Pizza",
                source_type="url_import",
                created_by=test_user.id,
                prep_time_minutes=15,
                cook_time_minutes=25,
                tags=["fusion"],
                steps=["step1"],
                variation_groups={"size": ["small", "large"]},
            ),
            Recipe(
                id=uuid4(),
                name="Simple Salad",
                source_type="manual",
                created_by=test_user.id,
                prep_time_minutes=10,
                cook_time_minutes=None,  # No cooking required
                tags=["healthy", "vegetarian"],
                steps=["step1"],
            ),
        ]
        db_session.add_all(recipes)
        db_session.commit()
        return recipes

    def test_filter_by_source_type_manual(self, client, auth_headers, sample_recipes):
        """Test filtering by source_type=manual."""
        response = client.get("/recipes?source_type=manual", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # Quick Tacos, Fast Pasta, Simple Salad
        assert all(r["source_type"] == "manual" for r in data)

    def test_filter_by_source_type_hellofresh(self, client, auth_headers, sample_recipes):
        """Test filtering by source_type=hellofresh_card."""
        response = client.get("/recipes?source_type=hellofresh_card", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Slow Curry
        assert data[0]["source_type"] == "hellofresh_card"

    def test_filter_by_invalid_source_type(self, client, auth_headers, sample_recipes):
        """Test filtering by invalid source_type returns 422."""
        response = client.get("/recipes?source_type=invalid", headers=auth_headers)

        assert response.status_code == 422
        assert "Invalid source_type" in response.json()["detail"]

    def test_filter_by_tag_mexican(self, client, auth_headers, sample_recipes):
        """Test filtering by tag=mexican."""
        response = client.get("/recipes?tag=mexican", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Quick Tacos
        assert "mexican" in data[0]["tags"]

    def test_filter_by_tag_quick(self, client, auth_headers, sample_recipes):
        """Test filtering by tag=quick (matches multiple)."""
        response = client.get("/recipes?tag=quick", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # Quick Tacos, Fast Pasta
        assert all("quick" in r["tags"] for r in data)

    def test_filter_by_tag_case_insensitive(self, client, auth_headers, sample_recipes):
        """Test tag filtering is case-insensitive."""
        response = client.get("/recipes?tag=MEXICAN", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Quick Tacos

    def test_filter_by_max_cook_time(self, client, auth_headers, sample_recipes):
        """Test filtering by max_cook_time=30."""
        response = client.get("/recipes?max_cook_time=30", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should return: Quick Tacos (15), Fast Pasta (10), Curry Pizza (25)
        # Should exclude: Slow Curry (60), Simple Salad (None)
        assert len(data) == 3
        assert all(r["cook_time_minutes"] is not None and r["cook_time_minutes"] <= 30 for r in data)

    def test_filter_by_max_cook_time_15(self, client, auth_headers, sample_recipes):
        """Test filtering by max_cook_time=15."""
        response = client.get("/recipes?max_cook_time=15", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should return: Quick Tacos (15), Fast Pasta (10)
        assert len(data) == 2

    def test_filter_by_max_prep_time(self, client, auth_headers, sample_recipes):
        """Test filtering by max_prep_time=15."""
        response = client.get("/recipes?max_prep_time=15", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should return: Quick Tacos (10), Fast Pasta (5), Curry Pizza (15), Simple Salad (10)
        assert len(data) == 4
        assert all(r["prep_time_minutes"] is not None and r["prep_time_minutes"] <= 15 for r in data)

    def test_filter_by_search_curry(self, client, auth_headers, sample_recipes):
        """Test search by name=curry (case-insensitive partial match)."""
        response = client.get("/recipes?search=curry", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should return: Slow Curry, Curry Pizza
        assert len(data) == 2
        assert all("curry" in r["name"].lower() for r in data)

    def test_filter_by_search_case_insensitive(self, client, auth_headers, sample_recipes):
        """Test search is case-insensitive."""
        response = client.get("/recipes?search=PASTA", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Fast Pasta
        assert "pasta" in data[0]["name"].lower()

    def test_filter_by_search_escapes_wildcards(self, client, auth_headers, test_user, db_session):
        """Test search escapes LIKE wildcards to prevent DoS."""
        # Create recipe with special chars in name
        recipe = Recipe(
            id=uuid4(),
            name="Test_Recipe%With%Special",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()

        # Search for literal % character (need at least 2 chars due to min_length validation)
        response = client.get("/recipes?search=%25W", headers=auth_headers)  # %25 is URL-encoded %, search for "%W"

        assert response.status_code == 200
        data = response.json()
        # Should match the recipe with %W in name
        assert len(data) == 1
        assert "%W" in data[0]["name"]

    def test_filter_by_search_minimum_length_validation(self, client, auth_headers, sample_recipes):
        """Test search parameter requires minimum 2 characters."""
        # Search with only 1 character should fail validation
        response = client.get("/recipes?search=a", headers=auth_headers)

        assert response.status_code == 422
        detail = response.json()["detail"]
        # FastAPI validation error for min_length constraint
        assert any("at least 2 characters" in str(error).lower() or "min_length" in str(error).lower()
                   for error in detail)

    def test_filter_by_has_variation_true(self, client, auth_headers, sample_recipes):
        """Test filtering by has_variation=true."""
        response = client.get("/recipes?has_variation=true", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Only Curry Pizza has variation_groups
        assert len(data) == 1
        assert data[0]["name"] == "Curry Pizza"

    def test_filter_by_has_variation_false(self, client, auth_headers, sample_recipes):
        """Test filtering by has_variation=false."""
        response = client.get("/recipes?has_variation=false", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # All except Curry Pizza
        assert len(data) == 4

    def test_combined_filters_and_logic(self, client, auth_headers, sample_recipes):
        """Test multiple filters combine with AND logic."""
        # Filter: source_type=manual AND tag=quick AND max_cook_time=20
        response = client.get(
            "/recipes?source_type=manual&tag=quick&max_cook_time=20",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Should return: Quick Tacos (manual, quick, 15min), Fast Pasta (manual, quick, 10min)
        assert len(data) == 2
        assert all(r["source_type"] == "manual" for r in data)
        assert all("quick" in r["tags"] for r in data)
        assert all(r["cook_time_minutes"] <= 20 for r in data)

    def test_combined_filters_narrow_results(self, client, auth_headers, sample_recipes):
        """Test multiple filters narrow down results progressively."""
        # Filter: tag=quick AND max_prep_time=8
        response = client.get(
            "/recipes?tag=quick&max_prep_time=8",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Only Fast Pasta (quick, 5min prep)
        assert len(data) == 1
        assert data[0]["name"] == "Fast Pasta"

    def test_pagination_with_filters(self, client, auth_headers, sample_recipes):
        """Test pagination works with filters."""
        response = client.get(
            "/recipes?source_type=manual&limit=2&offset=0",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # First 2 of 3 manual recipes

        # Get next page
        response = client.get(
            "/recipes?source_type=manual&limit=2&offset=2",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Remaining 1 manual recipe


class TestRecipeIngredientCRUD:
    """Test recipe ingredient CRUD operations."""

    @pytest.fixture
    def test_recipe(self, db_session, test_user):
        """Create a test recipe owned by test_user."""
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)
        return recipe

    @pytest.fixture
    def system_recipe(self, db_session):
        """Create a system recipe (created_by is NULL)."""
        recipe = Recipe(
            id=uuid4(),
            name="System Recipe",
            source_type="manual",
            created_by=None,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)
        return recipe

    @pytest.fixture
    def test_ingredient(self, db_session, test_recipe):
        """Create a test ingredient for test_recipe."""
        from src.db.models.recipe_ingredient import RecipeIngredient
        ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=test_recipe.id,
            ingredient_name="Test Ingredient",
            quantity=1.5,
            unit="cups",
            variation_group=None,
            variation_diet=None,
            is_optional=False,
        )
        db_session.add(ingredient)
        db_session.commit()
        db_session.refresh(ingredient)
        return ingredient

    def test_add_ingredient_success(self, client, auth_headers, test_recipe, db_session):
        """Test adding an ingredient to a recipe successfully."""
        ingredient_data = {
            "ingredient_name": "Tomatoes",
            "quantity": 2.0,
            "unit": "lbs",
            "is_optional": False,
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ingredient_name"] == "Tomatoes"
        assert data["quantity"] == 2.0
        assert data["unit"] == "lbs"
        assert data["recipe_id"] == str(test_recipe.id)
        assert data["is_optional"] is False
        assert "id" in data

    def test_add_ingredient_with_variations(self, client, auth_headers, test_recipe):
        """Test adding ingredient with variation fields."""
        ingredient_data = {
            "ingredient_name": "Chicken",
            "quantity": 1.0,
            "unit": "lb",
            "variation_group": "protein",
            "variation_diet": "non-vegetarian",
            "is_optional": False,
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ingredient_name"] == "Chicken"
        assert data["variation_group"] == "protein"
        assert data["variation_diet"] == "non-vegetarian"

    def test_add_ingredient_recipe_not_found(self, client, auth_headers):
        """Test adding ingredient to non-existent recipe returns 404."""
        ingredient_data = {
            "ingredient_name": "Test",
            "quantity": 1.0,
            "unit": "cup",
        }

        fake_recipe_id = uuid4()
        response = client.post(
            f"/recipes/{fake_recipe_id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_add_ingredient_recipe_not_owned(self, client, auth_headers2, test_recipe):
        """Test adding ingredient to another user's recipe returns 404."""
        ingredient_data = {
            "ingredient_name": "Test",
            "quantity": 1.0,
            "unit": "cup",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers2
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_add_ingredient_system_recipe(self, client, auth_headers, system_recipe):
        """Test adding ingredient to system recipe returns 403."""
        ingredient_data = {
            "ingredient_name": "Test",
            "quantity": 1.0,
            "unit": "cup",
        }

        response = client.post(
            f"/recipes/{system_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Cannot modify system recipes"

    def test_add_ingredient_unauthenticated(self, client, test_recipe):
        """Test adding ingredient without auth returns 401."""
        ingredient_data = {
            "ingredient_name": "Test",
            "quantity": 1.0,
            "unit": "cup",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data
        )

        assert response.status_code == 401

    def test_update_ingredient_success(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating an ingredient successfully."""
        update_data = {
            "quantity": 2.5,
            "unit": "tablespoons",
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 2.5
        assert data["unit"] == "tablespoons"
        assert data["ingredient_name"] == "Test Ingredient"  # Unchanged

    def test_update_ingredient_all_fields(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating all ingredient fields."""
        update_data = {
            "ingredient_name": "Updated Ingredient",
            "quantity": 3.0,
            "unit": "oz",
            "variation_group": "base",
            "variation_diet": "vegan",
            "is_optional": True,
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ingredient_name"] == "Updated Ingredient"
        assert data["quantity"] == 3.0
        assert data["unit"] == "oz"
        assert data["variation_group"] == "base"
        assert data["variation_diet"] == "vegan"
        assert data["is_optional"] is True

    def test_update_ingredient_not_found(self, client, auth_headers, test_recipe):
        """Test updating non-existent ingredient returns 404."""
        update_data = {"quantity": 2.0}
        fake_ingredient_id = uuid4()

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{fake_ingredient_id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Ingredient not found"

    def test_update_ingredient_recipe_not_owned(self, client, auth_headers2, test_recipe, test_ingredient):
        """Test updating ingredient on another user's recipe returns 404."""
        update_data = {"quantity": 2.0}

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers2
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_update_ingredient_system_recipe(self, client, auth_headers, system_recipe, db_session):
        """Test updating ingredient on system recipe returns 403."""
        from src.db.models.recipe_ingredient import RecipeIngredient
        # Create ingredient for system recipe
        ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=system_recipe.id,
            ingredient_name="System Ingredient",
            quantity=1.0,
            unit="cup",
        )
        db_session.add(ingredient)
        db_session.commit()

        update_data = {"quantity": 2.0}

        response = client.put(
            f"/recipes/{system_recipe.id}/ingredients/{ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Cannot modify system recipes"

    def test_delete_ingredient_success(self, client, auth_headers, test_recipe, test_ingredient, db_session):
        """Test deleting an ingredient successfully."""
        from src.db.models.recipe_ingredient import RecipeIngredient

        response = client.delete(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify ingredient is deleted
        ingredient = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.id == test_ingredient.id
        ).first()
        assert ingredient is None

    def test_delete_ingredient_not_found(self, client, auth_headers, test_recipe):
        """Test deleting non-existent ingredient returns 404."""
        fake_ingredient_id = uuid4()

        response = client.delete(
            f"/recipes/{test_recipe.id}/ingredients/{fake_ingredient_id}",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Ingredient not found"

    def test_delete_ingredient_recipe_not_owned(self, client, auth_headers2, test_recipe, test_ingredient):
        """Test deleting ingredient from another user's recipe returns 404."""
        response = client.delete(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            headers=auth_headers2
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_delete_ingredient_system_recipe(self, client, auth_headers, system_recipe, db_session):
        """Test deleting ingredient from system recipe returns 403."""
        from src.db.models.recipe_ingredient import RecipeIngredient
        # Create ingredient for system recipe
        ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=system_recipe.id,
            ingredient_name="System Ingredient",
            quantity=1.0,
            unit="cup",
        )
        db_session.add(ingredient)
        db_session.commit()

        response = client.delete(
            f"/recipes/{system_recipe.id}/ingredients/{ingredient.id}",
            headers=auth_headers
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Cannot modify system recipes"

    def test_delete_ingredient_unauthenticated(self, client, test_recipe, test_ingredient):
        """Test deleting ingredient without auth returns 401."""
        response = client.delete(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}"
        )

        assert response.status_code == 401
