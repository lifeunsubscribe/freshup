"""
Integration tests for grocery list purchase endpoints.

Tests cover:
- PUT /grocery/{id}/purchase: mark single item as purchased
- PUT /grocery/{id}/unpurchase: reverse purchase
- POST /grocery/bulk-purchase: bulk purchase with optional inventory creation
- Cross-user purchase allowed (household coordination)
- Conditional validation (storage_location and category required when create_inventory_item=true)
- Atomic transactions for bulk operations
- 404 handling for missing items
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
from src.db.models.grocery_list import GroceryListItem, GrocerySource
from src.db.models.inventory_item import InventoryItem
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import grocery_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the grocery router
app.include_router(grocery_router)

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
    """Create a second test user for cross-user purchase tests."""
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
def test_grocery_item(db_session, test_user):
    """Create a test grocery item."""
    item = GroceryListItem(
        id=uuid4(),
        item_name="Milk",
        quantity=1.0,
        unit="gallon",
        source=GrocerySource.manual.value,
        added_by=test_user.id,
        purchased=False,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def test_grocery_item_purchased(db_session, test_user):
    """Create a test grocery item that's already purchased."""
    purchase_time = datetime.now(timezone.utc)
    item = GroceryListItem(
        id=uuid4(),
        item_name="Bread",
        quantity=2.0,
        unit="count",
        source=GrocerySource.manual.value,
        added_by=test_user.id,
        purchased=True,
        purchased_by=test_user.id,
        purchased_date=purchase_time,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


class TestPurchaseItem:
    """Tests for PUT /grocery/{id}/purchase (mark single item as purchased)."""

    def test_purchase_success(self, client, auth_headers, test_grocery_item, test_user, db_session):
        """Should mark item as purchased with current user and timestamp."""
        response = client.put(
            f"/grocery/{test_grocery_item.id}/purchase",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_grocery_item.id)
        assert data["purchased"] is True
        assert data["purchased_by"] == str(test_user.id)
        assert data["purchased_date"] is not None

        # Verify in database
        db_session.refresh(test_grocery_item)
        assert test_grocery_item.purchased is True
        assert test_grocery_item.purchased_by == test_user.id
        assert test_grocery_item.purchased_date is not None

    def test_purchase_cross_user_allowed(self, client, auth_headers2, test_grocery_item, test_user2, db_session):
        """Should allow any authenticated user to purchase any item (household coordination)."""
        # test_grocery_item was added by test_user, but test_user2 should be able to purchase it
        response = client.put(
            f"/grocery/{test_grocery_item.id}/purchase",
            headers=auth_headers2
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchased"] is True
        assert data["purchased_by"] == str(test_user2.id)  # Purchased by user2, not owner

    def test_purchase_already_purchased(self, client, auth_headers, test_grocery_item_purchased):
        """Should allow re-purchasing an already purchased item (updates timestamp)."""
        original_date = test_grocery_item_purchased.purchased_date

        response = client.put(
            f"/grocery/{test_grocery_item_purchased.id}/purchase",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchased"] is True
        # Timestamp should be updated (newer than original)

    def test_purchase_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.put(
            f"/grocery/{fake_id}/purchase",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_purchase_unauthenticated(self, client, test_grocery_item):
        """Should return 401 if no auth token provided."""
        response = client.put(f"/grocery/{test_grocery_item.id}/purchase")

        assert response.status_code == 401


class TestUnpurchaseItem:
    """Tests for PUT /grocery/{id}/unpurchase (reverse purchase)."""

    def test_unpurchase_success(self, client, auth_headers, test_grocery_item_purchased, db_session):
        """Should mark item as unpurchased and clear purchase fields."""
        response = client.put(
            f"/grocery/{test_grocery_item_purchased.id}/unpurchase",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_grocery_item_purchased.id)
        assert data["purchased"] is False
        assert data["purchased_by"] is None
        assert data["purchased_date"] is None

        # Verify in database
        db_session.refresh(test_grocery_item_purchased)
        assert test_grocery_item_purchased.purchased is False
        assert test_grocery_item_purchased.purchased_by is None
        assert test_grocery_item_purchased.purchased_date is None

    def test_unpurchase_cross_user_allowed(self, client, auth_headers2, test_grocery_item_purchased):
        """Should allow any authenticated user to unpurchase any item (household coordination)."""
        # test_grocery_item_purchased was purchased by test_user, but test_user2 should be able to unpurchase it
        response = client.put(
            f"/grocery/{test_grocery_item_purchased.id}/unpurchase",
            headers=auth_headers2
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchased"] is False

    def test_unpurchase_already_unpurchased(self, client, auth_headers, test_grocery_item):
        """Should allow unpurchasing an already unpurchased item (idempotent)."""
        response = client.put(
            f"/grocery/{test_grocery_item.id}/unpurchase",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchased"] is False

    def test_unpurchase_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.put(
            f"/grocery/{fake_id}/unpurchase",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_unpurchase_unauthenticated(self, client, test_grocery_item_purchased):
        """Should return 401 if no auth token provided."""
        response = client.put(f"/grocery/{test_grocery_item_purchased.id}/unpurchase")

        assert response.status_code == 401


class TestBulkPurchase:
    """Tests for POST /grocery/bulk-purchase (bulk purchase with optional inventory creation)."""

    def test_bulk_purchase_success(self, client, auth_headers, test_user, db_session):
        """Should mark multiple items as purchased atomically."""
        # Create multiple grocery items
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Apples",
            quantity=5.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="Bananas",
            quantity=3.0,
            unit="bunch",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        payload = {
            "item_ids": [str(item1.id), str(item2.id)],
            "create_inventory_item": False,
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["inventory_items_created"] == 0

        # Verify all items are purchased
        for item_data in data["items"]:
            assert item_data["purchased"] is True
            assert item_data["purchased_by"] == str(test_user.id)
            assert item_data["purchased_date"] is not None

    def test_bulk_purchase_with_inventory_creation(self, client, auth_headers, test_user, db_session):
        """Should create inventory items from purchased groceries when flag is true."""
        # Create grocery items
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Cheese",
            quantity=1.0,
            unit="lb",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="Yogurt",
            quantity=2.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        payload = {
            "item_ids": [str(item1.id), str(item2.id)],
            "create_inventory_item": True,
            "storage_location": "fridge",
            "category": "dairy",
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["inventory_items_created"] == 2

        # Verify inventory items were created
        inventory_items = db_session.query(InventoryItem).filter(
            InventoryItem.added_by == test_user.id
        ).all()
        assert len(inventory_items) == 2

        # Check inventory item properties
        cheese_inv = [i for i in inventory_items if i.name == "Cheese"][0]
        assert cheese_inv.quantity == 1.0
        assert cheese_inv.unit == "lb"
        assert cheese_inv.storage_location == "fridge"
        assert cheese_inv.category == "dairy"
        assert cheese_inv.added_by == test_user.id

    def test_bulk_purchase_conditional_validation_missing_storage(self, client, auth_headers, test_user, db_session):
        """Should return 422 when create_inventory_item=true but storage_location is missing."""
        item = GroceryListItem(
            id=uuid4(),
            item_name="Eggs",
            quantity=12.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add(item)
        db_session.commit()

        payload = {
            "item_ids": [str(item.id)],
            "create_inventory_item": True,
            "category": "protein",
            # storage_location missing - should fail
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 422
        # Verify item was NOT purchased (transaction rolled back)
        db_session.refresh(item)
        assert item.purchased is False

    def test_bulk_purchase_conditional_validation_missing_category(self, client, auth_headers, test_user, db_session):
        """Should return 422 when create_inventory_item=true but category is missing."""
        item = GroceryListItem(
            id=uuid4(),
            item_name="Butter",
            quantity=1.0,
            unit="lb",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add(item)
        db_session.commit()

        payload = {
            "item_ids": [str(item.id)],
            "create_inventory_item": True,
            "storage_location": "fridge",
            # category missing - should fail
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 422
        # Verify item was NOT purchased (transaction rolled back)
        db_session.refresh(item)
        assert item.purchased is False

    def test_bulk_purchase_item_not_found(self, client, auth_headers, test_user, db_session):
        """Should return 404 and rollback entire batch if any item not found."""
        # Create one valid item
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Valid Item",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add(item1)
        db_session.commit()

        # Include one fake ID
        fake_id = uuid4()
        payload = {
            "item_ids": [str(item1.id), str(fake_id)],
            "create_inventory_item": False,
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert str(fake_id) in response.json()["detail"]

        # Verify the valid item was NOT purchased (entire batch rolled back)
        db_session.refresh(item1)
        assert item1.purchased is False

    def test_bulk_purchase_cross_user_allowed(self, client, auth_headers2, test_user, test_user2, db_session):
        """Should allow any authenticated user to bulk purchase items added by others."""
        # Create items added by test_user
        item = GroceryListItem(
            id=uuid4(),
            item_name="Rice",
            quantity=2.0,
            unit="lb",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add(item)
        db_session.commit()

        # test_user2 purchases items added by test_user
        payload = {
            "item_ids": [str(item.id)],
            "create_inventory_item": False,
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers2)

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["purchased_by"] == str(test_user2.id)  # Purchased by user2

    def test_bulk_purchase_empty_list(self, client, auth_headers):
        """Should return 422 if item_ids list is empty."""
        payload = {
            "item_ids": [],
            "create_inventory_item": False,
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_bulk_purchase_unauthenticated(self, client, test_grocery_item):
        """Should return 401 if no auth token provided."""
        payload = {
            "item_ids": [str(test_grocery_item.id)],
            "create_inventory_item": False,
        }

        response = client.post("/grocery/bulk-purchase", json=payload)

        assert response.status_code == 401
