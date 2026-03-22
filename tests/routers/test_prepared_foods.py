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
from uuid import uuid4

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
        from uuid import UUID
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
        assert data["total"] == 2
        assert len(data["items"]) == 2
        names = {item["name"] for item in data["items"]}
        assert "User1 shared curry" in names
        assert "User2 shared chili" in names

        # User2 should also see both shared items
        response = client.get("/prepared-foods", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

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
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "User1 personal meal"

        # User2 should only see their own reserved item
        response = client.get("/prepared-foods", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "User2 reserved batch"

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
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["type"] == "complete_meal"

        # Filter by storage_location
        response = client.get("/prepared-foods?storage_location=freezer", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["storage_location"] == "freezer"

        # Filter by shareability
        response = client.get("/prepared-foods?shareability=personal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["shareability"] == "personal"

    def test_list_pagination(self, client, auth_headers, test_user, db_session):
        """Should support limit and offset pagination with total count."""
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
        assert data["total"] == 10  # Total count should reflect all items
        assert len(data["items"]) == 5  # But only 5 items returned

        # Get second page
        response = client.get("/prepared-foods?limit=5&offset=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10  # Total count remains the same
        assert len(data["items"]) == 5  # Second page has 5 items

    def test_list_total_count_accuracy(self, client, auth_headers, test_user, db_session):
        """Should return accurate total count with different filters."""
        # Create diverse items
        items = [
            PreparedFood(id=uuid4(), name="Meal1", type="complete_meal", servings_remaining=1.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Meal2", type="complete_meal", servings_remaining=2.0, storage_location="fridge", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Meal3", type="complete_meal", servings_remaining=3.0, storage_location="freezer", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Batch1", type="batch_portion", servings_remaining=5.0, storage_location="freezer", shareability="shared", prepared_by=test_user.id),
            PreparedFood(id=uuid4(), name="Component1", type="component_ingredient", servings_remaining=10.0, storage_location="fridge", shareability="personal", prepared_by=test_user.id),
        ]
        db_session.add_all(items)
        db_session.commit()

        # Test total without filters
        response = client.get("/prepared-foods", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

        # Test total with type filter
        response = client.get("/prepared-foods?type=complete_meal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        # Test total with pagination (should show full total, not paginated count)
        response = client.get("/prepared-foods?limit=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5  # Total is 5, even though only 2 returned
        assert len(data["items"]) == 2

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
        assert data["total"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["type"] == "complete_meal"
            assert item["storage_location"] == "fridge"

        # Combine all three filters
        response = client.get("/prepared-foods?type=complete_meal&storage_location=fridge&shareability=personal", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Meal2"
        assert data["items"][0]["type"] == "complete_meal"
        assert data["items"][0]["storage_location"] == "fridge"
        assert data["items"][0]["shareability"] == "personal"

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
        assert data["total"] == 0
        assert len(data["items"]) == 0

        # Another non-matching combination
        response = client.get("/prepared-foods?type=component_ingredient&shareability=shared", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_invalid_type_filter(self, client, auth_headers):
        """Should reject invalid type enum value with 422."""
        response = client.get("/prepared-foods?type=invalid_type", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        assert "type" in data["detail"].lower()

    def test_invalid_storage_location_filter(self, client, auth_headers):
        """Should reject invalid storage_location enum value with 422."""
        response = client.get("/prepared-foods?storage_location=garage", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        assert "storage_location" in data["detail"].lower()

    def test_invalid_shareability_filter(self, client, auth_headers):
        """Should reject invalid shareability enum value with 422."""
        response = client.get("/prepared-foods?shareability=public", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        assert "shareability" in data["detail"].lower()

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
        assert data["total"] == 10  # Total count with filter applied
        assert len(data["items"]) == 5  # But only 5 items in first page
        for item in data["items"]:
            assert item["type"] == "complete_meal"

        # Get second page with filter
        response = client.get("/prepared-foods?type=complete_meal&limit=5&offset=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10  # Total remains the same
        assert len(data["items"]) == 5
        for item in data["items"]:
            assert item["type"] == "complete_meal"

        # Get beyond available items
        response = client.get("/prepared-foods?type=complete_meal&limit=5&offset=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10  # Total still shows all items
        assert len(data["items"]) == 0  # But no items on this page

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
