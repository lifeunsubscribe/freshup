"""
Integration tests for menu endpoints.

Tests cover:
- GET /menus: list user's menus
- POST /menus: create manual menu
- PUT /menus/{id}: update menu
- DELETE /menus/{id}: delete menu and cascade to MenuRecipe entries
- GET /menus/{id}/recipes: get recipes in menu with pagination
- POST /menus/{id}/recipes: add recipe to menu with manual override logic
- DELETE /menus/{id}/recipes/{recipe_id}: remove recipe with manual override logic
- Filter rule evaluation (tags, source_type, cook_time_minutes)
- Authentication and ownership requirements
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
from src.db.models.menu import Menu, MenuRecipe
from src.db.models.user_recipe import UserRecipeRelation
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import menus as menus_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the menus router
app.include_router(menus_router.router)


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
        role=UserRole.member,
        hashed_password=hash_password("password123")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    """Create another test user for ownership tests."""
    user = User(
        id=uuid4(),
        name="Other User",
        email="other@example.com",
        role=UserRole.member,
        hashed_password=hash_password("password123")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(other_user):
    """Create authentication headers for other user."""
    token = create_access_token({"sub": str(other_user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_get_menus_empty(client, auth_headers):
    """Test getting menus when user has none."""
    response = client.get("/menus", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["menus"] == []
    assert data["total"] == 0


def test_create_manual_menu(client, auth_headers, test_user, db_session):
    """Test creating a manual menu."""
    menu_data = {
        "name": "My Favorites",
        "description": "My favorite recipes",
        "is_auto_generated": False,
        "sort_order": 0
    }

    response = client.post("/menus", json=menu_data, headers=auth_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "My Favorites"
    assert data["description"] == "My favorite recipes"
    assert data["is_auto_generated"] is False
    assert data["user_id"] == str(test_user.id)

    # Verify in database
    menu = db_session.query(Menu).filter(Menu.user_id == test_user.id).first()
    assert menu is not None
    assert menu.name == "My Favorites"


def test_create_menu_with_filter_rules(client, auth_headers, test_user, db_session):
    """Test creating a menu with filter rules."""
    menu_data = {
        "name": "Quick Meals",
        "description": "Recipes under 30 minutes",
        "filter_rules": {
            "match_logic": "all",
            "rules": [
                {
                    "field": "cook_time_minutes",
                    "operator": "<=",
                    "value": 30
                }
            ]
        },
        "is_auto_generated": False
    }

    response = client.post("/menus", json=menu_data, headers=auth_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["filter_rules"] is not None
    assert data["filter_rules"]["match_logic"] == "all"
    assert len(data["filter_rules"]["rules"]) == 1


def test_get_menus_sorted(client, auth_headers, test_user, db_session):
    """Test getting menus returns them sorted by sort_order."""
    # Create menus with different sort orders
    menu1 = Menu(user_id=test_user.id, name="Second", sort_order=2)
    menu2 = Menu(user_id=test_user.id, name="First", sort_order=1)
    menu3 = Menu(user_id=test_user.id, name="Third", sort_order=3)
    db_session.add_all([menu1, menu2, menu3])
    db_session.commit()

    response = client.get("/menus", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert len(data["menus"]) == 3
    assert data["menus"][0]["name"] == "First"
    assert data["menus"][1]["name"] == "Second"
    assert data["menus"][2]["name"] == "Third"


def test_update_menu(client, auth_headers, test_user, db_session):
    """Test updating a menu."""
    menu = Menu(user_id=test_user.id, name="Old Name", description="Old desc")
    db_session.add(menu)
    db_session.commit()
    db_session.refresh(menu)

    update_data = {
        "name": "New Name",
        "description": "New description",
        "sort_order": 5
    }

    response = client.put(f"/menus/{menu.id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "New description"
    assert data["sort_order"] == 5

    # Verify in database
    db_session.refresh(menu)
    assert menu.name == "New Name"


def test_update_menu_not_found(client, auth_headers):
    """Test updating a non-existent menu returns 404."""
    fake_id = uuid4()
    response = client.put(f"/menus/{fake_id}", json={"name": "New"}, headers=auth_headers)
    assert response.status_code == 404


def test_update_menu_non_owner(client, other_auth_headers, test_user, db_session):
    """Test that non-owner cannot update a menu."""
    menu = Menu(user_id=test_user.id, name="Test Menu")
    db_session.add(menu)
    db_session.commit()

    response = client.put(f"/menus/{menu.id}", json={"name": "Hacked"}, headers=other_auth_headers)
    assert response.status_code == 404


def test_delete_menu(client, auth_headers, test_user, db_session):
    """Test deleting a menu."""
    menu = Menu(user_id=test_user.id, name="To Delete")
    db_session.add(menu)
    db_session.commit()
    menu_id = menu.id

    response = client.delete(f"/menus/{menu_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify deleted from database
    menu = db_session.query(Menu).filter(Menu.id == menu_id).first()
    assert menu is None


def test_delete_menu_cascades_to_menu_recipes(client, auth_headers, test_user, db_session):
    """Test that deleting a menu cascades to MenuRecipe entries."""
    menu = Menu(user_id=test_user.id, name="To Delete")
    recipe = Recipe(name="Test Recipe", source_type="manual", created_by=test_user.id)
    db_session.add_all([menu, recipe])
    db_session.commit()

    menu_recipe = MenuRecipe(menu_id=menu.id, recipe_id=recipe.id)
    db_session.add(menu_recipe)
    db_session.commit()

    menu_id = menu.id

    response = client.delete(f"/menus/{menu_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify MenuRecipe entry is also deleted
    menu_recipe = db_session.query(MenuRecipe).filter(MenuRecipe.menu_id == menu_id).first()
    assert menu_recipe is None


def test_delete_menu_non_owner(client, other_auth_headers, test_user, db_session):
    """Test that non-owner cannot delete a menu."""
    menu = Menu(user_id=test_user.id, name="Protected")
    db_session.add(menu)
    db_session.commit()

    response = client.delete(f"/menus/{menu.id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_get_menu_recipes(client, auth_headers, test_user, db_session):
    """Test getting recipes in a menu."""
    menu = Menu(user_id=test_user.id, name="Test Menu")
    recipe1 = Recipe(name="Recipe 1", source_type="manual", created_by=test_user.id)
    recipe2 = Recipe(name="Recipe 2", source_type="manual", created_by=test_user.id)
    db_session.add_all([menu, recipe1, recipe2])
    db_session.commit()

    mr1 = MenuRecipe(menu_id=menu.id, recipe_id=recipe1.id, sort_order=1)
    mr2 = MenuRecipe(menu_id=menu.id, recipe_id=recipe2.id, sort_order=0)
    db_session.add_all([mr1, mr2])
    db_session.commit()

    response = client.get(f"/menus/{menu.id}/recipes", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 2
    assert len(data["recipes"]) == 2
    # Should be sorted by sort_order
    assert data["recipes"][0]["name"] == "Recipe 2"  # sort_order=0
    assert data["recipes"][1]["name"] == "Recipe 1"  # sort_order=1


def test_get_menu_recipes_excludes_manually_removed(client, auth_headers, test_user, db_session):
    """Test that manually_removed recipes are excluded from results."""
    menu = Menu(user_id=test_user.id, name="Test Menu")
    recipe1 = Recipe(name="Visible", source_type="manual", created_by=test_user.id)
    recipe2 = Recipe(name="Hidden", source_type="manual", created_by=test_user.id)
    db_session.add_all([menu, recipe1, recipe2])
    db_session.commit()

    mr1 = MenuRecipe(menu_id=menu.id, recipe_id=recipe1.id, manually_removed=False)
    mr2 = MenuRecipe(menu_id=menu.id, recipe_id=recipe2.id, manually_removed=True)
    db_session.add_all([mr1, mr2])
    db_session.commit()

    response = client.get(f"/menus/{menu.id}/recipes", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["recipes"][0]["name"] == "Visible"


def test_add_recipe_to_menu(client, auth_headers, test_user, db_session):
    """Test adding a recipe to a menu."""
    menu = Menu(user_id=test_user.id, name="Test Menu")
    recipe = Recipe(name="Test Recipe", source_type="manual", created_by=test_user.id)
    db_session.add_all([menu, recipe])
    db_session.commit()

    add_data = {
        "recipe_id": str(recipe.id),
        "sort_order": 0
    }

    response = client.post(f"/menus/{menu.id}/recipes", json=add_data, headers=auth_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["recipe_id"] == str(recipe.id)
    assert data["menu_id"] == str(menu.id)

    # Verify in database
    menu_recipe = db_session.query(MenuRecipe).filter(
        MenuRecipe.menu_id == menu.id,
        MenuRecipe.recipe_id == recipe.id
    ).first()
    assert menu_recipe is not None


def test_add_recipe_sets_manually_added_if_not_matching_filter(client, auth_headers, test_user, db_session):
    """Test that manually_added is set when recipe doesn't match filter rules."""
    # Menu with filter: cook_time <= 30
    menu = Menu(
        user_id=test_user.id,
        name="Quick Meals",
        filter_rules={
            "match_logic": "all",
            "rules": [
                {"field": "cook_time_minutes", "operator": "<=", "value": 30}
            ]
        }
    )
    # Recipe with cook_time > 30 (doesn't match filter)
    recipe = Recipe(name="Slow Recipe", source_type="manual", cook_time_minutes=60, created_by=test_user.id)
    db_session.add_all([menu, recipe])
    db_session.commit()

    add_data = {"recipe_id": str(recipe.id), "sort_order": 0}

    response = client.post(f"/menus/{menu.id}/recipes", json=add_data, headers=auth_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["manually_added"] is True


def test_add_recipe_doesnt_set_manually_added_if_matching_filter(client, auth_headers, test_user, db_session):
    """Test that manually_added is False when recipe matches filter rules."""
    # Menu with filter: cook_time <= 30
    menu = Menu(
        user_id=test_user.id,
        name="Quick Meals",
        filter_rules={
            "match_logic": "all",
            "rules": [
                {"field": "cook_time_minutes", "operator": "<=", "value": 30}
            ]
        }
    )
    # Recipe with cook_time <= 30 (matches filter)
    recipe = Recipe(name="Quick Recipe", source_type="manual", cook_time_minutes=20, created_by=test_user.id)
    db_session.add_all([menu, recipe])
    db_session.commit()

    add_data = {"recipe_id": str(recipe.id), "sort_order": 0}

    response = client.post(f"/menus/{menu.id}/recipes", json=add_data, headers=auth_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["manually_added"] is False


def test_remove_recipe_from_menu_deletes_if_not_matching(client, auth_headers, test_user, db_session):
    """Test that removing a non-matching recipe deletes the MenuRecipe entry."""
    menu = Menu(
        user_id=test_user.id,
        name="Quick Meals",
        filter_rules={
            "match_logic": "all",
            "rules": [
                {"field": "cook_time_minutes", "operator": "<=", "value": 30}
            ]
        }
    )
    # Recipe doesn't match filter (cook_time > 30)
    recipe = Recipe(name="Slow Recipe", source_type="manual", cook_time_minutes=60, created_by=test_user.id)
    db_session.add_all([menu, recipe])
    db_session.commit()

    menu_recipe = MenuRecipe(menu_id=menu.id, recipe_id=recipe.id, manually_added=True)
    db_session.add(menu_recipe)
    db_session.commit()

    response = client.delete(f"/menus/{menu.id}/recipes/{recipe.id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify entry is deleted
    menu_recipe = db_session.query(MenuRecipe).filter(
        MenuRecipe.menu_id == menu.id,
        MenuRecipe.recipe_id == recipe.id
    ).first()
    assert menu_recipe is None


def test_remove_recipe_from_menu_sets_manually_removed_if_matching(client, auth_headers, test_user, db_session):
    """Test that removing a matching recipe sets manually_removed instead of deleting."""
    menu = Menu(
        user_id=test_user.id,
        name="Quick Meals",
        filter_rules={
            "match_logic": "all",
            "rules": [
                {"field": "cook_time_minutes", "operator": "<=", "value": 30}
            ]
        }
    )
    # Recipe matches filter (cook_time <= 30)
    recipe = Recipe(name="Quick Recipe", source_type="manual", cook_time_minutes=20, created_by=test_user.id)
    db_session.add_all([menu, recipe])
    db_session.commit()

    menu_recipe = MenuRecipe(menu_id=menu.id, recipe_id=recipe.id, manually_added=False)
    db_session.add(menu_recipe)
    db_session.commit()

    response = client.delete(f"/menus/{menu.id}/recipes/{recipe.id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify entry still exists but manually_removed is True
    db_session.refresh(menu_recipe)
    assert menu_recipe.manually_removed is True

def test_filter_evaluation_tags_contains(client, auth_headers, test_user, db_session):
    """Test filter rule evaluation: tags contains."""
    menu = Menu(
        user_id=test_user.id,
        name="Italian Menu",
        filter_rules={
            "match_logic": "all",
            "rules": [{"field": "tags", "operator": "contains", "value": "italian"}]
        }
    )
    matching_recipe = Recipe(name="Pasta", source_type="manual", tags=["italian", "pasta"], created_by=test_user.id)
    non_matching_recipe = Recipe(name="Curry", source_type="manual", tags=["indian"], created_by=test_user.id)
    db_session.add_all([menu, matching_recipe, non_matching_recipe])
    db_session.commit()

    # Add matching recipe - should have manually_added=False
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is False

    # Add non-matching recipe - should have manually_added=True
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(non_matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is True


def test_filter_evaluation_source_type_eq(client, auth_headers, test_user, db_session):
    """Test filter rule evaluation: source_type eq."""
    menu = Menu(
        user_id=test_user.id,
        name="HelloFresh Menu",
        filter_rules={
            "match_logic": "all",
            "rules": [{"field": "source_type", "operator": "eq", "value": "hellofresh_card"}]
        }
    )
    matching_recipe = Recipe(name="HF Recipe", source_type="hellofresh_card", created_by=test_user.id)
    non_matching_recipe = Recipe(name="Manual Recipe", source_type="manual", created_by=test_user.id)
    db_session.add_all([menu, matching_recipe, non_matching_recipe])
    db_session.commit()

    # Add matching recipe
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is False

    # Add non-matching recipe
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(non_matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is True


def test_filter_evaluation_cook_time_lte(client, auth_headers, test_user, db_session):
    """Test filter rule evaluation: cook_time_minutes <=."""
    menu = Menu(
        user_id=test_user.id,
        name="Quick Meals",
        filter_rules={
            "match_logic": "all",
            "rules": [{"field": "cook_time_minutes", "operator": "<=", "value": 30}]
        }
    )
    matching_recipe = Recipe(name="Quick Recipe", source_type="manual", cook_time_minutes=20, created_by=test_user.id)
    non_matching_recipe = Recipe(name="Slow Recipe", source_type="manual", cook_time_minutes=60, created_by=test_user.id)
    db_session.add_all([menu, matching_recipe, non_matching_recipe])
    db_session.commit()

    # Add matching recipe
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is False

    # Add non-matching recipe
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(non_matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is True


def test_filter_evaluation_match_logic_all(client, auth_headers, test_user, db_session):
    """Test filter rule evaluation: match_logic 'all' (AND)."""
    menu = Menu(
        user_id=test_user.id,
        name="Quick Italian",
        filter_rules={
            "match_logic": "all",
            "rules": [
                {"field": "tags", "operator": "contains", "value": "italian"},
                {"field": "cook_time_minutes", "operator": "<=", "value": 30}
            ]
        }
    )
    # Matches both rules
    matching_recipe = Recipe(
        name="Quick Pasta",
        source_type="manual",
        tags=["italian"],
        cook_time_minutes=20,
        created_by=test_user.id
    )
    # Matches only one rule (italian but > 30 minutes)
    non_matching_recipe = Recipe(
        name="Slow Pasta",
        source_type="manual",
        tags=["italian"],
        cook_time_minutes=60,
        created_by=test_user.id
    )
    db_session.add_all([menu, matching_recipe, non_matching_recipe])
    db_session.commit()

    # Add matching recipe
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is False

    # Add non-matching recipe (only matches 1 of 2 rules with AND logic)
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(non_matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is True


def test_filter_evaluation_match_logic_any(client, auth_headers, test_user, db_session):
    """Test filter rule evaluation: match_logic 'any' (OR)."""
    menu = Menu(
        user_id=test_user.id,
        name="Italian or Quick",
        filter_rules={
            "match_logic": "any",
            "rules": [
                {"field": "tags", "operator": "contains", "value": "italian"},
                {"field": "cook_time_minutes", "operator": "<=", "value": 30}
            ]
        }
    )
    # Matches first rule only
    matching_recipe1 = Recipe(
        name="Slow Pasta",
        source_type="manual",
        tags=["italian"],
        cook_time_minutes=60,
        created_by=test_user.id
    )
    # Matches second rule only
    matching_recipe2 = Recipe(
        name="Quick Curry",
        source_type="manual",
        tags=["indian"],
        cook_time_minutes=20,
        created_by=test_user.id
    )
    # Matches neither rule
    non_matching_recipe = Recipe(
        name="Slow Curry",
        source_type="manual",
        tags=["indian"],
        cook_time_minutes=60,
        created_by=test_user.id
    )
    db_session.add_all([menu, matching_recipe1, matching_recipe2, non_matching_recipe])
    db_session.commit()

    # Add matching recipe 1
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(matching_recipe1.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is False

    # Add matching recipe 2
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(matching_recipe2.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is False

    # Add non-matching recipe
    response = client.post(
        f"/menus/{menu.id}/recipes",
        json={"recipe_id": str(non_matching_recipe.id)},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["manually_added"] is True

