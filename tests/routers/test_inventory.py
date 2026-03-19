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
        assert "Invalid category" in response.json()["detail"]

    def test_filter_invalid_storage_location(self, client, auth_headers):
        """Should return 422 for invalid storage_location."""
        response = client.get("/inventory?storage_location=invalid_location", headers=auth_headers)
        assert response.status_code == 422
        assert "Invalid storage_location" in response.json()["detail"]

    def test_filter_invalid_shareability(self, client, auth_headers):
        """Should return 422 for invalid shareability."""
        response = client.get("/inventory?shareability=invalid_share", headers=auth_headers)
        assert response.status_code == 422
        assert "Invalid shareability" in response.json()["detail"]

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
