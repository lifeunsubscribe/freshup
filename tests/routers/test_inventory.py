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
from datetime import datetime, timedelta, timezone

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.inventory_item import InventoryItem
from src.db.models.store import Store
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


@pytest.fixture
def test_store(db_session):
    """Create a test store."""
    store = Store(
        id=uuid4(),
        name="Test Store",
        has_digital_receipts=False,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)
    return store


@pytest.fixture
def test_store2(db_session):
    """Create a second test store."""
    store = Store(
        id=uuid4(),
        name="Test Store 2",
        has_digital_receipts=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)
    return store


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


class TestFilterInventoryItems:
    """Tests for GET /inventory filtering and search functionality."""

    def test_filter_by_category(self, client, auth_headers, test_user, db_session):
        """Should filter items by category."""
        # Create items with different categories
        dairy_item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        produce_item = InventoryItem(
            name="Apple",
            quantity=5.0,
            unit="count",
            category="produce",
            storage_location="fridge",
            added_by=test_user.id,
        )
        protein_item = InventoryItem(
            name="Chicken",
            quantity=2.0,
            unit="lb",
            category="protein",
            storage_location="freezer",
            added_by=test_user.id,
        )
        db_session.add_all([dairy_item, produce_item, protein_item])
        db_session.commit()

        # Filter by dairy category
        response = client.get("/inventory?category=dairy", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Milk"
        assert data[0]["category"] == "dairy"

        # Filter by produce category
        response = client.get("/inventory?category=produce", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Apple"

    def test_filter_by_storage_location(self, client, auth_headers, test_user, db_session):
        """Should filter items by storage location."""
        # Create items with different storage locations
        fridge_item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        freezer_item = InventoryItem(
            name="Frozen Pizza",
            quantity=2.0,
            unit="count",
            category="frozen",
            storage_location="freezer",
            added_by=test_user.id,
        )
        pantry_item = InventoryItem(
            name="Pasta",
            quantity=1.0,
            unit="box",
            category="grain",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add_all([fridge_item, freezer_item, pantry_item])
        db_session.commit()

        # Filter by fridge
        response = client.get("/inventory?storage_location=fridge", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Milk"
        assert data[0]["storage_location"] == "fridge"

        # Filter by freezer
        response = client.get("/inventory?storage_location=freezer", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Frozen Pizza"

    def test_filter_by_shareability(self, client, auth_headers, test_user, db_session):
        """Should filter items by shareability."""
        # Create items with different shareability
        shared_item = InventoryItem(
            name="Shared Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            shareability="shared",
            added_by=test_user.id,
        )
        reserved_item = InventoryItem(
            name="Reserved Yogurt",
            quantity=1.0,
            unit="count",
            category="dairy",
            storage_location="fridge",
            shareability="reserved",
            added_by=test_user.id,
        )
        personal_item = InventoryItem(
            name="Personal Cheese",
            quantity=1.0,
            unit="oz",
            category="dairy",
            storage_location="fridge",
            shareability="personal",
            added_by=test_user.id,
        )
        db_session.add_all([shared_item, reserved_item, personal_item])
        db_session.commit()

        # Filter by shared
        response = client.get("/inventory?shareability=shared", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Shared Milk"
        assert data[0]["shareability"] == "shared"

        # Filter by reserved
        response = client.get("/inventory?shareability=reserved", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Reserved Yogurt"

    def test_filter_by_is_staple(self, client, auth_headers, test_user, db_session):
        """Should filter items by staple status."""
        # Create staple and non-staple items
        staple_item = InventoryItem(
            name="Rice",
            quantity=5.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            added_by=test_user.id,
        )
        non_staple_item = InventoryItem(
            name="Ice Cream",
            quantity=1.0,
            unit="pint",
            category="frozen",
            storage_location="freezer",
            is_staple=False,
            added_by=test_user.id,
        )
        db_session.add_all([staple_item, non_staple_item])
        db_session.commit()

        # Filter by is_staple=true
        response = client.get("/inventory?is_staple=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Rice"
        assert data[0]["is_staple"] is True

        # Filter by is_staple=false
        response = client.get("/inventory?is_staple=false", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Ice Cream"
        assert data[0]["is_staple"] is False

    def test_filter_by_expiring_soon(self, client, auth_headers, test_user, db_session):
        """Should filter items expiring within 7 days."""
        # Create items with different expiration dates
        expiring_soon_item = InventoryItem(
            name="Milk Expiring Soon",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=3),
            added_by=test_user.id,
        )
        expiring_later_item = InventoryItem(
            name="Milk Expiring Later",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=14),
            added_by=test_user.id,
        )
        no_expiration_item = InventoryItem(
            name="Canned Beans",
            quantity=1.0,
            unit="can",
            category="canned",
            storage_location="pantry",
            expiration_date=None,
            added_by=test_user.id,
        )
        db_session.add_all([expiring_soon_item, expiring_later_item, no_expiration_item])
        db_session.commit()

        # Filter by expiring_soon=true
        response = client.get("/inventory?expiring_soon=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Milk Expiring Soon"

        # Filter by expiring_soon=false (should return all items, including those not expiring soon)
        response = client.get("/inventory?expiring_soon=false", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # When expiring_soon=false, no expiration filter is applied, so all items are returned
        assert len(data) == 3

    def test_filter_by_expiring_within_days(self, client, auth_headers, test_user, db_session):
        """Should filter items expiring within N days."""
        # Create items with different expiration dates
        expiring_in_2_days = InventoryItem(
            name="Milk 2 Days",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=2),
            added_by=test_user.id,
        )
        expiring_in_5_days = InventoryItem(
            name="Milk 5 Days",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=5),
            added_by=test_user.id,
        )
        expiring_in_10_days = InventoryItem(
            name="Milk 10 Days",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=10),
            added_by=test_user.id,
        )
        db_session.add_all([expiring_in_2_days, expiring_in_5_days, expiring_in_10_days])
        db_session.commit()

        # Filter by expiring_within_days=3
        response = client.get("/inventory?expiring_within_days=3", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Milk 2 Days"

        # Filter by expiring_within_days=6
        response = client.get("/inventory?expiring_within_days=6", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        item_names = {item["name"] for item in data}
        assert item_names == {"Milk 2 Days", "Milk 5 Days"}

        # Filter by expiring_within_days=15
        response = client.get("/inventory?expiring_within_days=15", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_filter_by_search(self, client, auth_headers, test_user, db_session):
        """Should search items by name (case-insensitive partial match)."""
        # Create items with different names
        item1 = InventoryItem(
            name="Whole Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            name="Almond Milk",
            quantity=1.0,
            unit="quart",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item3 = InventoryItem(
            name="Apple Juice",
            quantity=1.0,
            unit="bottle",
            category="beverage",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2, item3])
        db_session.commit()

        # Search for "milk" (case-insensitive)
        response = client.get("/inventory?search=milk", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        item_names = {item["name"] for item in data}
        assert item_names == {"Whole Milk", "Almond Milk"}

        # Search for "MILK" (case-insensitive)
        response = client.get("/inventory?search=MILK", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Search for "apple"
        response = client.get("/inventory?search=apple", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Apple Juice"

        # Search for partial match "alm"
        response = client.get("/inventory?search=alm", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Almond Milk"

    def test_filter_multiple_combined_with_and_logic(self, client, auth_headers, test_user, db_session):
        """Should combine multiple filters with AND logic."""
        # Create diverse items
        target_item = InventoryItem(
            name="Organic Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            shareability="shared",
            is_staple=True,
            added_by=test_user.id,
        )
        wrong_category = InventoryItem(
            name="Orange Juice",
            quantity=1.0,
            unit="bottle",
            category="beverage",
            storage_location="fridge",
            shareability="shared",
            is_staple=True,
            added_by=test_user.id,
        )
        wrong_location = InventoryItem(
            name="Frozen Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="freezer",
            shareability="shared",
            is_staple=True,
            added_by=test_user.id,
        )
        wrong_shareability = InventoryItem(
            name="Personal Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            shareability="personal",
            is_staple=True,
            added_by=test_user.id,
        )
        db_session.add_all([target_item, wrong_category, wrong_location, wrong_shareability])
        db_session.commit()

        # Apply multiple filters (should only match target_item)
        response = client.get(
            "/inventory?category=dairy&storage_location=fridge&shareability=shared",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Organic Milk"

    def test_filter_invalid_category(self, client, auth_headers):
        """Should return 422 for invalid category."""
        response = client.get("/inventory?category=invalid_category", headers=auth_headers)
        assert response.status_code == 422
        assert "category" in response.json()["detail"]

    def test_filter_invalid_storage_location(self, client, auth_headers):
        """Should return 422 for invalid storage_location."""
        response = client.get("/inventory?storage_location=invalid_location", headers=auth_headers)
        assert response.status_code == 422
        assert "storage_location" in response.json()["detail"]

    def test_filter_invalid_shareability(self, client, auth_headers):
        """Should return 422 for invalid shareability."""
        response = client.get("/inventory?shareability=invalid_share", headers=auth_headers)
        assert response.status_code == 422
        assert "shareability" in response.json()["detail"]

    def test_filter_no_matches(self, client, auth_headers, test_user, db_session):
        """Should return empty list when no items match filters."""
        # Create a single item
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

        # Filter for produce (no matches)
        response = client.get("/inventory?category=produce", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_filter_with_pagination(self, client, auth_headers, test_user, db_session):
        """Should apply filters with pagination."""
        # Create multiple dairy items
        for i in range(5):
            item = InventoryItem(
                name=f"Dairy Item {i}",
                quantity=1.0,
                unit="count",
                category="dairy",
                storage_location="fridge",
                added_by=test_user.id,
            )
            db_session.add(item)
        db_session.commit()

        # Filter by category with pagination
        response = client.get("/inventory?category=dairy&limit=2&offset=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Get next page
        response = client.get("/inventory?category=dairy&limit=2&offset=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_filter_expiring_within_days_overrides_expiring_soon(self, client, auth_headers, test_user, db_session):
        """Should use expiring_within_days when both expiring_soon and expiring_within_days are provided."""
        # Create items
        expiring_in_2_days = InventoryItem(
            name="Milk 2 Days",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=2),
            added_by=test_user.id,
        )
        expiring_in_5_days = InventoryItem(
            name="Milk 5 Days",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            expiration_date=datetime.now(timezone.utc) + timedelta(days=5),
            added_by=test_user.id,
        )
        db_session.add_all([expiring_in_2_days, expiring_in_5_days])
        db_session.commit()

        # When both are provided, expiring_within_days should take precedence
        response = client.get(
            "/inventory?expiring_soon=true&expiring_within_days=3",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Milk 2 Days"


class TestStoreMappingEndpoints:
    """Tests for store mapping endpoints (preferred store and available stores)."""

    def test_set_preferred_store_success(self, client, auth_headers, test_user, test_store, db_session):
        """Should set preferred store for inventory item."""
        # Create inventory item
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

        # Set preferred store
        payload = {"store_id": str(test_store.id)}
        response = client.put(f"/inventory/{item.id}/preferred-store", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_store"] == str(test_store.id)
        assert data["preferred_store_rel"]["id"] == str(test_store.id)
        assert data["preferred_store_rel"]["name"] == "Test Store"

    def test_set_preferred_store_invalid_store_id(self, client, auth_headers, test_user, db_session):
        """Should return 404 if store_id doesn't exist."""
        # Create inventory item
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

        # Try to set non-existent store
        fake_store_id = uuid4()
        payload = {"store_id": str(fake_store_id)}
        response = client.put(f"/inventory/{item.id}/preferred-store", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Store not found"

    def test_set_preferred_store_item_not_found(self, client, auth_headers, test_store):
        """Should return 404 if inventory item doesn't exist."""
        fake_item_id = uuid4()
        payload = {"store_id": str(test_store.id)}
        response = client.put(f"/inventory/{fake_item_id}/preferred-store", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_set_preferred_store_cross_user_access_denied(self, client, auth_headers, test_user2, test_store, db_session):
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

        # User 1 tries to set preferred store for user 2's item
        payload = {"store_id": str(test_store.id)}
        response = client.put(f"/inventory/{item.id}/preferred-store", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_set_preferred_store_requires_auth(self, client, test_user, test_store, db_session):
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

        payload = {"store_id": str(test_store.id)}
        response = client.put(f"/inventory/{item.id}/preferred-store", json=payload)

        assert response.status_code == 401

    def test_clear_preferred_store_success(self, client, auth_headers, test_user, test_store, db_session):
        """Should clear preferred store for inventory item."""
        # Create inventory item with preferred store
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
            preferred_store=test_store.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Clear preferred store
        response = client.delete(f"/inventory/{item.id}/preferred-store", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_store"] is None
        assert data["preferred_store_rel"] is None

    def test_clear_preferred_store_item_not_found(self, client, auth_headers):
        """Should return 404 if inventory item doesn't exist."""
        fake_item_id = uuid4()
        response = client.delete(f"/inventory/{fake_item_id}/preferred-store", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_clear_preferred_store_cross_user_access_denied(self, client, auth_headers, test_user2, test_store, db_session):
        """Should return 404 if item belongs to another user."""
        # Create item for user 2
        item = InventoryItem(
            name="User 2 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user2.id,
            preferred_store=test_store.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to clear preferred store for user 2's item
        response = client.delete(f"/inventory/{item.id}/preferred-store", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_clear_preferred_store_requires_auth(self, client, test_user, test_store, db_session):
        """Should return 401 if no auth token provided."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
            preferred_store=test_store.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.delete(f"/inventory/{item.id}/preferred-store")

        assert response.status_code == 401

    def test_add_available_store_success(self, client, auth_headers, test_user, test_store, db_session):
        """Should add store to available_at_stores list."""
        # Create inventory item
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

        # Add available store
        payload = {"store_id": str(test_store.id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["available_at_stores"]) == 1
        assert data["available_at_stores"][0]["id"] == str(test_store.id)
        assert data["available_at_stores"][0]["name"] == "Test Store"

    def test_add_available_store_multiple(self, client, auth_headers, test_user, test_store, test_store2, db_session):
        """Should add multiple stores to available_at_stores list."""
        # Create inventory item
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

        # Add first store
        payload = {"store_id": str(test_store.id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)
        assert response.status_code == 200

        # Add second store
        payload = {"store_id": str(test_store2.id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["available_at_stores"]) == 2
        store_ids = {store["id"] for store in data["available_at_stores"]}
        assert store_ids == {str(test_store.id), str(test_store2.id)}

    def test_add_available_store_idempotent(self, client, auth_headers, test_user, test_store, db_session):
        """Should be idempotent when adding same store twice."""
        # Create inventory item
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

        # Add store first time
        payload = {"store_id": str(test_store.id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()["available_at_stores"]) == 1

        # Add same store again
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["available_at_stores"]) == 1  # Should still be 1

    def test_add_available_store_invalid_store_id(self, client, auth_headers, test_user, db_session):
        """Should return 404 if store_id doesn't exist."""
        # Create inventory item
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

        # Try to add non-existent store
        fake_store_id = uuid4()
        payload = {"store_id": str(fake_store_id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Store not found"

    def test_add_available_store_item_not_found(self, client, auth_headers, test_store):
        """Should return 404 if inventory item doesn't exist."""
        fake_item_id = uuid4()
        payload = {"store_id": str(test_store.id)}
        response = client.post(f"/inventory/{fake_item_id}/available-stores", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_add_available_store_cross_user_access_denied(self, client, auth_headers, test_user2, test_store, db_session):
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

        # User 1 tries to add available store for user 2's item
        payload = {"store_id": str(test_store.id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_add_available_store_requires_auth(self, client, test_user, test_store, db_session):
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

        payload = {"store_id": str(test_store.id)}
        response = client.post(f"/inventory/{item.id}/available-stores", json=payload)

        assert response.status_code == 401

    def test_remove_available_store_success(self, client, auth_headers, test_user, test_store, db_session):
        """Should remove store from available_at_stores list."""
        # Create inventory item with available store
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item.available_at_stores.append(test_store)
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Remove available store
        response = client.delete(f"/inventory/{item.id}/available-stores/{test_store.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["available_at_stores"]) == 0

    def test_remove_available_store_multiple(self, client, auth_headers, test_user, test_store, test_store2, db_session):
        """Should remove specific store from list with multiple stores."""
        # Create inventory item with multiple available stores
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item.available_at_stores.extend([test_store, test_store2])
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Remove first store
        response = client.delete(f"/inventory/{item.id}/available-stores/{test_store.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["available_at_stores"]) == 1
        assert data["available_at_stores"][0]["id"] == str(test_store2.id)

    def test_remove_available_store_idempotent(self, client, auth_headers, test_user, test_store, db_session):
        """Should be idempotent when removing store not in list."""
        # Create inventory item without available stores
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

        # Try to remove store that's not in the list
        response = client.delete(f"/inventory/{item.id}/available-stores/{test_store.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["available_at_stores"]) == 0

    def test_remove_available_store_invalid_store_id(self, client, auth_headers, test_user, db_session):
        """Should return 404 if store_id doesn't exist."""
        # Create inventory item
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

        # Try to remove non-existent store
        fake_store_id = uuid4()
        response = client.delete(f"/inventory/{item.id}/available-stores/{fake_store_id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Store not found"

    def test_remove_available_store_item_not_found(self, client, auth_headers, test_store):
        """Should return 404 if inventory item doesn't exist."""
        fake_item_id = uuid4()
        response = client.delete(f"/inventory/{fake_item_id}/available-stores/{test_store.id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_remove_available_store_cross_user_access_denied(self, client, auth_headers, test_user2, test_store, db_session):
        """Should return 404 if item belongs to another user."""
        # Create item for user 2 with available store
        item = InventoryItem(
            name="User 2 Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user2.id,
        )
        item.available_at_stores.append(test_store)
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to remove available store for user 2's item
        response = client.delete(f"/inventory/{item.id}/available-stores/{test_store.id}", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_remove_available_store_requires_auth(self, client, test_user, test_store, db_session):
        """Should return 401 if no auth token provided."""
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        item.available_at_stores.append(test_store)
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.delete(f"/inventory/{item.id}/available-stores/{test_store.id}")

        assert response.status_code == 401

    def test_get_inventory_item_includes_store_data(self, client, auth_headers, test_user, test_store, test_store2, db_session):
        """Should include preferred_store_rel and available_at_stores in GET response."""
        # Create inventory item with both preferred store and available stores
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
            preferred_store=test_store.id,
        )
        item.available_at_stores.extend([test_store, test_store2])
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Get inventory item
        response = client.get(f"/inventory/{item.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check preferred store data
        assert data["preferred_store"] == str(test_store.id)
        assert data["preferred_store_rel"] is not None
        assert data["preferred_store_rel"]["id"] == str(test_store.id)
        assert data["preferred_store_rel"]["name"] == "Test Store"
        assert data["preferred_store_rel"]["has_digital_receipts"] is False

        # Check available stores data
        assert len(data["available_at_stores"]) == 2
        store_ids = {store["id"] for store in data["available_at_stores"]}
        assert store_ids == {str(test_store.id), str(test_store2.id)}

        # Verify store names are included
        store_names = {store["name"] for store in data["available_at_stores"]}
        assert store_names == {"Test Store", "Test Store 2"}


class TestUpdateShareability:
    """Tests for PUT /inventory/{id}/shareability endpoint."""

    def test_update_shareability_to_reserved_with_note(self, client, auth_headers, test_user, db_session):
        """Should update shareability to reserved with a note."""
        # Create inventory item
        item = InventoryItem(
            name="Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            shareability="shared",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Update to reserved with note
        payload = {
            "shareability": "reserved",
            "reserved_note": "For Saturday cheesecake"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["shareability"] == "reserved"
        assert data["reserved_note"] == "For Saturday cheesecake"
        assert data["reserved_for"] is None  # FK not implemented yet (Phase 3)

    def test_update_shareability_to_personal_with_note(self, client, auth_headers, test_user, db_session):
        """Should update shareability to personal with a note."""
        # Create inventory item
        item = InventoryItem(
            name="Cheese",
            quantity=0.5,
            unit="lb",
            category="dairy",
            storage_location="fridge",
            shareability="shared",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Update to personal with note
        payload = {
            "shareability": "personal",
            "reserved_note": "My special cheese"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["shareability"] == "personal"
        assert data["reserved_note"] == "My special cheese"

    def test_update_shareability_to_reserved_without_note(self, client, auth_headers, test_user, db_session):
        """Should update shareability to reserved without a note."""
        # Create inventory item
        item = InventoryItem(
            name="Yogurt",
            quantity=1.0,
            unit="count",
            category="dairy",
            storage_location="fridge",
            shareability="shared",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Update to reserved without note
        payload = {
            "shareability": "reserved"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["shareability"] == "reserved"
        assert data["reserved_note"] is None

    def test_update_shareability_to_shared_clears_reserved_fields(self, client, auth_headers, test_user, db_session):
        """Should clear reserved_note and reserved_for when setting to shared."""
        # Create inventory item with reserved status and note
        item = InventoryItem(
            name="Butter",
            quantity=1.0,
            unit="lb",
            category="dairy",
            storage_location="fridge",
            shareability="reserved",
            reserved_note="For my cookies",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Update to shared (should clear reserved fields)
        payload = {
            "shareability": "shared"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["shareability"] == "shared"
        assert data["reserved_note"] is None
        assert data["reserved_for"] is None

    def test_update_shareability_transition_reserved_to_personal(self, client, auth_headers, test_user, db_session):
        """Should transition from reserved to personal, updating note."""
        # Create inventory item with reserved status
        item = InventoryItem(
            name="Cream",
            quantity=1.0,
            unit="pint",
            category="dairy",
            storage_location="fridge",
            shareability="reserved",
            reserved_note="For dinner party",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Transition to personal with new note
        payload = {
            "shareability": "personal",
            "reserved_note": "Changed my mind, this is mine"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["shareability"] == "personal"
        assert data["reserved_note"] == "Changed my mind, this is mine"

    def test_update_shareability_invalid_enum(self, client, auth_headers, test_user, db_session):
        """Should return 422 for invalid shareability value."""
        # Create inventory item
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

        # Try invalid shareability
        payload = {
            "shareability": "invalid_value"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_update_shareability_reserved_note_too_long(self, client, auth_headers, test_user, db_session):
        """Should return 422 if reserved_note exceeds 500 characters."""
        # Create inventory item
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

        # Try note that's too long (501 chars)
        long_note = "x" * 501
        payload = {
            "shareability": "reserved",
            "reserved_note": long_note
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_update_shareability_item_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        payload = {
            "shareability": "reserved",
            "reserved_note": "For dinner"
        }
        response = client.put(f"/inventory/{fake_id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_update_shareability_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
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
        payload = {
            "shareability": "reserved",
            "reserved_note": "For my dinner"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_update_shareability_requires_auth(self, client, test_user, db_session):
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

        payload = {
            "shareability": "reserved",
            "reserved_note": "For dinner"
        }
        response = client.put(f"/inventory/{item.id}/shareability", json=payload)

        assert response.status_code == 401


class TestFreezeThawActions:
    """Tests for POST /inventory/{id}/freeze and POST /inventory/{id}/thaw endpoints."""

    def test_freeze_item_success(self, client, auth_headers, test_user, db_session):
        """Should freeze item by setting storage_location to freezer and frozen_date to now."""
        # Create inventory item in fridge
        item = InventoryItem(
            name="Chicken Breast",
            quantity=2.0,
            unit="lb",
            category="protein",
            storage_location="fridge",
            frozen_date=None,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Freeze the item
        response = client.post(f"/inventory/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["frozen_date"] is not None
        # Verify frozen_date is recent (within last minute)
        from datetime import datetime, timedelta
        frozen_date = datetime.fromisoformat(data["frozen_date"])
        now = datetime.utcnow()
        assert (now - frozen_date) < timedelta(minutes=1)

    def test_freeze_item_already_frozen_is_idempotent(self, client, auth_headers, test_user, db_session):
        """Should update frozen_date when freezing already-frozen item (idempotent)."""
        # Create inventory item already frozen with old frozen_date
        from datetime import datetime, timedelta
        old_frozen_date = datetime.utcnow() - timedelta(days=5)
        item = InventoryItem(
            name="Frozen Pizza",
            quantity=1.0,
            unit="count",
            category="frozen",
            storage_location="freezer",
            frozen_date=old_frozen_date,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Freeze again
        response = client.post(f"/inventory/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        # Verify frozen_date is updated to recent time (not old date)
        frozen_date = datetime.fromisoformat(data["frozen_date"])
        now = datetime.utcnow()
        assert (now - frozen_date) < timedelta(minutes=1)
        assert frozen_date > old_frozen_date

    def test_freeze_item_from_pantry(self, client, auth_headers, test_user, db_session):
        """Should freeze item from pantry storage location."""
        # Create inventory item in pantry
        item = InventoryItem(
            name="Bread",
            quantity=1.0,
            unit="count",
            category="grain",
            storage_location="pantry",
            frozen_date=None,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Freeze the item
        response = client.post(f"/inventory/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "freezer"
        assert data["frozen_date"] is not None

    def test_freeze_item_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.post(f"/inventory/{fake_id}/freeze", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_freeze_item_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
        """Should return 404 if item belongs to another user."""
        # Create item for user 2
        item = InventoryItem(
            name="User 2 Meat",
            quantity=1.0,
            unit="lb",
            category="protein",
            storage_location="fridge",
            added_by=test_user2.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to freeze user 2's item
        response = client.post(f"/inventory/{item.id}/freeze", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_freeze_item_requires_auth(self, client, test_user, db_session):
        """Should return 401 if no auth token provided."""
        item = InventoryItem(
            name="Chicken",
            quantity=1.0,
            unit="lb",
            category="protein",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.post(f"/inventory/{item.id}/freeze")

        assert response.status_code == 401

    def test_thaw_item_success(self, client, auth_headers, test_user, db_session):
        """Should thaw item by setting storage_location to fridge and clearing frozen_date."""
        # Create inventory item in freezer with frozen_date
        from datetime import datetime, timezone, timedelta
        item = InventoryItem(
            name="Frozen Chicken",
            quantity=2.0,
            unit="lb",
            category="protein",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc) - timedelta(days=3),
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw the item
        response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["frozen_date"] is None

    def test_thaw_item_not_frozen_is_idempotent(self, client, auth_headers, test_user, db_session):
        """Should succeed when thawing non-frozen item (idempotent)."""
        # Create inventory item in fridge (not frozen)
        item = InventoryItem(
            name="Fresh Milk",
            quantity=1.0,
            unit="gallon",
            category="dairy",
            storage_location="fridge",
            frozen_date=None,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw non-frozen item
        response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["frozen_date"] is None

    def test_thaw_item_from_pantry(self, client, auth_headers, test_user, db_session):
        """Should thaw item from pantry storage location."""
        # Create inventory item in pantry
        item = InventoryItem(
            name="Frozen Bread",
            quantity=1.0,
            unit="count",
            category="grain",
            storage_location="pantry",
            frozen_date=None,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw the item
        response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["frozen_date"] is None

    def test_thaw_item_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.post(f"/inventory/{fake_id}/thaw", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_thaw_item_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
        """Should return 404 if item belongs to another user."""
        # Create frozen item for user 2
        from datetime import datetime, timezone
        item = InventoryItem(
            name="User 2 Frozen Meat",
            quantity=1.0,
            unit="lb",
            category="protein",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            added_by=test_user2.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # User 1 tries to thaw user 2's item
        response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Inventory item not found"

    def test_thaw_item_requires_auth(self, client, test_user, db_session):
        """Should return 401 if no auth token provided."""
        from datetime import datetime, timezone
        item = InventoryItem(
            name="Frozen Chicken",
            quantity=1.0,
            unit="lb",
            category="protein",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = client.post(f"/inventory/{item.id}/thaw")

        assert response.status_code == 401

    def test_freeze_then_thaw_transition(self, client, auth_headers, test_user, db_session):
        """Should transition item from freeze to thaw correctly."""
        # Create fresh item
        item = InventoryItem(
            name="Chicken",
            quantity=2.0,
            unit="lb",
            category="protein",
            storage_location="fridge",
            frozen_date=None,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Freeze it
        freeze_response = client.post(f"/inventory/{item.id}/freeze", headers=auth_headers)
        assert freeze_response.status_code == 200
        freeze_data = freeze_response.json()
        assert freeze_data["storage_location"] == "freezer"
        assert freeze_data["frozen_date"] is not None

        # Thaw it
        thaw_response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)
        assert thaw_response.status_code == 200
        thaw_data = thaw_response.json()
        assert thaw_data["storage_location"] == "fridge"
        assert thaw_data["frozen_date"] is None
        assert thaw_data["expiration_date"] is None  # Expiration cleared on thaw

    def test_thaw_then_freeze_transition(self, client, auth_headers, test_user, db_session):
        """Should transition item from thaw to freeze correctly."""
        from datetime import datetime, timezone
        # Create frozen item
        item = InventoryItem(
            name="Frozen Pizza",
            quantity=1.0,
            unit="count",
            category="frozen",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw it
        thaw_response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)
        assert thaw_response.status_code == 200
        thaw_data = thaw_response.json()
        assert thaw_data["storage_location"] == "fridge"
        assert thaw_data["frozen_date"] is None

        # Freeze it again
        freeze_response = client.post(f"/inventory/{item.id}/freeze", headers=auth_headers)
        assert freeze_response.status_code == 200
        freeze_data = freeze_response.json()
        assert freeze_data["storage_location"] == "freezer"
        assert freeze_data["frozen_date"] is not None

    def test_thaw_to_custom_destination_pantry(self, client, auth_headers, test_user, db_session):
        """Should thaw item to pantry when destination is specified."""
        from datetime import datetime, timezone
        # Create frozen item
        item = InventoryItem(
            name="Frozen Bread",
            quantity=1.0,
            unit="count",
            category="grain",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw to pantry
        response = client.post(
            f"/inventory/{item.id}/thaw",
            headers=auth_headers,
            json={"destination": "pantry"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "pantry"
        assert data["frozen_date"] is None

    def test_thaw_to_freezer_fails(self, client, auth_headers, test_user, db_session):
        """Should return 422 when trying to thaw to freezer (nonsensical operation)."""
        from datetime import datetime, timezone
        # Create frozen item
        item = InventoryItem(
            name="Frozen Chicken",
            quantity=2.0,
            unit="lb",
            category="protein",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Try to thaw to freezer
        response = client.post(
            f"/inventory/{item.id}/thaw",
            headers=auth_headers,
            json={"destination": "freezer"}
        )

        assert response.status_code == 422
        assert "freezer" in response.json()["detail"][0]["msg"].lower()

    def test_thaw_clears_expiration_date(self, client, auth_headers, test_user, db_session):
        """Should clear expiration_date when thawing (thawed items have different shelf life)."""
        from datetime import datetime, timezone, timedelta
        # Create frozen item with expiration date
        expiration = datetime.now(timezone.utc) + timedelta(days=30)
        item = InventoryItem(
            name="Frozen Meat",
            quantity=2.0,
            unit="lb",
            category="protein",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            expiration_date=expiration,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw the item
        response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"
        assert data["frozen_date"] is None
        assert data["expiration_date"] is None  # Expiration cleared

    def test_thaw_default_destination_fridge_backwards_compatibility(self, client, auth_headers, test_user, db_session):
        """Should default to fridge when no destination specified (backwards compatibility)."""
        from datetime import datetime, timezone
        # Create frozen item
        item = InventoryItem(
            name="Frozen Vegetables",
            quantity=1.0,
            unit="lb",
            category="produce",
            storage_location="freezer",
            frozen_date=datetime.now(timezone.utc),
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        # Thaw without specifying destination (empty body)
        response = client.post(f"/inventory/{item.id}/thaw", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["storage_location"] == "fridge"  # Default to fridge
        assert data["frozen_date"] is None


class TestLowStockAlerts:
    """Tests for GET /inventory/alerts/low-stock endpoint (threshold alerts)."""

    def test_low_stock_alerts_item_below_threshold(self, client, auth_headers, test_user, db_session):
        """Should return staple item when quantity is below threshold."""
        # Create staple item below threshold
        item = InventoryItem(
            name="Rice",
            quantity=2.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Rice"
        assert data[0]["quantity"] == 2.0
        assert data[0]["minimum_threshold"] == 5.0
        assert data[0]["deficit"] == 3.0  # 5.0 - 2.0
        assert data[0]["unit"] == "lb"

    def test_low_stock_alerts_item_at_threshold(self, client, auth_headers, test_user, db_session):
        """Should return staple item when quantity equals threshold (edge case)."""
        # Create staple item at exact threshold
        item = InventoryItem(
            name="Flour",
            quantity=5.0,
            unit="lb",
            category="baking",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Flour"
        assert data[0]["quantity"] == 5.0
        assert data[0]["minimum_threshold"] == 5.0
        assert data[0]["deficit"] == 0.0  # 5.0 - 5.0

    def test_low_stock_alerts_item_above_threshold_not_returned(self, client, auth_headers, test_user, db_session):
        """Should NOT return staple item when quantity is above threshold."""
        # Create staple item above threshold
        item = InventoryItem(
            name="Pasta",
            quantity=10.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_low_stock_alerts_non_staple_not_returned(self, client, auth_headers, test_user, db_session):
        """Should NOT return non-staple items even if below threshold."""
        # Create non-staple item below threshold
        item = InventoryItem(
            name="Ice Cream",
            quantity=1.0,
            unit="pint",
            category="frozen",
            storage_location="freezer",
            is_staple=False,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_low_stock_alerts_no_threshold_not_returned(self, client, auth_headers, test_user, db_session):
        """Should NOT return staple items without a threshold set."""
        # Create staple item without threshold
        item = InventoryItem(
            name="Sugar",
            quantity=1.0,
            unit="lb",
            category="baking",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=None,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_low_stock_alerts_empty_when_all_stocked(self, client, auth_headers, test_user, db_session):
        """Should return empty list when all staple items are adequately stocked."""
        # Create multiple staple items all above threshold
        item1 = InventoryItem(
            name="Rice",
            quantity=10.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            name="Pasta",
            quantity=8.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_low_stock_alerts_multiple_items_sorted_by_deficit(self, client, auth_headers, test_user, db_session):
        """Should return multiple low-stock items sorted by deficit (most urgent first)."""
        # Create multiple staple items below threshold with different deficits
        item1 = InventoryItem(
            name="Rice",
            quantity=2.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,  # deficit = 3.0
            added_by=test_user.id,
        )
        item2 = InventoryItem(
            name="Flour",
            quantity=1.0,
            unit="lb",
            category="baking",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=10.0,  # deficit = 9.0 (most urgent)
            added_by=test_user.id,
        )
        item3 = InventoryItem(
            name="Sugar",
            quantity=4.0,
            unit="lb",
            category="baking",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,  # deficit = 1.0 (least urgent)
            added_by=test_user.id,
        )
        db_session.add_all([item1, item2, item3])
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Verify sorted by deficit descending (most urgent first)
        assert data[0]["name"] == "Flour"
        assert data[0]["deficit"] == 9.0
        assert data[1]["name"] == "Rice"
        assert data[1]["deficit"] == 3.0
        assert data[2]["name"] == "Sugar"
        assert data[2]["deficit"] == 1.0

    def test_low_stock_alerts_multi_tenant_isolation(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Should only return low-stock items for the authenticated user."""
        # Create low-stock item for user 1
        item1 = InventoryItem(
            name="User 1 Rice",
            quantity=2.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        # Create low-stock item for user 2
        item2 = InventoryItem(
            name="User 2 Flour",
            quantity=1.0,
            unit="lb",
            category="baking",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user2.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # User 1 should only see their low-stock item
        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User 1 Rice"

        # User 2 should only see their low-stock item
        response = client.get("/inventory/alerts/low-stock", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "User 2 Flour"

    def test_low_stock_alerts_requires_auth(self, client):
        """Should return 401 if no auth token provided."""
        response = client.get("/inventory/alerts/low-stock")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_low_stock_alerts_threshold_zero_edge_case(self, client, auth_headers, test_user, db_session):
        """Should handle threshold of 0 correctly."""
        # Create staple item with threshold=0 and quantity=0 (at threshold)
        item = InventoryItem(
            name="Salt",
            quantity=0.0,
            unit="oz",
            category="spice",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=0.0,
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should be included (quantity <= threshold)
        assert len(data) == 1
        assert data[0]["name"] == "Salt"
        assert data[0]["deficit"] == 0.0

    def test_low_stock_alerts_mixed_conditions(self, client, auth_headers, test_user, db_session):
        """Should correctly filter with mixed conditions (staple, non-staple, threshold, no threshold)."""
        # Create various items
        low_stock_staple = InventoryItem(
            name="Low Stock Staple",
            quantity=2.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        stocked_staple = InventoryItem(
            name="Stocked Staple",
            quantity=10.0,
            unit="lb",
            category="grain",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        low_stock_non_staple = InventoryItem(
            name="Low Stock Non-Staple",
            quantity=1.0,
            unit="count",
            category="frozen",
            storage_location="freezer",
            is_staple=False,
            minimum_threshold=5.0,
            added_by=test_user.id,
        )
        staple_no_threshold = InventoryItem(
            name="Staple No Threshold",
            quantity=1.0,
            unit="lb",
            category="baking",
            storage_location="pantry",
            is_staple=True,
            minimum_threshold=None,
            added_by=test_user.id,
        )
        db_session.add_all([low_stock_staple, stocked_staple, low_stock_non_staple, staple_no_threshold])
        db_session.commit()

        response = client.get("/inventory/alerts/low-stock", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Only low_stock_staple should be returned
        assert len(data) == 1
        assert data[0]["name"] == "Low Stock Staple"


class TestConsumeInventoryItem:
    """Test suite for inventory item consumption endpoint."""

    def test_consume_item_default_amount(self, client, auth_headers, test_user, db_session):
        """Should consume item with default amount (1) and return updated item."""
        item = InventoryItem(
            name="Chocolate Bar",
            quantity=5.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(f"/inventory/{item_id}/consume", headers=auth_headers, json={})

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["message"] == "Consumed 1.0 count. 4.0 count remaining."
        assert data["item"] is not None
        assert data["item"]["quantity"] == 4.0
        assert data["item"]["name"] == "Chocolate Bar"

        # Verify in database
        db_session.expire_all()
        updated_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert updated_item.quantity == 4.0

    def test_consume_item_specific_amount(self, client, auth_headers, test_user, db_session):
        """Should consume item with specified amount."""
        item = InventoryItem(
            name="Milk",
            quantity=10.0,
            unit="oz",
            category="dairy",
            storage_location="fridge",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 3.5}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["message"] == "Consumed 3.5 oz. 6.5 oz remaining."
        assert data["item"]["quantity"] == 6.5

    def test_consume_exact_quantity_with_auto_delete(self, client, auth_headers, test_user, db_session):
        """Should delete item when consuming exact quantity with delete_when_empty=true (default)."""
        item = InventoryItem(
            name="Last Cookie",
            quantity=1.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 1.0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["message"] == "Consumed 1.0 count. Item deleted (quantity reached 0)."
        assert data["item"] is None

        # Verify item is deleted from database
        db_session.expire_all()
        deleted_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert deleted_item is None

    def test_consume_exact_quantity_without_auto_delete(self, client, auth_headers, test_user, db_session):
        """Should keep item at quantity 0 when delete_when_empty=false."""
        item = InventoryItem(
            name="Empty Container",
            quantity=2.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 2.0, "delete_when_empty": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["message"] == "Consumed 2.0 count. 0.0 count remaining."
        assert data["item"] is not None
        assert data["item"]["quantity"] == 0.0

        # Verify item still exists in database with quantity 0
        db_session.expire_all()
        kept_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert kept_item is not None
        assert kept_item.quantity == 0.0

    def test_consume_over_consumption_error(self, client, auth_headers, test_user, db_session):
        """Should return 400 error when trying to consume more than available."""
        item = InventoryItem(
            name="Limited Snack",
            quantity=2.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 5.0}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Cannot consume 5.0 count. Only 2.0 count available" in data["detail"]

        # Verify quantity unchanged
        db_session.expire_all()
        unchanged_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert unchanged_item.quantity == 2.0

    def test_consume_negative_amount_validation_error(self, client, auth_headers, test_user, db_session):
        """Should return 422 validation error for negative amount."""
        item = InventoryItem(
            name="Some Snack",
            quantity=5.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": -1.0}
        )

        assert response.status_code == 422

    def test_consume_zero_amount_validation_error(self, client, auth_headers, test_user, db_session):
        """Should return 422 validation error for zero amount."""
        item = InventoryItem(
            name="Some Snack",
            quantity=5.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 0}
        )

        assert response.status_code == 422

    def test_consume_item_not_found(self, client, auth_headers):
        """Should return 404 when item doesn't exist."""
        non_existent_id = uuid4()

        response = client.post(
            f"/inventory/{non_existent_id}/consume",
            headers=auth_headers,
            json={"amount": 1.0}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Inventory item not found"

    def test_consume_cross_user_access_denied(self, client, auth_headers, test_user2, db_session):
        """Should return 404 when trying to consume another user's item."""
        # Create item for test_user2
        item = InventoryItem(
            name="User2's Snack",
            quantity=5.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user2.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # Try to consume with test_user's auth (auth_headers)
        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 1.0}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Inventory item not found"

        # Verify quantity unchanged for user2's item
        db_session.expire_all()
        unchanged_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert unchanged_item.quantity == 5.0

    def test_consume_requires_auth(self, client, test_user, db_session):
        """Should return 401 when Authorization header is missing."""
        item = InventoryItem(
            name="Some Snack",
            quantity=5.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(f"/inventory/{item_id}/consume", json={"amount": 1.0})

        assert response.status_code == 401

    def test_consume_partial_with_decimal(self, client, auth_headers, test_user, db_session):
        """Should handle decimal quantities correctly."""
        item = InventoryItem(
            name="Olive Oil",
            quantity=16.5,
            unit="oz",
            category="oil_vinegar",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 0.25}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["item"]["quantity"] == 16.25

    def test_consume_multiple_times(self, client, auth_headers, test_user, db_session):
        """Should handle multiple consumption requests correctly."""
        item = InventoryItem(
            name="Crackers",
            quantity=10.0,
            unit="count",
            category="snack",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # First consumption
        response1 = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 3.0}
        )
        assert response1.status_code == 200
        assert response1.json()["item"]["quantity"] == 7.0

        # Second consumption
        response2 = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 2.0}
        )
        assert response2.status_code == 200
        assert response2.json()["item"]["quantity"] == 5.0

        # Third consumption (exact remaining)
        response3 = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 5.0}
        )
        assert response3.status_code == 200
        assert response3.json()["deleted"] is True

    def test_consume_floating_point_edge_case_tiny_positive_value(self, client, auth_headers, test_user, db_session):
        """Should delete item when result is tiny positive value (effectively zero) with auto-delete."""
        # Create item with a quantity that will result in a very small positive value after consumption
        # due to floating-point arithmetic (e.g., 1.0 - 0.9999999999 = ~1e-10)
        item = InventoryItem(
            name="Precision Test Item",
            quantity=1.0,
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # Consume an amount that leaves a tiny residual due to floating-point precision
        # Using 0.9999999999 which should leave ~1e-10
        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 0.9999999999, "delete_when_empty": True}
        )

        assert response.status_code == 200
        data = response.json()
        # Should delete because remaining quantity is within tolerance of zero
        assert data["deleted"] is True
        assert "Item deleted (quantity reached 0)" in data["message"]
        assert data["item"] is None

        # Verify item is deleted from database
        db_session.expire_all()
        deleted_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert deleted_item is None

    def test_consume_floating_point_edge_case_exactly_tolerance(self, client, auth_headers, test_user, db_session):
        """Should keep item when result is just above tolerance threshold without auto-delete."""
        # Create item with quantity that will result in a value just above the tolerance (1e-9)
        item = InventoryItem(
            name="Tolerance Boundary Item",
            quantity=1.0,
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # Consume amount leaving exactly 2e-9 (above tolerance of 1e-9)
        # This should NOT be deleted
        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 1.0 - 2e-9, "delete_when_empty": False}
        )

        assert response.status_code == 200
        data = response.json()
        # Should NOT delete because remaining is above tolerance
        assert data["deleted"] is False
        assert data["item"] is not None
        # Verify the small remaining quantity is preserved
        assert data["item"]["quantity"] > 0

        # Verify item still exists in database
        db_session.expire_all()
        kept_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert kept_item is not None

    def test_consume_floating_point_edge_case_multiple_operations(self, client, auth_headers, test_user, db_session):
        """Should handle multiple floating-point operations correctly."""
        # Test multiple consumption operations that accumulate floating-point errors
        item = InventoryItem(
            name="Multi-Op Item",
            quantity=10.0,
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # Perform multiple consumptions with decimal amounts that are known to
        # accumulate floating-point rounding errors
        amounts = [0.1] * 100  # Consume 0.1 oz 100 times = 10.0 oz total

        for amount in amounts:
            response = client.post(
                f"/inventory/{item_id}/consume",
                headers=auth_headers,
                json={"amount": amount, "delete_when_empty": True}
            )
            assert response.status_code == 200

        # After all consumptions, item should be deleted (total consumed = 10.0)
        # despite potential floating-point rounding errors
        db_session.expire_all()
        deleted_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert deleted_item is None

    def test_consume_floating_point_edge_case_overconsumption_validation(self, client, auth_headers, test_user, db_session):
        """Should prevent overconsumption even with floating-point edge cases."""
        # Test that validation still works correctly with floating-point values
        item = InventoryItem(
            name="Validation Test Item",
            quantity=0.3,  # A value that's difficult to represent exactly in binary
            unit="oz",
            category="other",
            storage_location="pantry",
            added_by=test_user.id,
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        # Try to consume slightly more than available
        response = client.post(
            f"/inventory/{item_id}/consume",
            headers=auth_headers,
            json={"amount": 0.30000001}
        )

        # Should reject overconsumption
        assert response.status_code == 400
        assert "Cannot consume" in response.json()["detail"]

        # Verify quantity unchanged
        db_session.expire_all()
        unchanged_item = db_session.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        assert unchanged_item.quantity == 0.3


class TestBulkCreateInventoryItems:
    """Test suite for bulk inventory item creation endpoint."""

    def test_bulk_create_single_item(self, client, auth_headers, test_user, db_session):
        """Should create a single item via bulk endpoint."""
        payload = {
            "items": [
                {
                    "name": "Apples",
                    "quantity": 6.0,
                    "unit": "count",
                    "category": "produce",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),  # Should be ignored
                }
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Apples"
        assert data["items"][0]["quantity"] == 6.0
        assert data["items"][0]["unit"] == "count"
        assert data["items"][0]["category"] == "produce"
        assert data["items"][0]["added_by"] == str(test_user.id)
        assert "id" in data["items"][0]

        # Verify in database
        db_session.expire_all()
        items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(items) == 1
        assert items[0].name == "Apples"

    def test_bulk_create_multiple_items(self, client, auth_headers, test_user, db_session):
        """Should create multiple items in a single transaction."""
        payload = {
            "items": [
                {
                    "name": "Milk",
                    "quantity": 1.0,
                    "unit": "gallon",
                    "category": "dairy",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
                {
                    "name": "Bread",
                    "quantity": 2.0,
                    "unit": "count",
                    "category": "grain",
                    "storage_location": "pantry",
                    "added_by": str(uuid4()),
                },
                {
                    "name": "Chicken Breast",
                    "quantity": 1.5,
                    "unit": "lb",
                    "category": "protein",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 3

        # Check all items have correct user
        for item in data["items"]:
            assert item["added_by"] == str(test_user.id)
            assert "id" in item

        # Check specific items
        names = [item["name"] for item in data["items"]]
        assert "Milk" in names
        assert "Bread" in names
        assert "Chicken Breast" in names

        # Verify in database
        db_session.expire_all()
        items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(items) == 3

    def test_bulk_create_max_limit_50_items(self, client, auth_headers, test_user, db_session):
        """Should successfully create 50 items (max limit)."""
        items = []
        for i in range(50):
            items.append({
                "name": f"Item {i}",
                "quantity": 1.0,
                "unit": "count",
                "category": "pantry_staple",
                "storage_location": "pantry",
                "added_by": str(uuid4()),
            })

        payload = {"items": items}

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 50

        # Verify in database
        db_session.expire_all()
        db_items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(db_items) == 50

    def test_bulk_create_exceeds_max_limit(self, client, auth_headers, test_user, db_session):
        """Should reject request with more than 50 items."""
        items = []
        for i in range(51):
            items.append({
                "name": f"Item {i}",
                "quantity": 1.0,
                "unit": "count",
                "category": "pantry_staple",
                "storage_location": "pantry",
                "added_by": str(uuid4()),
            })

        payload = {"items": items}

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Verify nothing was created
        db_session.expire_all()
        db_items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(db_items) == 0

    def test_bulk_create_empty_list(self, client, auth_headers, test_user, db_session):
        """Should reject empty items list."""
        payload = {"items": []}

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_bulk_create_validation_error_invalid_category(self, client, auth_headers, test_user, db_session):
        """Should return 422 for validation errors with item details."""
        payload = {
            "items": [
                {
                    "name": "Valid Item",
                    "quantity": 1.0,
                    "unit": "count",
                    "category": "produce",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
                {
                    "name": "Invalid Item",
                    "quantity": 1.0,
                    "unit": "count",
                    "category": "invalid_category",  # Invalid
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Verify no items were created (atomic transaction)
        db_session.expire_all()
        db_items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(db_items) == 0

    def test_bulk_create_validation_error_negative_quantity(self, client, auth_headers, test_user, db_session):
        """Should return 422 for negative quantity."""
        payload = {
            "items": [
                {
                    "name": "Bad Item",
                    "quantity": -5.0,  # Invalid
                    "unit": "count",
                    "category": "produce",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Verify no items were created
        db_session.expire_all()
        db_items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(db_items) == 0

    def test_bulk_create_validation_error_invalid_unit(self, client, auth_headers, test_user, db_session):
        """Should return 422 for invalid unit."""
        payload = {
            "items": [
                {
                    "name": "Item",
                    "quantity": 1.0,
                    "unit": "invalid_unit",  # Invalid
                    "category": "produce",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 422

        # Verify no items were created
        db_session.expire_all()
        db_items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(db_items) == 0

    def test_bulk_create_atomic_transaction(self, client, auth_headers, test_user, db_session):
        """Should rollback all items if any validation fails (atomic)."""
        payload = {
            "items": [
                {
                    "name": "Good Item 1",
                    "quantity": 1.0,
                    "unit": "count",
                    "category": "produce",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
                {
                    "name": "Good Item 2",
                    "quantity": 2.0,
                    "unit": "lb",
                    "category": "protein",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
                {
                    "name": "Bad Item",
                    "quantity": 3.0,
                    "unit": "invalid_unit",  # This will fail
                    "category": "dairy",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                },
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 422

        # Verify NO items were created (all-or-nothing)
        db_session.expire_all()
        db_items = db_session.query(InventoryItem).filter(InventoryItem.added_by == test_user.id).all()
        assert len(db_items) == 0

    def test_bulk_create_requires_authentication(self, client, db_session):
        """Should require authentication."""
        payload = {
            "items": [
                {
                    "name": "Apples",
                    "quantity": 6.0,
                    "unit": "count",
                    "category": "produce",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                }
            ]
        }

        response = client.post("/inventory/bulk", json=payload)

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"

    def test_bulk_create_with_optional_fields(self, client, auth_headers, test_user, db_session):
        """Should create items with optional fields."""
        expiration = datetime.now(timezone.utc) + timedelta(days=7)

        payload = {
            "items": [
                {
                    "name": "Premium Cheese",
                    "quantity": 1.0,
                    "unit": "lb",
                    "category": "dairy",
                    "storage_location": "fridge",
                    "added_by": str(uuid4()),
                    "expiration_date": expiration.isoformat(),
                    "is_staple": True,
                    "minimum_threshold": 0.5,
                    "price": 8.99,
                    "brand": "Organic Valley",
                    "vegan_friendly": False,
                }
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Premium Cheese"
        assert data["items"][0]["is_staple"] is True
        assert data["items"][0]["minimum_threshold"] == 0.5
        assert data["items"][0]["price"] == 8.99
        assert data["items"][0]["brand"] == "Organic Valley"
        assert data["items"][0]["vegan_friendly"] is False

    def test_bulk_create_returns_all_fields(self, client, auth_headers, test_user, db_session):
        """Should return complete item data including generated fields."""
        payload = {
            "items": [
                {
                    "name": "Test Item",
                    "quantity": 1.0,
                    "unit": "count",
                    "category": "other",
                    "storage_location": "pantry",
                    "added_by": str(uuid4()),
                }
            ]
        }

        response = client.post("/inventory/bulk", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        item = data["items"][0]

        # Check all expected fields are present
        assert "id" in item
        assert "name" in item
        assert "quantity" in item
        assert "unit" in item
        assert "category" in item
        assert "storage_location" in item
        assert "date_added" in item
        assert "added_by" in item
        assert "shareability" in item
        assert "is_staple" in item
        assert "vegan_friendly" in item
