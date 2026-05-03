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

    def test_home_feed_includes_new_row_fields(self, client, auth_headers, test_user, db_session):
        """Test home feed response includes new personalized/source/fallback row fields."""
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have new fields
        assert "personalized_rows" in data
        assert "source_rows" in data
        assert "fallback_rows" in data

        # Fields should be arrays
        assert isinstance(data["personalized_rows"], list)
        assert isinstance(data["source_rows"], list)
        assert isinstance(data["fallback_rows"], list)


class TestPersonalizedRows:
    """Test personalized rows (tag-based patterns)."""

    def test_personalized_rows_detect_tag_patterns(self, client, auth_headers, test_user, db_session):
        """Test personalized rows detect user's tag patterns from saved recipes."""
        # Create recipes with tags
        recipe1 = Recipe(
            id=uuid4(),
            name="Indian Curry",
            source_type="manual",
            is_persisted=True,
            tags=["indian", "spicy"],
            times_cooked=5
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Indian Tikka",
            source_type="manual",
            is_persisted=True,
            tags=["indian", "grilled"],
            times_cooked=3
        )
        recipe3 = Recipe(
            id=uuid4(),
            name="Indian Biryani",
            source_type="manual",
            is_persisted=True,
            tags=["indian", "rice"],
            times_cooked=7
        )
        # Another recipe with indian tag (not saved)
        recipe4 = Recipe(
            id=uuid4(),
            name="Indian Dal",
            source_type="manual",
            is_persisted=True,
            tags=["indian", "vegetarian"],
            times_cooked=2
        )
        db_session.add_all([recipe1, recipe2, recipe3, recipe4])
        db_session.commit()

        # User saves 3 recipes with "indian" tag (meets >=3 threshold)
        rating1 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe1.id,
            rating=5.0
        )
        rating2 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe2.id,
            rating=4.0
        )
        rating3 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe3.id,
            rating=5.0
        )
        db_session.add_all([rating1, rating2, rating3])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have at least one personalized row for "indian" tag
        assert len(data["personalized_rows"]) >= 1

        # Check first row is for indian cuisine
        indian_row = data["personalized_rows"][0]
        assert "indian" in indian_row["title"].lower()
        assert indian_row["title"].endswith(".")  # Design system: period at end
        assert len(indian_row["recipes"]) >= 3  # Should include saved + non-saved

        # Row should include browse_url
        assert indian_row["browse_url"] is not None
        assert "tag=indian" in indian_row["browse_url"]

    def test_personalized_rows_mix_saved_and_non_saved(self, client, auth_headers, test_user, db_session):
        """Test personalized rows include both saved and non-saved recipes."""
        # Create multiple recipes with same tag
        recipes = []
        for i in range(8):
            recipe = Recipe(
                id=uuid4(),
                name=f"Vegan Recipe {i}",
                source_type="manual",
                is_persisted=True,
                tags=["vegan"],
                times_cooked=i + 1
            )
            recipes.append(recipe)
            db_session.add(recipe)
        db_session.commit()

        # User saves only first 3 (meets >=3 threshold)
        for i in range(3):
            rating = UserRecipeRating(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=recipes[i].id,
                rating=5.0
            )
            db_session.add(rating)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have personalized row for vegan tag
        assert len(data["personalized_rows"]) >= 1

        vegan_row = data["personalized_rows"][0]
        # Should have more than just saved recipes (includes non-saved for discovery)
        assert len(vegan_row["recipes"]) > 3

    def test_personalized_rows_respect_min_saves_threshold(self, client, auth_headers, test_user, db_session):
        """Test personalized rows only include tags with >=3 saved recipes."""
        # Create recipes with different tags
        recipe1 = Recipe(
            id=uuid4(),
            name="One Off Recipe",
            source_type="manual",
            is_persisted=True,
            tags=["rare_tag"],
            times_cooked=1
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Another One Off",
            source_type="manual",
            is_persisted=True,
            tags=["rare_tag"],
            times_cooked=1
        )
        db_session.add_all([recipe1, recipe2])
        db_session.commit()

        # User saves only 2 recipes with "rare_tag" (below threshold)
        rating1 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe1.id,
            rating=5.0
        )
        rating2 = UserRecipeRating(
            id=uuid4(),
            user_id=test_user.id,
            recipe_id=recipe2.id,
            rating=4.0
        )
        db_session.add_all([rating1, rating2])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should NOT have personalized row for "rare_tag" (below threshold)
        for row in data["personalized_rows"]:
            assert "rare_tag" not in row["title"].lower()

    def test_personalized_rows_max_limit(self, client, auth_headers, test_user, db_session):
        """Test personalized rows respect max limit of 4 rows."""
        # Create recipes with 5 different tags, all meeting threshold
        tags = ["italian", "mexican", "chinese", "japanese", "thai"]
        for tag in tags:
            for i in range(3):  # Create 3 recipes per tag to meet threshold
                recipe = Recipe(
                    id=uuid4(),
                    name=f"{tag.title()} Recipe {i}",
                    source_type="manual",
                    is_persisted=True,
                    tags=[tag],
                    times_cooked=i + 1
                )
                db_session.add(recipe)
                db_session.commit()

                # User saves all recipes
                rating = UserRecipeRating(
                    id=uuid4(),
                    user_id=test_user.id,
                    recipe_id=recipe.id,
                    rating=5.0
                )
                db_session.add(rating)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have at most 4 personalized rows (even though 5 tags qualify)
        assert len(data["personalized_rows"]) <= 4


