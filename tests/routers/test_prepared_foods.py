"""
Integration tests for prepared food endpoints.

Tests cover:
- POST /prepared-foods: create items with validation
- GET /prepared-foods: list items with shareability-aware filtering
- GET /prepared-foods/{id}: get single item with shareability-aware access
- PUT /prepared-foods/{id}: update items (owner-only)
- DELETE /prepared-foods/{id}: delete item (owner-only)
- Shareability-aware permissions (shared visible to all, personal/reserved to owner only)
- Filters (type, storage_location, shareability)
- Combined filter validation (invalid enum values, multiple filters with AND logic)
- Pagination (limit, offset)
- Authentication requirements
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.prepared_food import PreparedFood
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import prepared_foods_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the prepared_foods router
app.include_router(prepared_foods_router)


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


class TestCreatePreparedFood:
    """Tests for POST /prepared-foods (create prepared food item)."""

    def test_create_prepared_food(self, client, auth_headers, test_user, db_session):
        """Should create prepared food item and auto-set prepared_by to current user."""
        payload = {
            "name": "Leftover curry",
            "type": "complete_meal",
            "servings_remaining": 3.0,
            "storage_location": "fridge",
            "shareability": "shared",
        }

        response = client.post("/prepared-foods", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Leftover curry"
        assert data["type"] == "complete_meal"
        assert data["servings_remaining"] == 3.0
        assert data["storage_location"] == "fridge"
        assert data["shareability"] == "shared"
        assert data["prepared_by"] == str(test_user.id)

        # Verify in database
        item = db_session.query(PreparedFood).filter_by(id=UUID(data["id"])).first()
        assert item is not None
        assert item.prepared_by == test_user.id

    def test_create_with_defaults(self, client, auth_headers, test_user):
        """Should create item with default shareability value."""
        payload = {
            "name": "Batch chili",
            "type": "batch_portion",
            "servings_remaining": 8.0,
            "storage_location": "freezer",
        }

        response = client.post("/prepared-foods", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["shareability"] == "shared"  # Default value

    def test_create_requires_auth(self, client):
        """Should reject request without authentication."""
        payload = {
            "name": "Leftover pasta",
            "type": "complete_meal",
            "servings_remaining": 2.0,
            "storage_location": "fridge",
        }

        response = client.post("/prepared-foods", json=payload)

        assert response.status_code == 401

    def test_create_invalid_type(self, client, auth_headers):
        """Should reject invalid type enum value."""
        payload = {
            "name": "Test item",
            "type": "invalid_type",
            "servings_remaining": 1.0,
            "storage_location": "fridge",
        }

        response = client.post("/prepared-foods", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_invalid_storage_location(self, client, auth_headers):
        """Should reject invalid storage_location enum value."""
        payload = {
            "name": "Test item",
            "type": "complete_meal",
            "servings_remaining": 1.0,
            "storage_location": "garage",
        }

        response = client.post("/prepared-foods", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_negative_servings(self, client, auth_headers):
        """Should reject negative servings_remaining."""
        payload = {
            "name": "Test item",
            "type": "complete_meal",
            "servings_remaining": -1.0,
            "storage_location": "fridge",
        }

        response = client.post("/prepared-foods", json=payload, headers=auth_headers)

        assert response.status_code == 422


class TestListPreparedFoods:
    """Tests for GET /prepared-foods (list with shareability-aware filtering)."""

    def test_list_includes_shared_items_from_all_users(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Should return shared items from all users."""
        # Create shared item from user1
        item1 = PreparedFood(
            id=uuid4(),
            name="User1 shared curry",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        # Create shared item from user2
        item2 = PreparedFood(
            id=uuid4(),
            name="User2 shared chili",
            type="batch_portion",
            servings_remaining=8.0,
            storage_location="freezer",
            shareability="shared",
            prepared_by=test_user2.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # User1 should see both shared items
        response = client.get("/prepared-foods", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert "User1 shared curry" in names
        assert "User2 shared chili" in names

        # User2 should also see both shared items
        response = client.get("/prepared-foods", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_includes_personal_items_only_for_owner(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Should return personal/reserved items only to their owner."""
        # Create personal item from user1
        item1 = PreparedFood(
            id=uuid4(),
            name="User1 personal meal",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        # Create reserved item from user2
        item2 = PreparedFood(
            id=uuid4(),
            name="User2 reserved batch",
            type="batch_portion",
            servings_remaining=4.0,
            storage_location="freezer",
            shareability="reserved",
            prepared_by=test_user2.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # User1 should only see their own personal item
        response = client.get("/prepared-foods", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User1 personal meal"

        # User2 should only see their own reserved item
        response = client.get("/prepared-foods", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User2 reserved batch"

    def test_list_filters(self, client, auth_headers, test_user, db_session):
        """Should filter by type, storage_location, shareability."""
        # Create diverse items
        items = [
            PreparedFood(id=uuid4(), name="Meal1", type="complete_meal", servings_remaining=1.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Batch1", type="batch_portion", servings_remaining=5.0, storage_location="freezer", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Component1", type="component_ingredient", servings_remaining=10.0, storage_location="fridge", shareability="personal", prepared_by=test_user.id),
        ]
        db_session.add_all(items)
        db_session.commit()

        # Filter by type
        response = client.get("/prepared-foods?type=complete_meal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "complete_meal"

        # Filter by storage_location
        response = client.get("/prepared-foods?storage_location=freezer", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["storage_location"] == "freezer"

        # Filter by shareability
        response = client.get("/prepared-foods?shareability=personal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["shareability"] == "personal"

    def test_list_pagination(self, client, auth_headers, test_user, db_session):
        """Should support limit and offset pagination."""
        # Create multiple items
        items = [
            PreparedFood(id=uuid4(), name=f"Item{i}", type="complete_meal", servings_remaining=1.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id)
            for i in range(10)
        ]
        db_session.add_all(items)
        db_session.commit()

        # Get first page
        response = client.get("/prepared-foods?limit=5&offset=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

        # Get second page
        response = client.get("/prepared-foods?limit=5&offset=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    def test_list_requires_auth(self, client):
        """Should reject request without authentication."""
        response = client.get("/prepared-foods")
        assert response.status_code == 401


class TestListPreparedFoodsFilterCombinations:
    """Tests for GET /prepared-foods with combined and invalid filter parameters."""

    def test_combined_filters_valid(self, client, auth_headers, test_user, db_session):
        """Should apply multiple filters together with AND logic."""
        # Create diverse items
        items = [
            PreparedFood(id=uuid4(), name="Meal1", type="complete_meal", servings_remaining=1.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Batch1", type="batch_portion", servings_remaining=5.0, storage_location="freezer", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Component1", type="component_ingredient", servings_remaining=10.0, storage_location="fridge", shareability="personal", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Meal2", type="complete_meal", servings_remaining=2.0, storage_location="fridge", shareability="personal", prepared_by=test_user.id),
        ]
        db_session.add_all(items)
        db_session.commit()

        # Combine type + storage_location
        response = client.get("/prepared-foods?type=complete_meal&storage_location=fridge", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for item in data:
            assert item["type"] == "complete_meal"
            assert item["storage_location"] == "fridge"

        # Combine all three filters
        response = client.get("/prepared-foods?type=complete_meal&storage_location=fridge&shareability=personal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Meal2"
        assert data[0]["type"] == "complete_meal"
        assert data[0]["storage_location"] == "fridge"
        assert data[0]["shareability"] == "personal"

    def test_combined_filters_no_matches(self, client, auth_headers, test_user, db_session):
        """Should return empty list when combined filters match no items."""
        # Create items
        items = [
            PreparedFood(id=uuid4(), name="Meal1", type="complete_meal", servings_remaining=1.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Batch1", type="batch_portion", servings_remaining=5.0, storage_location="freezer", shareability="shared", prepared_by=test_user.id),
        ]
        db_session.add_all(items)
        db_session.commit()

        # Search for combination that doesn't exist
        response = client.get("/prepared-foods?type=complete_meal&storage_location=freezer", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

        # Another non-matching combination
        response = client.get("/prepared-foods?type=component_ingredient&shareability=shared", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_invalid_type_filter(self, client, auth_headers):
        """Should reject invalid type enum value with 422."""
        response = client.get("/prepared-foods?type=invalid_type", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        # Assert validation error detail exists and has proper structure
        assert "detail" in data
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        # Verify the error is specifically about the 'type' field (semantic validation)
        assert any("type" in error.get("loc", []) for error in data["detail"])

    def test_invalid_storage_location_filter(self, client, auth_headers):
        """Should reject invalid storage_location enum value with 422."""
        response = client.get("/prepared-foods?storage_location=garage", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        # Assert validation error detail exists and has proper structure
        assert "detail" in data
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        # Verify the error is specifically about the 'storage_location' field (semantic validation)
        assert any("storage_location" in error.get("loc", []) for error in data["detail"])

    def test_invalid_shareability_filter(self, client, auth_headers):
        """Should reject invalid shareability enum value with 422."""
        response = client.get("/prepared-foods?shareability=public", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        # Assert validation error detail exists and has proper structure
        assert "detail" in data
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        # Verify the error is specifically about the 'shareability' field (semantic validation)
        assert any("shareability" in error.get("loc", []) for error in data["detail"])

    def test_combined_filters_with_pagination(self, client, auth_headers, test_user, db_session):
        """Should apply filters and pagination together correctly."""
        # Create multiple items of the same type
        items = [
            PreparedFood(id=uuid4(), name=f"Meal{i}", type="complete_meal", servings_remaining=1.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id)
            for i in range(10)
        ]
        db_session.add_all(items)
        db_session.commit()

        # Get first page with filter
        response = client.get("/prepared-foods?type=complete_meal&limit=5&offset=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        for item in data:
            assert item["type"] == "complete_meal"

        # Get second page with filter
        response = client.get("/prepared-foods?type=complete_meal&limit=5&offset=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        for item in data:
            assert item["type"] == "complete_meal"

        # Get beyond available items
        response = client.get("/prepared-foods?type=complete_meal&limit=5&offset=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_invalid_filter_with_valid_filters(self, client, auth_headers, test_user, db_session):
        """Should reject request if any filter is invalid, even if others are valid."""
        # Create item
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # Valid type but invalid storage_location
        response = client.get("/prepared-foods?type=complete_meal&storage_location=garage", headers=auth_headers)
        assert response.status_code == 422

        # Valid shareability but invalid type
        response = client.get("/prepared-foods?shareability=shared&type=invalid_type", headers=auth_headers)
        assert response.status_code == 422


class TestGetPreparedFood:
    """Tests for GET /prepared-foods/{id} (get single item with shareability-aware access)."""

    def test_get_shared_item_by_any_user(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Should allow any user to read shared items."""
        # Create shared item from user1
        item = PreparedFood(
            id=uuid4(),
            name="Shared curry",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # User1 (owner) should be able to read
        response = client.get(f"/prepared-foods/{item.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Shared curry"

        # User2 (non-owner) should also be able to read shared item
        response = client.get(f"/prepared-foods/{item.id}", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Shared curry"

    def test_get_personal_item_only_by_owner(self, client, auth_headers, auth_headers2, test_user, db_session):
        """Should only allow owner to read personal items."""
        # Create personal item from user1
        item = PreparedFood(
            id=uuid4(),
            name="Personal meal",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # User1 (owner) should be able to read
        response = client.get(f"/prepared-foods/{item.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Personal meal"

        # User2 (non-owner) should get 404
        response = client.get(f"/prepared-foods/{item.id}", headers=auth_headers2)
        assert response.status_code == 404

    def test_get_nonexistent_item(self, client, auth_headers):
        """Should return 404 for nonexistent item."""
        fake_id = uuid4()
        response = client.get(f"/prepared-foods/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_get_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get(f"/prepared-foods/{item.id}")
        assert response.status_code == 401


class TestUpdatePreparedFood:
    """Tests for PUT /prepared-foods/{id} (update, owner-only)."""

    def test_update_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to update their item."""
        item = PreparedFood(
            id=uuid4(),
            name="Original name",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {
            "name": "Updated name",
            "servings_remaining": 2.0,
        }

        response = client.put(f"/prepared-foods/{item.id}", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated name"
        assert data["servings_remaining"] == 2.0
        assert data["storage_location"] == "fridge"  # Unchanged

    def test_update_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject update by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"name": "Hacked name"}

        # User2 tries to update user1's item
        response = client.put(f"/prepared-foods/{item.id}", json=payload, headers=auth_headers2)
        assert response.status_code == 404

    def test_update_nonexistent_item(self, client, auth_headers):
        """Should return 404 for nonexistent item."""
        fake_id = uuid4()
        payload = {"name": "Test"}

        response = client.put(f"/prepared-foods/{fake_id}", json=payload, headers=auth_headers)
        assert response.status_code == 404

    def test_update_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"name": "New name"}
        response = client.put(f"/prepared-foods/{item.id}", json=payload)
        assert response.status_code == 401


class TestDeletePreparedFood:
    """Tests for DELETE /prepared-foods/{id} (delete, owner-only)."""

    def test_delete_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to delete their item."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.delete(f"/prepared-foods/{item_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify item is deleted
        deleted_item = db_session.query(PreparedFood).filter_by(id=item_id).first()
        assert deleted_item is None

    def test_delete_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject delete by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # User2 tries to delete user1's item
        response = client.delete(f"/prepared-foods/{item.id}", headers=auth_headers2)
        assert response.status_code == 404

        # Verify item still exists
        existing_item = db_session.query(PreparedFood).filter_by(id=item.id).first()
        assert existing_item is not None

    def test_delete_nonexistent_item(self, client, auth_headers):
        """Should return 404 for nonexistent item."""
        fake_id = uuid4()
        response = client.delete(f"/prepared-foods/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.delete(f"/prepared-foods/{item.id}")
        assert response.status_code == 401


class TestConsumePreparedFood:
    """Tests for POST /prepared-foods/{id}/consume (consume with shareability-aware permissions)."""

    def test_consume_shared_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to consume shared item."""
        item = PreparedFood(
            id=uuid4(),
            name="Shared curry",
            type="complete_meal",
            servings_remaining=5.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        payload = {"amount": 2.0, "delete_when_empty": False}
        response = client.post(f"/prepared-foods/{item_id}/consume", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["item"]["servings_remaining"] == 3.0
        assert "Consumed 2.0 servings" in data["message"]

    def test_consume_shared_by_other_user(self, client, auth_headers2, test_user, db_session):
        """Should allow any authenticated user to consume shared items."""
        item = PreparedFood(
            id=uuid4(),
            name="Shared meal",
            type="complete_meal",
            servings_remaining=4.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # User2 consumes user1's shared item
        payload = {"amount": 1.0, "delete_when_empty": False}
        response = client.post(f"/prepared-foods/{item_id}/consume", json=payload, headers=auth_headers2)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["item"]["servings_remaining"] == 3.0

    def test_consume_personal_by_other_user(self, client, auth_headers2, test_user, db_session):
        """Should reject consumption of personal items by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="Personal meal",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # User2 tries to consume user1's personal item
        payload = {"amount": 1.0}
        response = client.post(f"/prepared-foods/{item.id}/consume", json=payload, headers=auth_headers2)

        assert response.status_code == 404

    def test_consume_reserved_by_other_user(self, client, auth_headers2, test_user, db_session):
        """Should reject consumption of reserved items by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="Reserved meal",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # User2 tries to consume user1's reserved item
        payload = {"amount": 1.0}
        response = client.post(f"/prepared-foods/{item.id}/consume", json=payload, headers=auth_headers2)

        assert response.status_code == 404

    def test_consume_exceeds_available(self, client, auth_headers, test_user, db_session):
        """Should return 400 if amount exceeds servings_remaining."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"amount": 3.0}
        response = client.post(f"/prepared-foods/{item.id}/consume", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert "Cannot consume 3.0 servings" in response.json()["detail"]

    def test_consume_with_delete_when_empty_true(self, client, auth_headers, test_user, db_session):
        """Should delete item when servings reach 0 and delete_when_empty is true."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        payload = {"amount": 2.0, "delete_when_empty": True}
        response = client.post(f"/prepared-foods/{item_id}/consume", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["item"] is None
        assert "Item deleted" in data["message"]

        # Verify item is deleted from database
        deleted_item = db_session.query(PreparedFood).filter_by(id=item_id).first()
        assert deleted_item is None

    def test_consume_with_delete_when_empty_false(self, client, auth_headers, test_user, db_session):
        """Should keep item at 0 servings when delete_when_empty is false."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        payload = {"amount": 2.0, "delete_when_empty": False}
        response = client.post(f"/prepared-foods/{item_id}/consume", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["item"]["servings_remaining"] == 0.0

        # Verify item still exists in database
        existing_item = db_session.query(PreparedFood).filter_by(id=item_id).first()
        assert existing_item is not None
        assert existing_item.servings_remaining == 0.0

    def test_consume_default_amount(self, client, auth_headers, test_user, db_session):
        """Should use default amount of 1.0 when not specified."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        # No payload - use defaults
        response = client.post(f"/prepared-foods/{item.id}/consume", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["item"]["servings_remaining"] == 2.0

    def test_consume_default_delete_when_empty(self, client, auth_headers, test_user, db_session):
        """Should default to delete_when_empty=true."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # Only specify amount, let delete_when_empty use default
        payload = {"amount": 1.0}
        response = client.post(f"/prepared-foods/{item_id}/consume", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True  # Should be deleted by default

    def test_consume_nonexistent_item(self, client, auth_headers):
        """Should return 404 for nonexistent item."""
        fake_id = uuid4()
        payload = {"amount": 1.0}
        response = client.post(f"/prepared-foods/{fake_id}/consume", json=payload, headers=auth_headers)
        assert response.status_code == 404

    def test_consume_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"amount": 1.0}
        response = client.post(f"/prepared-foods/{item.id}/consume", json=payload)
        assert response.status_code == 401

    def test_consume_floating_point_edge_cases(self, client, auth_headers, test_user, db_session):
        """Should handle floating-point precision edge cases correctly."""
        # Test case 1: Consuming amount that would leave tiny remainder due to float precision
        # e.g., 3.3 - 3.3 might not equal exactly 0.0
        item1 = PreparedFood(
            id=uuid4(),
            name="Float test 1",
            type="complete_meal",
            servings_remaining=3.3,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item1)
        db_session.commit()
        item1_id = item1.id

        # Consume exact amount (should delete due to tolerance handling)
        payload = {"amount": 3.3, "delete_when_empty": True}
        response = client.post(f"/prepared-foods/{item1_id}/consume", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        deleted_item = db_session.query(PreparedFood).filter_by(id=item1_id).first()
        assert deleted_item is None

        # Test case 2: Amount within tolerance of remaining servings should succeed
        item2 = PreparedFood(
            id=uuid4(),
            name="Float test 2",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item2)
        db_session.commit()
        item2_id = item2.id

        # Try to consume slightly more than available (within tolerance)
        # 2.0 + 1e-10 should be within tolerance (1e-9)
        payload = {"amount": 2.0 + 1e-10, "delete_when_empty": False}
        response = client.post(f"/prepared-foods/{item2_id}/consume", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Result should be effectively zero (within tolerance)
        assert data["deleted"] is False
        assert data["item"]["servings_remaining"] <= 1e-9

        # Test case 3: Amount beyond tolerance should fail
        item3 = PreparedFood(
            id=uuid4(),
            name="Float test 3",
            type="complete_meal",
            servings_remaining=1.5,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item3)
        db_session.commit()

        # Try to consume amount exceeding available by more than tolerance
        # 1.5 + 1e-8 is greater than tolerance (1e-9)
        payload = {"amount": 1.5 + 1e-8, "delete_when_empty": False}
        response = client.post(f"/prepared-foods/{item3.id}/consume", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "Cannot consume" in response.json()["detail"]

        # Test case 4: Result near zero with delete_when_empty=False should keep item
        item4 = PreparedFood(
            id=uuid4(),
            name="Float test 4",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item4)
        db_session.commit()
        item4_id = item4.id

        # Consume amount leaving near-zero remainder
        payload = {"amount": 1.0 - 1e-10, "delete_when_empty": False}
        response = client.post(f"/prepared-foods/{item4_id}/consume", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        # Verify item exists with tiny positive remainder
        existing_item = db_session.query(PreparedFood).filter_by(id=item4_id).first()
        assert existing_item is not None
        assert existing_item.servings_remaining >= 0

        # Test case 5: Multiple decimal places consumption
        item5 = PreparedFood(
            id=uuid4(),
            name="Float test 5",
            type="complete_meal",
            servings_remaining=0.1 + 0.2,  # Classic float precision issue: may not equal exactly 0.3
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item5)
        db_session.commit()
        item5_id = item5.id

        # Consume 0.3 which should match within tolerance
        payload = {"amount": 0.3, "delete_when_empty": True}
        response = client.post(f"/prepared-foods/{item5_id}/consume", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Should successfully consume and delete due to tolerance handling
        assert data["deleted"] is True or (data["item"] is not None and abs(data["item"]["servings_remaining"]) < 1e-9)


class TestTransferPreparedFood:
    """Tests for POST /prepared-foods/{id}/transfer (transfer to different storage location)."""

    def test_transfer_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to transfer item to different location."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["servings_remaining"] == 3.0  # Unchanged

    def test_transfer_shared_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should allow transfer of shared item by non-owner (shareability-aware)."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"

    def test_transfer_personal_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject transfer of personal item by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 personal item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers2)
        assert response.status_code == 404

    def test_transfer_reserved_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject transfer of reserved item by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 reserved item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers2)
        assert response.status_code == 404

    def test_transfer_personal_item_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to transfer their own personal item."""
        item = PreparedFood(
            id=uuid4(),
            name="Personal item",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["shareability"] == "personal"

    def test_transfer_reserved_item_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to transfer their own reserved item."""
        item = PreparedFood(
            id=uuid4(),
            name="Reserved item",
            type="complete_meal",
            servings_remaining=4.0,
            storage_location="fridge",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["shareability"] == "reserved"

    def test_transfer_to_same_location(self, client, auth_headers, test_user, db_session):
        """Should be idempotent - transferring to same location succeeds."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "fridge"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["servings_remaining"] == 3.0  # Unchanged

    def test_transfer_invalid_location(self, client, auth_headers, test_user, db_session):
        """Should reject invalid storage_location."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "garage"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_transfer_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        payload = {"storage_location": "freezer"}
        response = client.post(f"/prepared-foods/{item.id}/transfer", json=payload)
        assert response.status_code == 401


class TestFreezePreparedFood:
    """Tests for POST /prepared-foods/{id}/freeze (quick freeze action)."""

    def test_freeze_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to freeze item."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"

    def test_freeze_personal_item_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to freeze their own personal item."""
        item = PreparedFood(
            id=uuid4(),
            name="Personal item",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["shareability"] == "personal"

    def test_freeze_reserved_item_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to freeze their own reserved item."""
        item = PreparedFood(
            id=uuid4(),
            name="Reserved item",
            type="complete_meal",
            servings_remaining=4.0,
            storage_location="fridge",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["shareability"] == "reserved"

    def test_freeze_already_frozen(self, client, auth_headers, test_user, db_session):
        """Should be idempotent - freezing already-frozen item succeeds."""
        item = PreparedFood(
            id=uuid4(),
            name="Already frozen",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="freezer",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"

    def test_freeze_shared_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should allow freeze of shared item by non-owner (shareability-aware)."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"

    def test_freeze_personal_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject freeze of personal item by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 personal item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers2)
        assert response.status_code == 404

    def test_freeze_reserved_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject freeze of reserved item by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 reserved item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze", headers=auth_headers2)
        assert response.status_code == 404

    def test_freeze_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/freeze")
        assert response.status_code == 401


class TestThawPreparedFood:
    """Tests for POST /prepared-foods/{id}/thaw (quick thaw action)."""

    def test_thaw_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to thaw item."""
        item = PreparedFood(
            id=uuid4(),
            name="Frozen item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="freezer",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"

    def test_thaw_personal_item_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to thaw their own personal item."""
        item = PreparedFood(
            id=uuid4(),
            name="Personal frozen item",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="freezer",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["shareability"] == "personal"

    def test_thaw_reserved_item_by_owner(self, client, auth_headers, test_user, db_session):
        """Should allow owner to thaw their own reserved item."""
        item = PreparedFood(
            id=uuid4(),
            name="Reserved frozen item",
            type="complete_meal",
            servings_remaining=4.0,
            storage_location="freezer",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["shareability"] == "reserved"

    def test_thaw_already_thawed(self, client, auth_headers, test_user, db_session):
        """Should be idempotent - thawing already-thawed item succeeds."""
        item = PreparedFood(
            id=uuid4(),
            name="Already thawed",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"

    def test_thaw_shared_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should allow thaw of shared item by non-owner (shareability-aware)."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="freezer",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"

    def test_thaw_personal_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject thaw of personal item by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 personal item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="freezer",
            shareability="personal",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers2)
        assert response.status_code == 404

    def test_thaw_reserved_item_by_non_owner(self, client, auth_headers2, test_user, db_session):
        """Should reject thaw of reserved item by non-owner with 404."""
        item = PreparedFood(
            id=uuid4(),
            name="User1 reserved item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="freezer",
            shareability="reserved",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw", headers=auth_headers2)
        assert response.status_code == 404

    def test_thaw_requires_auth(self, client, test_user, db_session):
        """Should reject request without authentication."""
        item = PreparedFood(
            id=uuid4(),
            name="Test item",
            type="complete_meal",
            servings_remaining=3.0,
            storage_location="freezer",
            shareability="shared",
            prepared_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.post(f"/prepared-foods/{item.id}/thaw")
        assert response.status_code == 401


class TestPreparedFoodExpiringAndSearchFilters:
    """Tests for expiring_soon, expiring_within_days, and search filters on prepared foods list endpoint."""

    def test_filter_by_expiring_soon(self, client, auth_headers, test_user, db_session):
        """Should filter items expiring within 7 days."""
        # Create items with different expiration dates
        expiring_soon_item = PreparedFood(
            name="Leftover Curry Expiring Soon",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=3),
            prepared_by=test_user.id,
        )
        expiring_later_item = PreparedFood(
            name="Frozen Soup Expiring Later",
            type="batch_portion",
            servings_remaining=4.0,
            storage_location="freezer",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=14),
            prepared_by=test_user.id,
        )
        no_expiration_item = PreparedFood(
            name="Dried Herbs No Expiration",
            type="component_ingredient",
            servings_remaining=10.0,
            storage_location="pantry",
            estimated_expiration=None,
            prepared_by=test_user.id,
        )
        db_session.add_all([expiring_soon_item, expiring_later_item, no_expiration_item])
        db_session.commit()

        # Filter by expiring_soon=true
        response = client.get("/prepared-foods?expiring_soon=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Leftover Curry Expiring Soon"

        # Filter by expiring_soon=false (should return all items, including those not expiring soon)
        response = client.get("/prepared-foods?expiring_soon=false", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # When expiring_soon=false, no expiration filter is applied, so all items are returned
        assert len(data) == 3

    def test_filter_by_expiring_within_days(self, client, auth_headers, test_user, db_session):
        """Should filter items expiring within N days."""
        # Create items with different expiration dates
        expiring_in_2_days = PreparedFood(
            name="Pasta 2 Days",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=2),
            prepared_by=test_user.id,
        )
        expiring_in_5_days = PreparedFood(
            name="Rice 5 Days",
            type="batch_portion",
            servings_remaining=3.0,
            storage_location="fridge",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=5),
            prepared_by=test_user.id,
        )
        expiring_in_10_days = PreparedFood(
            name="Stew 10 Days",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="freezer",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=10),
            prepared_by=test_user.id,
        )
        db_session.add_all([expiring_in_2_days, expiring_in_5_days, expiring_in_10_days])
        db_session.commit()

        # Filter by expiring_within_days=3
        response = client.get("/prepared-foods?expiring_within_days=3", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Pasta 2 Days"

        # Filter by expiring_within_days=6
        response = client.get("/prepared-foods?expiring_within_days=6", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        item_names = {item["name"] for item in data}
        assert item_names == {"Pasta 2 Days", "Rice 5 Days"}

        # Filter by expiring_within_days=15
        response = client.get("/prepared-foods?expiring_within_days=15", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_filter_expiring_within_days_overrides_expiring_soon(self, client, auth_headers, test_user, db_session):
        """Should use expiring_within_days when both expiring_soon and expiring_within_days are provided."""
        # Create items
        expiring_in_2_days = PreparedFood(
            name="Soup 2 Days",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=2),
            prepared_by=test_user.id,
        )
        expiring_in_5_days = PreparedFood(
            name="Curry 5 Days",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=5),
            prepared_by=test_user.id,
        )
        db_session.add_all([expiring_in_2_days, expiring_in_5_days])
        db_session.commit()

        # When both are provided, expiring_within_days should take precedence
        response = client.get(
            "/prepared-foods?expiring_soon=true&expiring_within_days=3",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Soup 2 Days"

    def test_expiring_filters_exclude_null_expiration(self, client, auth_headers, test_user, db_session):
        """Should exclude items with null estimated_expiration from expiring filters."""
        # Create items with and without expiration dates
        has_expiration = PreparedFood(
            name="Leftovers With Expiration",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=3),
            prepared_by=test_user.id,
        )
        no_expiration = PreparedFood(
            name="Dried Ingredients No Expiration",
            type="component_ingredient",
            servings_remaining=5.0,
            storage_location="pantry",
            estimated_expiration=None,
            prepared_by=test_user.id,
        )
        db_session.add_all([has_expiration, no_expiration])
        db_session.commit()

        # Filter by expiring_soon=true
        response = client.get("/prepared-foods?expiring_soon=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Leftovers With Expiration"

        # Filter by expiring_within_days=7
        response = client.get("/prepared-foods?expiring_within_days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Leftovers With Expiration"

    def test_filter_by_search(self, client, auth_headers, test_user, db_session):
        """Should search items by name (case-insensitive partial match)."""
        # Create items with different names
        item1 = PreparedFood(
            name="Leftover Curry",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            prepared_by=test_user.id,
        )
        item2 = PreparedFood(
            name="Chicken Curry Batch",
            type="batch_portion",
            servings_remaining=5.0,
            storage_location="freezer",
            prepared_by=test_user.id,
        )
        item3 = PreparedFood(
            name="Tomato Sauce",
            type="component_ingredient",
            servings_remaining=3.0,
            storage_location="fridge",
            prepared_by=test_user.id,
        )
        db_session.add_all([item1, item2, item3])
        db_session.commit()

        # Search for "curry" (case-insensitive)
        response = client.get("/prepared-foods?search=curry", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        item_names = {item["name"] for item in data}
        assert item_names == {"Leftover Curry", "Chicken Curry Batch"}

        # Search for "CURRY" (case-insensitive)
        response = client.get("/prepared-foods?search=CURRY", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Search for "tomato"
        response = client.get("/prepared-foods?search=tomato", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Tomato Sauce"

        # Search for partial match "chi"
        response = client.get("/prepared-foods?search=chi", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Chicken Curry Batch"

    def test_search_with_wildcard_characters(self, client, auth_headers, test_user, db_session):
        """Should escape SQL wildcards in search input to prevent DoS."""
        # Create items with special characters
        item1 = PreparedFood(
            name="Test_Item_With_Underscores",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            prepared_by=test_user.id,
        )
        item2 = PreparedFood(
            name="Test%Item%With%Percent",
            type="batch_portion",
            servings_remaining=2.0,
            storage_location="fridge",
            prepared_by=test_user.id,
        )
        item3 = PreparedFood(
            name="Regular Item",
            type="component_ingredient",
            servings_remaining=3.0,
            storage_location="pantry",
            prepared_by=test_user.id,
        )
        db_session.add_all([item1, item2, item3])
        db_session.commit()

        # Search with underscore wildcard (should be escaped and match literally)
        response = client.get("/prepared-foods?search=Test_Item", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test_Item_With_Underscores"

        # Search with percent wildcard (should be escaped and match literally)
        response = client.get("/prepared-foods?search=Test%Item", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test%Item%With%Percent"

    def test_search_min_length_validation(self, client, auth_headers):
        """Should return 422 when search term is less than 2 characters."""
        # Single character search should fail
        response = client.get("/prepared-foods?search=a", headers=auth_headers)
        assert response.status_code == 422

        # Two character search should succeed
        response = client.get("/prepared-foods?search=ab", headers=auth_headers)
        assert response.status_code == 200

    def test_combined_filters_with_expiring_and_search(self, client, auth_headers, test_user, db_session):
        """Should combine expiring and search filters with existing filters using AND logic."""
        # Create diverse items
        target_item = PreparedFood(
            name="Leftover Curry",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="shared",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=3),
            prepared_by=test_user.id,
        )
        wrong_expiration = PreparedFood(
            name="Leftover Curry Old",
            type="complete_meal",
            servings_remaining=1.0,
            storage_location="fridge",
            shareability="shared",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=14),
            prepared_by=test_user.id,
        )
        wrong_name = PreparedFood(
            name="Tomato Soup",
            type="complete_meal",
            servings_remaining=2.0,
            storage_location="fridge",
            shareability="shared",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=3),
            prepared_by=test_user.id,
        )
        wrong_type = PreparedFood(
            name="Leftover Curry Frozen",
            type="batch_portion",
            servings_remaining=3.0,
            storage_location="fridge",
            shareability="shared",
            estimated_expiration=datetime.now(timezone.utc) + timedelta(days=3),
            prepared_by=test_user.id,
        )
        db_session.add_all([target_item, wrong_expiration, wrong_name, wrong_type])
        db_session.commit()

        # Combine type, expiring_within_days, and search filters
        response = client.get(
            "/prepared-foods?type=complete_meal&expiring_within_days=5&search=curry",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Leftover Curry"
