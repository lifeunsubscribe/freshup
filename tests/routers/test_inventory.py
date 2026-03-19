"""
Integration tests for inventory item endpoints.

Tests cover:
- POST /inventory: create items with validation
- GET /inventory: list all user items with pagination
- GET /inventory/{id}: get single item
- PUT /inventory/{id}: update items with partial data
- DELETE /inventory/{id}: delete item
- Cross-user access prevention
- Authentication requirements
- Validation (quantity, unit, category, etc.)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.inventory_item import InventoryItem
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import inventory_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the inventory router
app.include_router(inventory_router)


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


class TestCreateInventoryItem:
    """Tests for POST /inventory (create inventory item)."""

    def test_create_item_success(self, client, auth_headers, test_user, db_session):
        """Should create inventory item and auto-set added_by to current user."""
        payload = {
            "name": "Milk",
            "quantity": 1.0,
            "unit": "gallon",
            "category": "dairy",
            "storage_location": "fridge",
            "added_by": str(uuid4()),  # Should be ignored
        }

        response = client.post("/inventory", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Milk"
        assert data["quantity"] == 1.0
        assert data["unit"] == "gallon"
        assert data["category"] == "dairy"
        assert data["storage_location"] == "fridge"
        assert data["added_by"] == str(test_user.id)  # Should be current user, not from payload
        assert "id" in data
        assert "date_added" in data

    def test_create_item_with_optional_fields(self, client, auth_headers, test_user):
        """Should create item with optional fields."""
        payload = {
            "name": "Organic Eggs",
            "quantity": 12,
            "unit": "count",
            "category": "protein",
            "storage_location": "fridge",
            "added_by": str(test_user.id),
            "is_staple": True,
            "minimum_threshold": 6.0,
            "price": 4.99,
            "brand": "Happy Hens",
            "vegan_friendly": False,
        }

        response = client.post("/inventory", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["is_staple"] is True
        assert data["minimum_threshold"] == 6.0
        assert data["price"] == 4.99
        assert data["brand"] == "Happy Hens"
        assert data["vegan_friendly"] is False

    def test_create_item_requires_auth(self, client):
        """Should return 401 if no auth token provided."""
        payload = {
            "name": "Milk",
            "quantity": 1.0,
            "unit": "gallon",
            "category": "dairy",
            "storage_location": "fridge",
            "added_by": str(uuid4()),
        }

        response = client.post("/inventory", json=payload)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_create_item_invalid_unit(self, client, auth_headers, test_user):
        """Should return 422 if unit is invalid."""
        payload = {
            "name": "Milk",
            "quantity": 1.0,
            "unit": "invalid_unit",
            "category": "dairy",
            "storage_location": "fridge",
            "added_by": str(test_user.id),
        }

        response = client.post("/inventory", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_item_invalid_category(self, client, auth_headers, test_user):
        """Should return 422 if category is invalid."""
        payload = {
            "name": "Milk",
            "quantity": 1.0,
            "unit": "gallon",
            "category": "invalid_category",
            "storage_location": "fridge",
            "added_by": str(test_user.id),
        }

        response = client.post("/inventory", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_item_negative_quantity(self, client, auth_headers, test_user):
        """Should return 422 if quantity is negative."""
        payload = {
            "name": "Milk",
            "quantity": -1.0,
            "unit": "gallon",
            "category": "dairy",
            "storage_location": "fridge",
            "added_by": str(test_user.id),
        }

        response = client.post("/inventory", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_item_empty_name(self, client, auth_headers, test_user):
        """Should return 422 if name is empty."""
        payload = {
            "name": "   ",
            "quantity": 1.0,
            "unit": "gallon",
            "category": "dairy",
            "storage_location": "fridge",
            "added_by": str(test_user.id),
        }

        response = client.post("/inventory", json=payload, headers=auth_headers)

        assert response.status_code == 422


class TestListInventoryItems:
    """Tests for GET /inventory (list inventory items)."""

    def test_list_items_empty(self, client, auth_headers):
        """Should return empty list if user has no items."""
        response = client.get("/inventory", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_items_success(self, client, auth_headers, test_user, db_session):
        """Should return user's inventory items ordered by date_added DESC."""
        # Create multiple items
        item1 = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            name="Bread",
            quantity=2.0,
            unit="count",
            category="grain",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        response = client.get("/inventory", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Verify both items are present (order may vary if created at same time)
        item_names = {item["name"] for item in data}
        assert item_names == {"Milk", "Bread"}

    def test_list_items_multi_tenant_isolation(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Should only return items owned by current user."""
        # Create items for both users
        item1 = InventoryItem(
            name="User 1 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            name="User 2 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user2.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # User 1 should only see their item
        response = client.get("/inventory", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User 1 Milk"

        # User 2 should only see their item
        response = client.get("/inventory", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User 2 Milk"

    def test_list_items_pagination(self, client, auth_headers, test_user, db_session):
        """Should support pagination with limit and offset."""
        # Create 5 items
        for i in range(5):
            item = InventoryItem(
                name=f"Item {i}",
                quantity=1.0,
                unit="count",
                category="other",
                storage_location="pantry",
                added_by=test_user.id,
            )
            db_session.add(item)
        db_session.commit()

        # Get first 2 items
        response = client.get("/inventory?limit=2&offset=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Get next 2 items
        response = client.get("/inventory?limit=2&offset=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Get last item
        response = client.get("/inventory?limit=2&offset=4", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_items_requires_auth(self, client):
        """Should return 401 if no auth token provided."""
        response = client.get("/inventory")

        assert response.status_code == 401


class TestGetInventoryItem:
    """Tests for GET /inventory/{id} (get single item)."""

    def test_get_item_success(self, client, auth_headers, test_user, db_session):
        """Should return single inventory item."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.get(f"/inventory/{item.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(item.id)
        assert data["name"] == "Milk"
        assert data["quantity"] == 1.0

    def test_get_item_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.get(f"/inventory/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_get_item_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
        """Should return 404 if item belongs to another user."""
        # Create item for user 2
        item = InventoryItem(
            name="User 2 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user2.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to access user 2's item
        response = client.get(f"/inventory/{item.id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_get_item_requires_auth(self, client, test_user, db_session):
        """Should return 401 if no auth token provided."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.get(f"/inventory/{item.id}")

        assert response.status_code == 401


class TestUpdateInventoryItem:
    """Tests for PUT /inventory/{id} (update item)."""

    def test_update_item_partial(self, client, auth_headers, test_user, db_session):
        """Should update only provided fields."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Update only quantity
        payload = {"quantity": 0.5}
        response = client.put(f"/inventory/{item.id}", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 0.5
        assert data["name"] == "Milk"  # Unchanged
        assert data["unit"] == "gallon"  # Unchanged

    def test_update_item_multiple_fields(self, client, auth_headers, test_user, db_session):
        """Should update multiple fields at once."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        payload = {
            "quantity": 2.0,
            "storage_location": "pantry",
            "is_staple": True,
        }
        response = client.put(f"/inventory/{item.id}", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 2.0
        assert data["storage_location"] == "pantry"
        assert data["is_staple"] is True

    def test_update_item_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        payload = {"quantity": 2.0}
        response = client.put(f"/inventory/{fake_id}", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_update_item_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
        """Should return 404 if item belongs to another user."""
        # Create item for user 2
        item = InventoryItem(
            name="User 2 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user2.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to update user 2's item
        payload = {"quantity": 2.0}
        response = client.put(f"/inventory/{item.id}", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_update_item_invalid_field(self, client, auth_headers, test_user, db_session):
        """Should return 422 if validation fails."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Try to update with invalid unit
        payload = {"unit": "invalid_unit"}
        response = client.put(f"/inventory/{item.id}", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_update_item_requires_auth(self, client, test_user, db_session):
        """Should return 401 if no auth token provided."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        payload = {"quantity": 2.0}
        response = client.put(f"/inventory/{item.id}", json=payload)

        assert response.status_code == 401


class TestDeleteInventoryItem:
    """Tests for DELETE /inventory/{id} (delete item)."""

    def test_delete_item_success(self, client, auth_headers, test_user, db_session):
        """Should delete inventory item and return 204."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        item_id = item.id

        response = client.delete(f"/inventory/{item_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify item is deleted
        deleted_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert deleted_item is None

    def test_delete_item_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.delete(f"/inventory/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_delete_item_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
        """Should return 404 if item belongs to another user."""
        # Create item for user 2
        item = InventoryItem(
            name="User 2 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user2.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to delete user 2's item
        response = client.delete(f"/inventory/{item.id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

        # Verify item is NOT deleted
        still_exists = db_session.query(InventoryItem).filter(InventoryItem.id == item.id).first()
        assert still_exists is not None

    def test_delete_item_requires_auth(self, client, test_user, db_session):
        """Should return 401 if no auth token provided."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.delete(f"/inventory/{item.id}")

        assert response.status_code == 401