class TestSourceRows:
    """Test source-specific rows."""

    def test_source_rows_detect_source_patterns(self, client, auth_headers, test_user, db_session):
        """Test source rows detect user's source patterns from saved recipes."""
        # Create 5 HelloFresh recipes (meets >=5 threshold)
        for i in range(5):
            recipe = Recipe(
                id=uuid4(),
                name=f"HelloFresh Recipe {i}",
                source_type="hellofresh_web",
                is_persisted=True,
                times_cooked=i + 1
            )
            db_session.add(recipe)
            db_session.commit()

            # User saves all
            rating = UserRecipeRating(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=recipe.id,
                rating=5.0
            )
            db_session.add(rating)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have at least one source row
        assert len(data["source_rows"]) >= 1

        # Check first row is for HelloFresh
        hf_row = data["source_rows"][0]
        assert "HelloFresh" in hf_row["title"]
        assert hf_row["title"].endswith(".")  # Design system
        assert len(hf_row["recipes"]) >= 5

        # Row should include browse_url
        assert hf_row["browse_url"] is not None
        assert "source=hellofresh" in hf_row["browse_url"]

    def test_source_rows_respect_min_saves_threshold(self, client, auth_headers, test_user, db_session):
        """Test source rows only include sources with >=5 saved recipes."""
        # Create 4 recipes from manual source (below threshold)
        for i in range(4):
            recipe = Recipe(
                id=uuid4(),
                name=f"Manual Recipe {i}",
                source_type="manual",
                is_persisted=True,
                times_cooked=i + 1
            )
            db_session.add(recipe)
            db_session.commit()

            rating = UserRecipeRating(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=recipe.id,
                rating=5.0
            )
            db_session.add(rating)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should NOT have source row for "manual" (below threshold)
        for row in data["source_rows"]:
            assert "manual" not in row["title"].lower()

    def test_source_rows_max_limit(self, client, auth_headers, test_user, db_session):
        """Test source rows respect max limit of 2 rows."""
        # Create 3 different sources, all meeting threshold
        sources = ["hellofresh_web", "kitchen_sanctuary", "url_import"]
        for source in sources:
            for i in range(5):  # Create 5 recipes per source
                recipe = Recipe(
                    id=uuid4(),
                    name=f"{source} Recipe {i}",
                    source_type=source,
                    is_persisted=True,
                    times_cooked=i + 1
                )
                db_session.add(recipe)
                db_session.commit()

                rating = UserRecipeRating(
                    id=uuid4(),
                    user_id=test_user.id,
                    recipe_id=recipe.id,
                    rating=5.0
                )
                db_session.add(rating)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have at most 2 source rows (even though 3 sources qualify)
        assert len(data["source_rows"]) <= 2


