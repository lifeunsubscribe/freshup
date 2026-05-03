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
- Recipe ingredient CRUD operations with edge case validation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import UUID, uuid4

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

    def test_create_recipe_sets_created_by_to_authenticated_user(self, client, auth_headers, test_user, db_session):
        """Test that created_by is correctly set to authenticated user on recipe creation."""
        recipe_data = {
            "name": "Ownership Test Recipe",
            "source_type": "manual",
        }

        response = client.post("/recipes", json=recipe_data, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()

        # Verify created_by in response matches authenticated user
        assert data["created_by"] == str(test_user.id)

        # Verify created_by in database matches authenticated user
        recipe_id = UUID(data["id"])
        db_recipe = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert db_recipe is not None
        assert db_recipe.created_by == test_user.id

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
        """Test listing recipes returns all recipes (global read)."""
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

    def test_get_recipe_cross_user_access_allowed(self, client, auth_headers, auth_headers2, test_user2, db_session):
        """Test user CAN access another user's recipe (global read)."""
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

        # Access with user1's token (global read should allow this)
        response = client.get(f"/recipes/{recipe.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "User2 Recipe"
        assert data["created_by"] == str(test_user2.id)

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

    def test_update_recipe_cross_user_denied(self, client, auth_headers, auth_headers2, test_user2, db_session):
        """Test user CANNOT update another user's recipe (ownership enforcement)."""
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

        update_data = {"name": "Hacked Name"}

        # Try to update with user1's token (should fail)
        response = client.put(f"/recipes/{recipe.id}", json=update_data, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

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

    def test_delete_recipe_cross_user_denied(self, client, auth_headers, auth_headers2, test_user2, db_session):
        """Test user CANNOT delete another user's recipe (ownership enforcement)."""
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
        recipe_id = recipe.id

        # Try to delete with user1's token (should fail)
        response = client.delete(f"/recipes/{recipe_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

        # Verify recipe was NOT deleted
        recipe_still_exists = db_session.query(Recipe).filter(Recipe.id == recipe_id).first()
        assert recipe_still_exists is not None

    def test_list_recipes_global_read(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Test that users can see recipes from all users (global read)."""
        # Create recipes for user1
        recipe1 = Recipe(
            id=uuid4(),
            name="User1 Recipe",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        # Create recipes for user2
        recipe2 = Recipe(
            id=uuid4(),
            name="User2 Recipe",
            source_type="manual",
            created_by=test_user2.id,
            tags=[],
            steps=[],
        )
        db_session.add_all([recipe1, recipe2])
        db_session.commit()

        # User1 can see both recipes
        response = client.get("/recipes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {r["name"] for r in data}
        assert "User1 Recipe" in names
        assert "User2 Recipe" in names

        # User2 can also see both recipes
        response = client.get("/recipes", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {r["name"] for r in data}
        assert "User1 Recipe" in names
        assert "User2 Recipe" in names


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

    def test_add_ingredient_empty_name(self, client, auth_headers, test_recipe):
        """Test adding ingredient with empty name fails validation."""
        ingredient_data = {
            "ingredient_name": "",
            "quantity": 1.0,
            "unit": "cup",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail either min_length or whitespace validation
        assert any("ingredient_name" in str(error).lower() for error in detail)

    def test_add_ingredient_whitespace_only_name(self, client, auth_headers, test_recipe):
        """Test adding ingredient with whitespace-only name fails validation."""
        ingredient_data = {
            "ingredient_name": "   ",
            "quantity": 1.0,
            "unit": "cup",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail whitespace validation
        assert any("ingredient_name" in str(error).lower() or "empty" in str(error).lower() or "whitespace" in str(error).lower() for error in detail)

    def test_add_ingredient_empty_unit(self, client, auth_headers, test_recipe):
        """Test adding ingredient with empty unit fails validation."""
        ingredient_data = {
            "ingredient_name": "Salt",
            "quantity": 1.0,
            "unit": "",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail either min_length or whitespace validation
        assert any("unit" in str(error).lower() for error in detail)

    def test_add_ingredient_whitespace_only_unit(self, client, auth_headers, test_recipe):
        """Test adding ingredient with whitespace-only unit fails validation."""
        ingredient_data = {
            "ingredient_name": "Salt",
            "quantity": 1.0,
            "unit": "   ",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail whitespace validation
        assert any("unit" in str(error).lower() or "empty" in str(error).lower() or "whitespace" in str(error).lower() for error in detail)

    def test_add_ingredient_zero_quantity(self, client, auth_headers, test_recipe):
        """Test adding ingredient with zero quantity fails validation."""
        ingredient_data = {
            "ingredient_name": "Salt",
            "quantity": 0,
            "unit": "tsp",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail gt=0 validation
        assert any("quantity" in str(error).lower() for error in detail)

    def test_add_ingredient_negative_quantity(self, client, auth_headers, test_recipe):
        """Test adding ingredient with negative quantity fails validation."""
        ingredient_data = {
            "ingredient_name": "Salt",
            "quantity": -1.5,
            "unit": "tsp",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail gt=0 validation
        assert any("quantity" in str(error).lower() for error in detail)

    def test_update_ingredient_empty_name(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating ingredient with empty name fails validation."""
        update_data = {
            "ingredient_name": "",
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("ingredient_name" in str(error).lower() for error in detail)

    def test_update_ingredient_whitespace_only_name(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating ingredient with whitespace-only name fails validation."""
        update_data = {
            "ingredient_name": "   ",
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("ingredient_name" in str(error).lower() or "empty" in str(error).lower() or "whitespace" in str(error).lower() for error in detail)

    def test_update_ingredient_empty_unit(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating ingredient with empty unit fails validation."""
        update_data = {
            "unit": "",
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("unit" in str(error).lower() for error in detail)

    def test_update_ingredient_whitespace_only_unit(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating ingredient with whitespace-only unit fails validation."""
        update_data = {
            "unit": "   ",
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("unit" in str(error).lower() or "empty" in str(error).lower() or "whitespace" in str(error).lower() for error in detail)

    def test_update_ingredient_zero_quantity(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating ingredient with zero quantity fails validation."""
        update_data = {
            "quantity": 0,
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("quantity" in str(error).lower() for error in detail)

    def test_update_ingredient_negative_quantity(self, client, auth_headers, test_recipe, test_ingredient):
        """Test updating ingredient with negative quantity fails validation."""
        update_data = {
            "quantity": -2.0,
        }

        response = client.put(
            f"/recipes/{test_recipe.id}/ingredients/{test_ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("quantity" in str(error).lower() for error in detail)


class TestRecipeRatings:
    """Test recipe rating endpoints."""

    @pytest.fixture
    def test_recipe(self, db_session, test_user):
        """Create a test recipe for rating tests."""
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe for Ratings",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)
        return recipe

    def test_create_rating_success(self, client, auth_headers, test_recipe, test_user, db_session):
        """Test creating a new rating for a recipe."""
        rating_data = {
            "rating": 4.5,
            "is_bookmarked": True,
            "rating_comment": "Delicious recipe!",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 4.5
        assert data["is_bookmarked"] is True
        assert data["rating_comment"] == "Delicious recipe!"
        assert data["user_id"] == str(test_user.id)
        assert data["recipe_id"] == str(test_recipe.id)
        assert "id" in data

    def test_create_rating_minimal_fields(self, client, auth_headers, test_recipe, test_user):
        """Test creating rating with only is_bookmarked (no rating value or comment)."""
        rating_data = {
            "is_bookmarked": True,
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] is None
        assert data["is_bookmarked"] is True
        assert data["rating_comment"] is None

    def test_update_rating_upsert(self, client, auth_headers, test_recipe, test_user, db_session):
        """Test updating an existing rating (upsert behavior)."""
        # Create initial rating
        rating_data = {
            "rating": 3.0,
            "is_bookmarked": False,
            "rating_comment": "Initial note",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        initial_id = response.json()["id"]

        # Update the rating (same endpoint, different data)
        update_data = {
            "rating": 5.0,
            "is_bookmarked": True,
            "rating_comment": "Updated note - much better!",
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == initial_id  # Same ID (updated, not created)
        assert data["rating"] == 5.0
        assert data["is_bookmarked"] is True
        assert data["rating_comment"] == "Updated note - much better!"

        # Verify only one rating exists in database
        from src.db.models.user_recipe import UserRecipeRelation
        ratings = db_session.query(UserRecipeRelation).filter(
            UserRecipeRelation.user_id == test_user.id,
            UserRecipeRelation.recipe_id == test_recipe.id,
        ).all()
        assert len(ratings) == 1

    def test_create_rating_recipe_not_found(self, client, auth_headers):
        """Test creating rating for non-existent recipe returns 404."""
        rating_data = {
            "rating": 4.0,
            "is_bookmarked": False,
        }

        fake_recipe_id = uuid4()
        response = client.post(
            f"/recipes/{fake_recipe_id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_create_rating_unauthenticated(self, client, test_recipe):
        """Test creating rating without auth returns 401."""
        rating_data = {
            "rating": 4.0,
            "is_bookmarked": False,
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data
        )

        assert response.status_code == 401

    def test_create_rating_out_of_range_high(self, client, auth_headers, test_recipe):
        """Test creating rating with value > 5.0 fails validation."""
        rating_data = {
            "rating": 5.5,
            "is_bookmarked": False,
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Should fail validation with message about range
        assert any("rating" in str(error).lower() or "0.0" in str(error) or "5.0" in str(error) for error in detail)

    def test_create_rating_out_of_range_low(self, client, auth_headers, test_recipe):
        """Test creating rating with value < 0.0 fails validation."""
        rating_data = {
            "rating": -1.0,
            "is_bookmarked": False,
        }

        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("rating" in str(error).lower() or "0.0" in str(error) or "5.0" in str(error) for error in detail)

    def test_create_rating_boundary_values(self, client, auth_headers, test_recipe, db_session):
        """Test creating ratings with boundary values (0.0 and 5.0)."""
        # Test 0.0 (minimum valid)
        rating_data = {"rating": 0.0, "is_bookmarked": False}
        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 0.0

        # Test 5.0 (maximum valid) - updates existing rating
        rating_data = {"rating": 5.0, "is_bookmarked": True}
        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 5.0

    def test_get_my_rating_success(self, client, auth_headers, test_recipe, test_user, db_session):
        """Test getting user's own rating for a recipe."""
        # Create a rating first
        from src.db.models.user_recipe import UserRecipeRelation
        rating = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            rating=4.0,
            is_bookmarked=True,
            rating_comment="My rating",
        )
        db_session.add(rating)
        db_session.commit()

        response = client.get(
            f"/recipes/{test_recipe.id}/my-rating",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 4.0
        assert data["is_bookmarked"] is True
        assert data["rating_comment"] == "My rating"
        assert data["user_id"] == str(test_user.id)

    def test_get_my_rating_not_found(self, client, auth_headers, test_recipe):
        """Test getting rating when user hasn't rated returns 404."""
        response = client.get(
            f"/recipes/{test_recipe.id}/my-rating",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Rating not found"

    def test_get_my_rating_recipe_not_found(self, client, auth_headers):
        """Test getting rating for non-existent recipe returns 404."""
        fake_recipe_id = uuid4()
        response = client.get(
            f"/recipes/{fake_recipe_id}/my-rating",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_get_my_rating_unauthenticated(self, client, test_recipe):
        """Test getting rating without auth returns 401."""
        response = client.get(f"/recipes/{test_recipe.id}/my-rating")

        assert response.status_code == 401

    def test_delete_my_rating_success(self, client, auth_headers, test_recipe, test_user, db_session):
        """Test deleting user's rating successfully."""
        # Create a rating first
        from src.db.models.user_recipe import UserRecipeRelation
        rating = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            rating=3.5,
            is_bookmarked=False,
        )
        db_session.add(rating)
        db_session.commit()
        rating_id = rating.id

        response = client.delete(
            f"/recipes/{test_recipe.id}/my-rating",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify rating is deleted
        deleted_rating = db_session.query(UserRecipeRelation).filter(
            UserRecipeRelation.id == rating_id
        ).first()
        assert deleted_rating is None

    def test_delete_my_rating_idempotent(self, client, auth_headers, test_recipe):
        """Test deleting non-existent rating returns 204 (idempotent)."""
        response = client.delete(
            f"/recipes/{test_recipe.id}/my-rating",
            headers=auth_headers
        )

        assert response.status_code == 204

    def test_delete_my_rating_recipe_not_found(self, client, auth_headers):
        """Test deleting rating for non-existent recipe returns 404."""
        fake_recipe_id = uuid4()
        response = client.delete(
            f"/recipes/{fake_recipe_id}/my-rating",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_delete_my_rating_unauthenticated(self, client, test_recipe):
        """Test deleting rating without auth returns 401."""
        response = client.delete(f"/recipes/{test_recipe.id}/my-rating")

        assert response.status_code == 401

    def test_get_aggregate_ratings_no_ratings(self, client, auth_headers, test_recipe):
        """Test aggregate ratings with no ratings returns zeros/null."""
        response = client.get(
            f"/recipes/{test_recipe.id}/ratings",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["average_rating"] is None
        assert data["rating_count"] == 0
        assert data["favorite_count"] == 0

    def test_get_aggregate_ratings_single_rating(self, client, auth_headers, test_recipe, test_user, db_session):
        """Test aggregate ratings with one rating."""
        from src.db.models.user_recipe import UserRecipeRelation
        rating = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            rating=4.0,
            is_bookmarked=True,
        )
        db_session.add(rating)
        db_session.commit()

        response = client.get(
            f"/recipes/{test_recipe.id}/ratings",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["average_rating"] == 4.0
        assert data["rating_count"] == 1
        assert data["favorite_count"] == 1

    def test_get_aggregate_ratings_multiple_ratings(self, client, auth_headers, test_recipe, test_user, test_user2, db_session):
        """Test aggregate ratings with multiple users' ratings."""
        from src.db.models.user_recipe import UserRecipeRelation

        # User 1 rating
        rating1 = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            rating=4.0,
            is_bookmarked=True,
        )

        # User 2 rating
        rating2 = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user2.id,
            recipe_id=test_recipe.id,
            rating=5.0,
            is_bookmarked=False,
        )

        db_session.add_all([rating1, rating2])
        db_session.commit()

        response = client.get(
            f"/recipes/{test_recipe.id}/ratings",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["average_rating"] == 4.5  # (4.0 + 5.0) / 2
        assert data["rating_count"] == 2
        assert data["favorite_count"] == 1  # Only user1 favorited

    def test_get_aggregate_ratings_favorite_only(self, client, auth_headers, test_recipe, test_user, db_session):
        """Test aggregate ratings when user only favorited (no rating value)."""
        from src.db.models.user_recipe import UserRecipeRelation
        rating = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            rating=None,  # No rating value
            is_bookmarked=True,
        )
        db_session.add(rating)
        db_session.commit()

        response = client.get(
            f"/recipes/{test_recipe.id}/ratings",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["average_rating"] is None  # No numeric ratings
        assert data["rating_count"] == 0  # Count only rows with rating values
        assert data["favorite_count"] == 1

    def test_get_aggregate_ratings_mixed_null_ratings(self, client, auth_headers, test_recipe, test_user, test_user2, db_session):
        """Test aggregate ratings with mix of null and numeric ratings."""
        from src.db.models.user_recipe import UserRecipeRelation

        # User 1: numeric rating
        rating1 = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=test_recipe.id,
            rating=4.0,
            is_bookmarked=False,
        )

        # User 2: favorite only (no rating)
        rating2 = UserRecipeRelation(
            id=uuid4(),
            user_id=test_user2.id,
            recipe_id=test_recipe.id,
            rating=None,
            is_bookmarked=True,
        )

        db_session.add_all([rating1, rating2])
        db_session.commit()

        response = client.get(
            f"/recipes/{test_recipe.id}/ratings",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["average_rating"] == 4.0  # Only counts numeric ratings
        assert data["rating_count"] == 1  # Only counts rows with rating values
        assert data["favorite_count"] == 1  # User 2 favorited

    def test_get_aggregate_ratings_recipe_not_found(self, client, auth_headers):
        """Test aggregate ratings for non-existent recipe returns 404."""
        fake_recipe_id = uuid4()
        response = client.get(
            f"/recipes/{fake_recipe_id}/ratings",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    def test_get_aggregate_ratings_unauthenticated(self, client, test_recipe):
        """Test aggregate ratings without auth returns 401."""
        response = client.get(f"/recipes/{test_recipe.id}/ratings")

        assert response.status_code == 401

    def test_ratings_cross_user_isolation(self, client, auth_headers, auth_headers2, test_recipe, test_user, test_user2, db_session):
        """Test that each user has separate ratings for the same recipe."""
        from src.db.models.user_recipe import UserRecipeRelation

        # User 1 creates rating
        rating_data = {
            "rating": 3.0,
            "is_bookmarked": False,
            "rating_comment": "User 1 note",
        }
        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        # User 2 creates different rating
        rating_data2 = {
            "rating": 5.0,
            "is_bookmarked": True,
            "rating_comment": "User 2 note",
        }
        response = client.post(
            f"/recipes/{test_recipe.id}/rate",
            json=rating_data2,
            headers=auth_headers2
        )
        assert response.status_code == 200

        # User 1 gets their rating
        response = client.get(
            f"/recipes/{test_recipe.id}/my-rating",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 3.0
        assert data["rating_comment"] == "User 1 note"

        # User 2 gets their rating
        response = client.get(
            f"/recipes/{test_recipe.id}/my-rating",
            headers=auth_headers2
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5.0
        assert data["rating_comment"] == "User 2 note"

        # Verify two separate ratings exist in database
        ratings = db_session.query(UserRecipeRelation).filter(
            UserRecipeRelation.recipe_id == test_recipe.id
        ).all()
        assert len(ratings) == 2


class TestAdHocRecipeCreation:
    """Tests for POST /recipes/ad-hoc endpoint."""

    def test_create_ad_hoc_recipe_without_decrement(self, client, db_session, auth_headers, test_user):
        """Test creating an ad-hoc recipe from inventory items without decrementing inventory."""
        from src.db.models.inventory_item import InventoryItem
        from src.db.models.recipe_ingredient import RecipeIngredient

        # Create inventory items
        item1 = InventoryItem(
            id=uuid4(),
            name="Tomatoes",
            quantity=10.0,
            unit="oz",
            category="produce",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            id=uuid4(),
            name="Onions",
            quantity=5.0,
            unit="count",
            category="produce",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # Create ad-hoc recipe
        recipe_data = {
            "name": "Quick Tomato Onion Soup",
            "steps": ["Chop onions", "Dice tomatoes", "Simmer together"],
            "notes": "Made this on the fly!",
            "tags": ["quick", "soup"],
            "inventory_items": [
                {"inventory_item_id": str(item1.id), "quantity_used": 5.0, "unit": "oz"},
                {"inventory_item_id": str(item2.id), "quantity_used": 2.0, "unit": "count"},
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()

        # Verify recipe created with correct attributes
        assert data["name"] == "Quick Tomato Onion Soup"
        assert data["source_type"] == "ad_hoc"
        assert data["created_by"] == str(test_user.id)
        assert data["steps"] == ["Chop onions", "Dice tomatoes", "Simmer together"]
        assert data["notes"] == "Made this on the fly!"
        assert "quick" in data["tags"]
        assert "soup" in data["tags"]

        # Verify recipe ingredients were created with inventory item names
        recipe_id = UUID(data["id"])
        ingredients = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        assert len(ingredients) == 2

        ingredient_names = {ing.ingredient_name for ing in ingredients}
        assert "Tomatoes" in ingredient_names
        assert "Onions" in ingredient_names

        # Verify inventory NOT decremented (decrement_inventory=False)
        db_session.refresh(item1)
        db_session.refresh(item2)
        assert item1.quantity == 10.0
        assert item2.quantity == 5.0

    def test_create_ad_hoc_recipe_with_decrement(self, client, db_session, auth_headers, test_user):
        """Test creating an ad-hoc recipe with inventory decrement."""
        from src.db.models.inventory_item import InventoryItem
        from src.db.models.recipe_ingredient import RecipeIngredient

        # Create inventory items
        item1 = InventoryItem(
            id=uuid4(),
            name="Pasta",
            quantity=16.0,
            unit="oz",
            category="grain",
            storage_location="pantry",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            id=uuid4(),
            name="Marinara Sauce",
            quantity=24.0,
            unit="oz",
            category="condiment",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # Create ad-hoc recipe with decrement
        recipe_data = {
            "name": "Simple Pasta Marinara",
            "steps": ["Boil pasta", "Heat sauce", "Combine"],
            "inventory_items": [
                {"inventory_item_id": str(item1.id), "quantity_used": 8.0, "unit": "oz"},
                {"inventory_item_id": str(item2.id), "quantity_used": 12.0, "unit": "oz"},
            ],
            "decrement_inventory": True,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()

        # Verify recipe created
        assert data["name"] == "Simple Pasta Marinara"
        assert data["source_type"] == "ad_hoc"

        # Verify recipe ingredients created
        recipe_id = UUID(data["id"])
        ingredients = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        assert len(ingredients) == 2

        # Verify inventory WAS decremented (decrement_inventory=True)
        db_session.refresh(item1)
        db_session.refresh(item2)
        assert item1.quantity == 8.0  # 16.0 - 8.0
        assert item2.quantity == 12.0  # 24.0 - 12.0

    def test_create_ad_hoc_recipe_invalid_inventory_id(self, client, auth_headers):
        """Test creating ad-hoc recipe with invalid inventory item ID returns 404."""
        fake_id = uuid4()

        recipe_data = {
            "name": "Ghost Recipe",
            "inventory_items": [
                {"inventory_item_id": str(fake_id), "quantity_used": 1.0, "unit": "oz"},
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 404
        assert "not found or not owned by user" in response.json()["detail"]

    def test_create_ad_hoc_recipe_cross_user_inventory_access_blocked(
        self, client, db_session, auth_headers, test_user
    ):
        """Test that users cannot create ad-hoc recipes from other users' inventory items."""
        from src.db.models.inventory_item import InventoryItem

        # Create another user
        other_user = User(
            id=uuid4(),
            name="Other User",
            email="other@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.member.value,
        )
        db_session.add(other_user)

        # Create inventory item owned by other user
        other_item = InventoryItem(
            id=uuid4(),
            name="Secret Ingredient",
            quantity=10.0,
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=other_user.id,
        )
        db_session.add(other_item)
        db_session.commit()

        # Try to create ad-hoc recipe using other user's inventory
        recipe_data = {
            "name": "Stolen Recipe",
            "inventory_items": [
                {"inventory_item_id": str(other_item.id), "quantity_used": 5.0, "unit": "oz"},
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 404
        assert "not found or not owned by user" in response.json()["detail"]

    def test_create_ad_hoc_recipe_insufficient_quantity(self, client, db_session, auth_headers, test_user):
        """Test creating ad-hoc recipe with insufficient inventory quantity returns 400."""
        from src.db.models.inventory_item import InventoryItem

        # Create inventory item with limited quantity
        item = InventoryItem(
            id=uuid4(),
            name="Rare Spice",
            quantity=2.0,
            unit="tsp",
            category="spice",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # Try to use more than available
        recipe_data = {
            "name": "Spicy Disaster",
            "inventory_items": [
                {"inventory_item_id": str(item.id), "quantity_used": 5.0, "unit": "tsp"},
            ],
            "decrement_inventory": True,  # Decrement is required to trigger validation
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 400
        assert "Only 2.0 tsp available" in response.json()["detail"]

        # Verify inventory was NOT decremented (atomic rollback)
        db_session.refresh(item)
        assert item.quantity == 2.0

    def test_create_ad_hoc_recipe_atomic_rollback_on_error(
        self, client, db_session, auth_headers, test_user
    ):
        """Test that ad-hoc recipe creation is atomic - if validation fails, nothing is created."""
        from src.db.models.inventory_item import InventoryItem
        from src.db.models.recipe import Recipe
        from src.db.models.recipe_ingredient import RecipeIngredient

        # Create two inventory items
        item1 = InventoryItem(
            id=uuid4(),
            name="Item A",
            quantity=10.0,
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            id=uuid4(),
            name="Item B",
            quantity=2.0,  # Intentionally low
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # Count recipes and ingredients before
        recipe_count_before = db_session.query(Recipe).count()
        ingredient_count_before = db_session.query(RecipeIngredient).count()

        # Try to create recipe that will fail on second item quantity check
        recipe_data = {
            "name": "Atomic Test Recipe",
            "inventory_items": [
                {"inventory_item_id": str(item1.id), "quantity_used": 5.0, "unit": "oz"},
                {"inventory_item_id": str(item2.id), "quantity_used": 10.0, "unit": "oz"},  # Too much!
            ],
            "decrement_inventory": True,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 400

        # Verify NO recipe was created
        recipe_count_after = db_session.query(Recipe).count()
        assert recipe_count_after == recipe_count_before

        # Verify NO ingredients were created
        ingredient_count_after = db_session.query(RecipeIngredient).count()
        assert ingredient_count_after == ingredient_count_before

        # Verify NO inventory was decremented
        db_session.refresh(item1)
        db_session.refresh(item2)
        assert item1.quantity == 10.0
        assert item2.quantity == 2.0

    def test_create_ad_hoc_recipe_empty_inventory_items_validation(self, client, auth_headers):
        """Test that empty inventory_items list is rejected by validation."""
        recipe_data = {
            "name": "Empty Recipe",
            "inventory_items": [],  # Empty list
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 422  # Validation error
        assert "inventory_items" in response.json()["detail"][0]["loc"]

    def test_create_ad_hoc_recipe_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        recipe_data = {
            "name": "Unauthorized Recipe",
            "inventory_items": [
                {"inventory_item_id": str(uuid4()), "quantity_used": 1.0, "unit": "oz"},
            ],
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data)
        assert response.status_code == 401

    def test_create_ad_hoc_recipe_with_multiple_items(self, client, db_session, auth_headers, test_user):
        """Test creating ad-hoc recipe with multiple inventory items."""
        from src.db.models.inventory_item import InventoryItem
        from src.db.models.recipe_ingredient import RecipeIngredient

        # Create multiple inventory items
        items = [
            InventoryItem(
                id=uuid4(),
                name=f"Ingredient {i}",
                quantity=100.0,
                unit="g",
                category="other",
                storage_location="pantry",
                added_by=test_user.id,
            )
            for i in range(5)
        ]
        db_session.add_all(items)
        db_session.commit()

        # Create recipe using all items
        recipe_data = {
            "name": "Complex Multi-Ingredient Recipe",
            "inventory_items": [
                {"inventory_item_id": str(item.id), "quantity_used": 20.0, "unit": "g"}
                for item in items
            ],
            "decrement_inventory": True,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()

        # Verify all ingredients were added
        recipe_id = UUID(data["id"])
        ingredients = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        assert len(ingredients) == 5

        # Verify all inventory was decremented correctly
        for item in items:
            db_session.refresh(item)
            assert item.quantity == 80.0  # 100.0 - 20.0

    def test_create_ad_hoc_recipe_unit_mismatch_without_decrement(self, client, db_session, auth_headers, test_user):
        """Test that unit mismatch is rejected even when decrement_inventory=False."""
        from src.db.models.inventory_item import InventoryItem

        # Create inventory item with "g" unit
        item = InventoryItem(
            id=uuid4(),
            name="Flour",
            quantity=500.0,
            unit="g",
            category="baking",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # Try to create recipe using different unit ("cup")
        recipe_data = {
            "name": "Unit Mismatch Recipe",
            "inventory_items": [
                {"inventory_item_id": str(item.id), "quantity_used": 2.0, "unit": "cup"},
            ],
            "decrement_inventory": False,  # Even without decrement, should fail
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 400
        assert "Unit mismatch for Flour" in response.json()["detail"]
        assert 'recipe uses "cup"' in response.json()["detail"]
        assert 'inventory has "g"' in response.json()["detail"]

        # Verify inventory was NOT touched
        db_session.refresh(item)
        assert item.quantity == 500.0

    def test_create_ad_hoc_recipe_unit_mismatch_with_decrement(self, client, db_session, auth_headers, test_user):
        """Test that unit mismatch is rejected when decrement_inventory=True."""
        from src.db.models.inventory_item import InventoryItem

        # Create inventory item with "oz" unit
        item = InventoryItem(
            id=uuid4(),
            name="Cheese",
            quantity=16.0,
            unit="oz",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # Try to create recipe using different unit ("lb")
        recipe_data = {
            "name": "Cheesy Recipe",
            "inventory_items": [
                {"inventory_item_id": str(item.id), "quantity_used": 1.0, "unit": "lb"},
            ],
            "decrement_inventory": True,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 400
        assert "Unit mismatch for Cheese" in response.json()["detail"]
        assert 'recipe uses "lb"' in response.json()["detail"]
        assert 'inventory has "oz"' in response.json()["detail"]

        # Verify inventory was NOT decremented (atomic rollback)
        db_session.refresh(item)
        assert item.quantity == 16.0

    def test_create_ad_hoc_recipe_matching_units_success(self, client, db_session, auth_headers, test_user):
        """Test that matching units allow recipe creation successfully."""
        from src.db.models.inventory_item import InventoryItem
        from src.db.models.recipe import Recipe

        # Create inventory item with "tsp" unit
        item = InventoryItem(
            id=uuid4(),
            name="Vanilla Extract",
            quantity=10.0,
            unit="tsp",
            category="baking",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # Create recipe using SAME unit ("tsp")
        recipe_data = {
            "name": "Vanilla Cookies",
            "inventory_items": [
                {"inventory_item_id": str(item.id), "quantity_used": 2.0, "unit": "tsp"},
            ],
            "decrement_inventory": True,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Vanilla Cookies"

        # Verify inventory was decremented correctly
        db_session.refresh(item)
        assert item.quantity == 8.0  # 10.0 - 2.0

    def test_create_ad_hoc_recipe_unit_case_insensitive(self, client, db_session, auth_headers, test_user):
        """Test that unit comparison is case-insensitive (oz == Oz for better UX)."""
        from src.db.models.inventory_item import InventoryItem

        # Create inventory item with lowercase "oz" unit
        item = InventoryItem(
            id=uuid4(),
            name="Milk",
            quantity=32.0,
            unit="oz",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # Create recipe using uppercase "Oz" - should succeed (case-insensitive)
        recipe_data = {
            "name": "Milkshake",
            "inventory_items": [
                {"inventory_item_id": str(item.id), "quantity_used": 8.0, "unit": "Oz"},
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Milkshake"
        assert data["source_type"] == "ad_hoc"

        # Verify inventory was NOT decremented (decrement_inventory=False)
        db_session.refresh(item)
        assert item.quantity == 32.0

    def test_create_ad_hoc_recipe_unit_mismatch_multiple_items_atomic(self, client, db_session, auth_headers, test_user):
        """Test that unit mismatch in one item prevents entire recipe creation (atomic)."""
        from src.db.models.inventory_item import InventoryItem
        from src.db.models.recipe import Recipe
        from src.db.models.recipe_ingredient import RecipeIngredient

        # Create two inventory items
        item1 = InventoryItem(
            id=uuid4(),
            name="Sugar",
            quantity=1000.0,
            unit="g",
            category="baking",
            storage_location="pantry",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            id=uuid4(),
            name="Butter",
            quantity=500.0,
            unit="g",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # Count recipes and ingredients before
        recipe_count_before = db_session.query(Recipe).count()
        ingredient_count_before = db_session.query(RecipeIngredient).count()

        # Try to create recipe with first item matching, second item mismatched
        recipe_data = {
            "name": "Atomic Unit Test Recipe",
            "inventory_items": [
                {"inventory_item_id": str(item1.id), "quantity_used": 100.0, "unit": "g"},  # Matches
                {"inventory_item_id": str(item2.id), "quantity_used": 8.0, "unit": "oz"},  # Mismatch!
            ],
            "decrement_inventory": True,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)
        assert response.status_code == 400
        assert "Unit mismatch for Butter" in response.json()["detail"]

        # Verify NO recipe was created (atomic rollback)
        recipe_count_after = db_session.query(Recipe).count()
        assert recipe_count_after == recipe_count_before

        # Verify NO ingredients were created
        ingredient_count_after = db_session.query(RecipeIngredient).count()
        assert ingredient_count_after == ingredient_count_before

        # Verify NO inventory was decremented
        db_session.refresh(item1)
        db_session.refresh(item2)
        assert item1.quantity == 1000.0
        assert item2.quantity == 500.0

    def test_create_ad_hoc_recipe_none_unit_behavior_documentation(self, client, db_session, auth_headers, test_user):
        """
        Document the defensive None unit handling behavior in src/routers/recipes.py:175-184.

        The code contains defensive logic to handle None units:
        ```python
        recipe_unit = item_usage.unit.lower() if item_usage.unit is not None else None
        inventory_unit = inventory_item.unit.lower() if inventory_item.unit is not None else None
        if recipe_unit != inventory_unit:
            raise HTTPException(...)
        ```

        This defensive code would allow None == None matching for unitless items. However:
        1. The database has a NOT NULL constraint on inventory_items.unit
        2. Pydantic schema requires unit to be a non-empty string
        3. Therefore, None units cannot actually occur in practice

        This test documents that the database prevents None units, making the defensive
        None-handling code unreachable but serving as good defensive programming practice
        for potential future schema changes.
        """
        from src.db.models.inventory_item import InventoryItem
        from sqlalchemy.exc import IntegrityError

        # Attempt to create inventory item with None unit fails at database level
        item = InventoryItem(
            id=uuid4(),
            name="Test Item",
            quantity=10.0,
            unit=None,  # This violates NOT NULL constraint
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)

        # Database enforces NOT NULL constraint on unit field
        try:
            db_session.commit()
            assert False, "Expected IntegrityError for NOT NULL constraint violation"
        except IntegrityError as e:
            assert "NOT NULL constraint failed: inventory_items.unit" in str(e)
            db_session.rollback()

    def test_create_ad_hoc_recipe_none_unit_rejected_by_schema_validation(self, client, auth_headers, test_user):
        """
        Test that Pydantic schema validation rejects None units in API requests.

        Even though the code has defensive None-handling logic (recipes.py:175-184),
        the Pydantic schema (InventoryItemUsage) requires unit to be a non-empty string,
        preventing None values from reaching the business logic layer.

        This is defense-in-depth: both schema validation AND the business logic
        can handle None units safely.
        """
        # Try to create recipe with None unit - rejected by Pydantic validation
        recipe_data = {
            "name": "Null Unit Recipe",
            "inventory_items": [
                {"inventory_item_id": str(uuid4()), "quantity_used": 1.0, "unit": None},
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)

        # Pydantic validation prevents None units from reaching business logic
        assert response.status_code == 422
        detail = response.json()["detail"]
        # Verify it's a validation error on the unit field
        assert any("unit" in str(error).lower() for error in detail)


class TestRecipeIngredientStepIndex:
    """Test step_index field for recipe ingredients."""

    @pytest.fixture
    def test_recipe_with_steps(self, db_session, test_user):
        """Create a test recipe with 3 steps."""
        recipe = Recipe(
            id=uuid4(),
            name="Recipe with Steps",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=["Step 1: Prep ingredients", "Step 2: Cook", "Step 3: Serve"],
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)
        return recipe

    @pytest.fixture
    def test_recipe_no_steps(self, db_session, test_user):
        """Create a test recipe with no steps."""
        recipe = Recipe(
            id=uuid4(),
            name="Recipe without Steps",
            source_type="manual",
            created_by=test_user.id,
            tags=[],
            steps=[],
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)
        return recipe

    def test_add_ingredient_with_step_index_zero(self, client, auth_headers, test_recipe_with_steps):
        """Test adding ingredient with step_index=0 succeeds."""
        ingredient_data = {
            "ingredient_name": "Tomatoes",
            "quantity": 2.0,
            "unit": "lbs",
            "step_index": 0,
        }

        response = client.post(
            f"/recipes/{test_recipe_with_steps.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ingredient_name"] == "Tomatoes"
        assert data["step_index"] == 0

    def test_add_ingredient_with_step_index_none(self, client, auth_headers, test_recipe_with_steps):
        """Test adding ingredient with step_index=None succeeds (backwards compatible)."""
        ingredient_data = {
            "ingredient_name": "Salt",
            "quantity": 1.0,
            "unit": "tsp",
            "step_index": None,
        }

        response = client.post(
            f"/recipes/{test_recipe_with_steps.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ingredient_name"] == "Salt"
        assert data["step_index"] is None

    def test_add_ingredient_without_step_index_field(self, client, auth_headers, test_recipe_with_steps):
        """Test adding ingredient without step_index field succeeds (backwards compatible)."""
        ingredient_data = {
            "ingredient_name": "Pepper",
            "quantity": 1.0,
            "unit": "tsp",
        }

        response = client.post(
            f"/recipes/{test_recipe_with_steps.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ingredient_name"] == "Pepper"
        assert data["step_index"] is None

    def test_add_ingredient_with_negative_step_index(self, client, auth_headers, test_recipe_with_steps):
        """Test adding ingredient with step_index=-1 returns 422 (Pydantic validation)."""
        ingredient_data = {
            "ingredient_name": "Invalid Ingredient",
            "quantity": 1.0,
            "unit": "cup",
            "step_index": -1,
        }

        response = client.post(
            f"/recipes/{test_recipe_with_steps.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Verify it's a validation error mentioning step_index
        assert any("step_index" in str(error).lower() for error in detail)

    def test_add_ingredient_with_step_index_out_of_bounds(self, client, auth_headers, test_recipe_with_steps):
        """Test adding ingredient with step_index >= len(steps) returns 400."""
        ingredient_data = {
            "ingredient_name": "Out of Bounds Ingredient",
            "quantity": 1.0,
            "unit": "cup",
            "step_index": 5,  # Recipe has only 3 steps (indices 0-2)
        }

        response = client.post(
            f"/recipes/{test_recipe_with_steps.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "step_index 5 is out of bounds" in detail
        assert "Recipe has 3 steps" in detail

    def test_add_ingredient_with_step_index_to_empty_steps_recipe(self, client, auth_headers, test_recipe_no_steps):
        """Test adding ingredient with step_index to recipe with no steps returns 400."""
        ingredient_data = {
            "ingredient_name": "No Steps Ingredient",
            "quantity": 1.0,
            "unit": "cup",
            "step_index": 0,
        }

        response = client.post(
            f"/recipes/{test_recipe_no_steps.id}/ingredients",
            json=ingredient_data,
            headers=auth_headers
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "step_index 0 is out of bounds" in detail
        assert "Recipe has 0 steps" in detail

    def test_update_ingredient_step_index(self, client, auth_headers, test_recipe_with_steps, db_session):
        """Test updating an ingredient's step_index."""
        from src.db.models.recipe_ingredient import RecipeIngredient

        # Create an ingredient without step_index
        ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=test_recipe_with_steps.id,
            ingredient_name="Updateable Ingredient",
            quantity=1.0,
            unit="cup",
            step_index=None,
        )
        db_session.add(ingredient)
        db_session.commit()
        db_session.refresh(ingredient)

        # Update to add step_index
        update_data = {
            "step_index": 1,
        }

        response = client.put(
            f"/recipes/{test_recipe_with_steps.id}/ingredients/{ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["step_index"] == 1

    def test_update_ingredient_step_index_out_of_bounds(self, client, auth_headers, test_recipe_with_steps, db_session):
        """Test updating ingredient with out of bounds step_index returns 400."""
        from src.db.models.recipe_ingredient import RecipeIngredient

        ingredient = RecipeIngredient(
            id=uuid4(),
            recipe_id=test_recipe_with_steps.id,
            ingredient_name="Test Ingredient",
            quantity=1.0,
            unit="cup",
            step_index=0,
        )
        db_session.add(ingredient)
        db_session.commit()
        db_session.refresh(ingredient)

        # Try to update to out of bounds step_index
        update_data = {
            "step_index": 10,
        }

        response = client.put(
            f"/recipes/{test_recipe_with_steps.id}/ingredients/{ingredient.id}",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "step_index 10 is out of bounds" in detail

    def test_ad_hoc_recipe_with_step_index(self, client, auth_headers, test_user, db_session):
        """Test creating ad-hoc recipe with step_index in inventory items."""
        from src.db.models.inventory_item import InventoryItem

        # Create inventory items
        item1 = InventoryItem(
            id=uuid4(),
            name="Pasta",
            quantity=500,
            unit="g",
            category="grain",
            storage_location="pantry",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            id=uuid4(),
            name="Tomato Sauce",
            quantity=200,
            unit="ml",
            category="condiment",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        recipe_data = {
            "name": "Quick Pasta",
            "steps": ["Boil pasta", "Heat sauce", "Mix together"],
            "inventory_items": [
                {
                    "inventory_item_id": str(item1.id),
                    "quantity_used": 200,
                    "unit": "g",
                    "step_index": 0,  # For "Boil pasta" step
                },
                {
                    "inventory_item_id": str(item2.id),
                    "quantity_used": 100,
                    "unit": "ml",
                    "step_index": 1,  # For "Heat sauce" step
                },
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Quick Pasta"
        assert data["source_type"] == "ad_hoc"

        # Verify ingredients were created with step_index
        recipe_id = UUID(data["id"])
        from src.db.models.recipe_ingredient import RecipeIngredient
        ingredients = db_session.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()

        assert len(ingredients) == 2
        # Check that step_index values were preserved
        step_indices = {ing.ingredient_name: ing.step_index for ing in ingredients}
        assert step_indices["Pasta"] == 0
        assert step_indices["Tomato Sauce"] == 1

    def test_ad_hoc_recipe_with_step_index_out_of_bounds(self, client, auth_headers, test_user, db_session):
        """Test creating ad-hoc recipe with out of bounds step_index returns 400."""
        from src.db.models.inventory_item import InventoryItem

        item = InventoryItem(
            id=uuid4(),
            name="Test Item",
            quantity=100,
            unit="g",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        recipe_data = {
            "name": "Invalid Recipe",
            "steps": ["Step 1"],
            "inventory_items": [
                {
                    "inventory_item_id": str(item.id),
                    "quantity_used": 50,
                    "unit": "g",
                    "step_index": 5,  # Out of bounds - recipe has only 1 step
                },
            ],
            "decrement_inventory": False,
        }

        response = client.post("/recipes/ad-hoc", json=recipe_data, headers=auth_headers)

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "step_index 5 is out of bounds" in detail
        assert "Recipe has 1 step" in detail


class TestPersistenceTrigger:
    """Test persistence trigger when users bookmark/like recipes."""

    def test_bookmark_non_persisted_recipe_triggers_persistence(self, client, auth_headers, test_user, db_session):
        """Test that bookmarking a non-persisted recipe sets is_persisted=True."""
        # Create a non-persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=False,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        # Verify recipe starts as non-persisted
        assert recipe.is_persisted is False

        # Bookmark the recipe (is_bookmarked=True)
        rating_data = {
            "is_bookmarked": True,
            "rating": None,  # User can bookmark without rating
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify recipe is now persisted
        db_session.refresh(recipe)
        assert recipe.is_persisted is True

    def test_like_with_rating_triggers_persistence(self, client, auth_headers, test_user, db_session):
        """Test that liking a recipe with a rating triggers persistence."""
        # Create a non-persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=False,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        # Rate and like the recipe
        rating_data = {
            "is_bookmarked": True,
            "rating": 4.5,
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify recipe is now persisted
        db_session.refresh(recipe)
        assert recipe.is_persisted is True

    def test_rate_without_favorite_does_not_trigger_persistence(self, client, auth_headers, test_user, db_session):
        """Test that rating without favoriting does not trigger persistence."""
        # Create a non-persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=False,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        # Rate without favoriting
        rating_data = {
            "is_bookmarked": False,
            "rating": 3.0,
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify recipe remains non-persisted
        db_session.refresh(recipe)
        assert recipe.is_persisted is False

    def test_bookmark_already_persisted_recipe_is_idempotent(self, client, auth_headers, test_user, db_session):
        """Test that bookmarking an already-persisted recipe has no side effects."""
        # Create a pre-persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=True,  # Already persisted
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(recipe)

        # Bookmark the recipe
        rating_data = {
            "is_bookmarked": True,
            "rating": None,
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify recipe remains persisted (idempotent)
        db_session.refresh(recipe)
        assert recipe.is_persisted is True

    def test_update_rating_to_favorite_triggers_persistence(self, client, auth_headers, test_user, db_session):
        """Test that updating an existing rating to is_bookmarked=True triggers persistence."""
        from src.db.models.user_recipe import UserRecipeRelation

        # Create a non-persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=False,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()

        # Create an initial rating without favoriting
        initial_rating = UserRecipeRelation(
            user_id=test_user.id,
            recipe_id=recipe.id,
            rating=3.0,
            is_bookmarked=False,
        )
        db_session.add(initial_rating)
        db_session.commit()
        db_session.refresh(recipe)

        # Verify recipe is not persisted yet
        assert recipe.is_persisted is False

        # Update rating to favorite
        update_data = {
            "is_bookmarked": True,
            "rating": 4.0,
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify recipe is now persisted
        db_session.refresh(recipe)
        assert recipe.is_persisted is True

    def test_update_rating_to_unfavorite_does_not_unpersist(self, client, auth_headers, test_user, db_session):
        """Test that un-favoriting does not reverse persistence (one-way operation)."""
        from src.db.models.user_recipe import UserRecipeRelation

        # Create a persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=True,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()

        # Create a favorited rating
        initial_rating = UserRecipeRelation(
            user_id=test_user.id,
            recipe_id=recipe.id,
            rating=4.0,
            is_bookmarked=True,
        )
        db_session.add(initial_rating)
        db_session.commit()
        db_session.refresh(recipe)

        # Update rating to un-favorite
        update_data = {
            "is_bookmarked": False,
            "rating": 4.0,
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=update_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify recipe remains persisted (persistence is one-way)
        db_session.refresh(recipe)
        assert recipe.is_persisted is True

    def test_rating_succeeds_even_if_persistence_trigger_fails(self, client, auth_headers, test_user, db_session, monkeypatch):
        """Test that rating operation succeeds even if persistence trigger fails."""
        from src.db.models.user_recipe import UserRecipeRelation
        from sqlalchemy.exc import SQLAlchemyError

        # Create a non-persisted recipe
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=False,
            created_by=test_user.id,
        )
        db_session.add(recipe)
        db_session.commit()

        # Mock trigger_persistence to raise an exception
        def mock_trigger_persistence(recipe, db):
            raise SQLAlchemyError("Simulated persistence failure")

        import src.routers.recipes
        monkeypatch.setattr(src.routers.recipes, "trigger_persistence", mock_trigger_persistence)

        # Create a rating with is_bookmarked=True
        rating_data = {
            "is_bookmarked": True,
            "rating": 5.0,
        }

        response = client.post(
            f"/recipes/{recipe.id}/rate",
            json=rating_data,
            headers=auth_headers
        )

        # The rating operation should succeed despite persistence failure
        assert response.status_code == 200
        assert response.json()["is_bookmarked"] is True
        assert response.json()["rating"] == 5.0

        # Verify the rating was saved to the database
        saved_rating = db_session.query(UserRecipeRelation).filter(
            UserRecipeRelation.user_id == test_user.id,
            UserRecipeRelation.recipe_id == recipe.id,
        ).first()
        assert saved_rating is not None
        assert saved_rating.is_bookmarked is True
        assert saved_rating.rating == 5.0

        # Verify recipe was NOT persisted (due to simulated failure)
        db_session.refresh(recipe)
        assert recipe.is_persisted is False