class TestFallbackRows:
    """Test fallback rows (Popular/Quick/New)."""

    def test_fallback_rows_include_popular_quick_new(self, client, auth_headers, test_user, db_session):
        """Test fallback rows include Popular, Quick, and New sections."""
        # Create popular recipe (high times_cooked)
        popular_recipe = Recipe(
            id=uuid4(),
            name="Very Popular Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=50,
            cook_time_minutes=45
        )
        # Create quick recipe (cook_time <= 30)
        quick_recipe = Recipe(
            id=uuid4(),
            name="Quick Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=5,
            cook_time_minutes=20
        )
        # Create new recipe (recent created_at)
        new_recipe = Recipe(
            id=uuid4(),
            name="Brand New Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=1,
            cook_time_minutes=60,
            created_at=datetime.now() - timedelta(hours=1)
        )
        db_session.add_all([popular_recipe, quick_recipe, new_recipe])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have 3 fallback rows
        assert len(data["fallback_rows"]) == 3

        # Check row titles
        titles = [row["title"] for row in data["fallback_rows"]]
        assert "Popular recipes." in titles
        assert "Quick meals." in titles
        assert "New recipes." in titles

        # Each row should have browse_url
        for row in data["fallback_rows"]:
            assert row["browse_url"] is not None

    def test_fallback_rows_popular_sorted_by_times_cooked(self, client, auth_headers, test_user, db_session):
        """Test Popular recipes row sorted by times_cooked descending."""
        # Create recipes with different times_cooked
        recipe1 = Recipe(
            id=uuid4(),
            name="Most Popular",
            source_type="manual",
            is_persisted=True,
            times_cooked=100
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Medium Popular",
            source_type="manual",
            is_persisted=True,
            times_cooked=50
        )
        recipe3 = Recipe(
            id=uuid4(),
            name="Less Popular",
            source_type="manual",
            is_persisted=True,
            times_cooked=10
        )
        db_session.add_all([recipe1, recipe2, recipe3])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find Popular recipes row
        popular_row = next(
            (row for row in data["fallback_rows"] if "Popular" in row["title"]),
            None
        )
        assert popular_row is not None

        # Should be sorted by times_cooked descending
        recipes = popular_row["recipes"]
        assert recipes[0]["name"] == "Most Popular"
        assert recipes[1]["name"] == "Medium Popular"
        assert recipes[2]["name"] == "Less Popular"

    def test_fallback_rows_quick_filtered_by_cook_time(self, client, auth_headers, test_user, db_session):
        """Test Quick meals row only includes recipes with cook_time <= 30."""
        # Create quick recipe
        quick_recipe = Recipe(
            id=uuid4(),
            name="Quick Recipe",
            source_type="manual",
            is_persisted=True,
            cook_time_minutes=25,
            times_cooked=5
        )
        # Create slow recipe
        slow_recipe = Recipe(
            id=uuid4(),
            name="Slow Recipe",
            source_type="manual",
            is_persisted=True,
            cook_time_minutes=60,
            times_cooked=10
        )
        db_session.add_all([quick_recipe, slow_recipe])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find Quick meals row
        quick_row = next(
            (row for row in data["fallback_rows"] if "Quick" in row["title"]),
            None
        )
        assert quick_row is not None

        # Should only include quick recipe
        recipe_names = [r["name"] for r in quick_row["recipes"]]
        assert "Quick Recipe" in recipe_names
        assert "Slow Recipe" not in recipe_names

    def test_fallback_rows_new_sorted_by_created_at(self, client, auth_headers, test_user, db_session):
        """Test New recipes row sorted by created_at descending."""
        # Create recipes with different created_at times
        recipe1 = Recipe(
            id=uuid4(),
            name="Newest",
            source_type="manual",
            is_persisted=True,
            created_at=datetime.now() - timedelta(hours=1)
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Middle",
            source_type="manual",
            is_persisted=True,
            created_at=datetime.now() - timedelta(days=1)
        )
        recipe3 = Recipe(
            id=uuid4(),
            name="Oldest",
            source_type="manual",
            is_persisted=True,
            created_at=datetime.now() - timedelta(days=7)
        )
        db_session.add_all([recipe1, recipe2, recipe3])
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/home", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find New recipes row
        new_row = next(
            (row for row in data["fallback_rows"] if "New" in row["title"]),
            None
        )
        assert new_row is not None

        # Should be sorted by created_at descending
        recipes = new_row["recipes"]
        assert recipes[0]["name"] == "Newest"
        assert recipes[1]["name"] == "Middle"
        assert recipes[2]["name"] == "Oldest"


class TestBrowseEndpoint:
    """Test /feed/browse endpoint."""

    def test_browse_requires_authentication(self, client):
        """Test browse endpoint requires authentication."""
        response = client.get("/feed/browse")
        assert response.status_code == 401

    def test_browse_returns_all_sections(self, client, auth_headers, test_user, db_session):
        """Test browse endpoint returns all carousel sections."""
        # Create some recipes for fallback rows
        recipe = Recipe(
            id=uuid4(),
            name="Test Recipe",
            source_type="manual",
            is_persisted=True,
            times_cooked=10,
            cook_time_minutes=25
        )
        db_session.add(recipe)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/browse", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have sections field
        assert "sections" in data
        assert isinstance(data["sections"], list)

        # Should have at least fallback rows
        assert len(data["sections"]) >= 1

    def test_browse_combines_personalized_source_fallback(self, client, auth_headers, test_user, db_session):
        """Test browse endpoint combines personalized, source, and fallback rows."""
        # Create recipes with tags (for personalized rows)
        for i in range(3):
            recipe = Recipe(
                id=uuid4(),
                name=f"Italian Recipe {i}",
                source_type="manual",
                is_persisted=True,
                tags=["italian"],
                times_cooked=i + 1,  # Needed for "Popular recipes" row
                cook_time_minutes=25  # Needed for "Quick meals" row
            )
            db_session.add(recipe)
            db_session.commit()

            rating = UserRecipeRating(
                id=uuid4(),
                user_id=test_user.id,
                recipe_id=recipe.id,
                rating=5.0
            )
            db_session.add(rating)
        db_session.commit()

        # Call endpoint
        response = client.get("/feed/browse", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have multiple sections (personalized + fallback)
        assert len(data["sections"]) >= 4  # At least 1 personalized + 3 fallback

        # Sections should have required fields
        for section in data["sections"]:
            assert "title" in section
            assert "recipes" in section
            assert section["title"].endswith(".")  # Design system
