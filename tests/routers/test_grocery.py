"""
Integration tests for grocery list CRUD and purchase endpoints.

Tests cover:
- POST /grocery: create new grocery item
- GET /grocery: list items with filters (purchased, search) and pagination
- GET /grocery/{id}: get single item by ID
- PUT /grocery/{id}: update item (owner-restricted)
- DELETE /grocery/{id}: delete item (owner-restricted)
- PUT /grocery/{id}/purchase: mark single item as purchased
- PUT /grocery/{id}/unpurchase: reverse purchase
- POST /grocery/bulk-purchase: bulk purchase with optional inventory creation
- Shared/global reads (any authenticated user can read any item)
- Owner-restricted writes (only added_by user can update/delete)
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

    def test_bulk_purchase_exceeds_max_batch_size(self, client, auth_headers):
        """Should return 422 if item_ids list exceeds maximum batch size of 100."""
        # Create a list with 101 items (exceeds max_length=100)
        payload = {
            "item_ids": [str(uuid4()) for _ in range(101)],
            "create_inventory_item": False,
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_bulk_purchase_with_invalid_unit_for_inventory(self, client, auth_headers, test_user, db_session):
        """Should return 422 when grocery item has invalid unit during inventory creation."""
        # Create a grocery item with an invalid unit using SQLAlchemy Core
        # to bypass Pydantic schema validation. This simulates data corruption
        # or migration scenarios where invalid data might exist in the database.
        from sqlalchemy import insert
        from src.db.models.grocery_list import GroceryListItem as GroceryTable

        invalid_item_id = uuid4()

        # Use SQLAlchemy insert to bypass ORM validations
        stmt = insert(GroceryTable.__table__).values(
            id=invalid_item_id,
            item_name="Test Item",
            quantity=1.0,
            unit="invalid_unit",
            source="manual",
            added_by=test_user.id,
            purchased=False,
        )
        db_session.execute(stmt)
        db_session.commit()

        payload = {
            "item_ids": [str(invalid_item_id)],
            "create_inventory_item": True,
            "storage_location": "pantry",
            "category": "other",
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 422
        assert "unit 'invalid_unit' is not valid for inventory" in response.json()["detail"]
        assert "Valid units:" in response.json()["detail"]

    def test_bulk_purchase_valid_units_accepted(self, client, auth_headers, test_user, db_session):
        """Should accept all valid UnitType enum values when creating inventory items."""
        from src.db.models.inventory_item import UnitType

        # Test a sample of valid units
        test_units = ["oz", "lb", "g", "kg", "count", "cup"]
        item_ids = []

        for unit in test_units:
            item = GroceryListItem(
                id=uuid4(),
                item_name=f"Test {unit}",
                quantity=1.0,
                unit=unit,
                source=GrocerySource.manual.value,
                added_by=test_user.id,
                purchased=False,
            )
            db_session.add(item)
            item_ids.append(str(item.id))

        db_session.commit()

        payload = {
            "item_ids": item_ids,
            "create_inventory_item": True,
            "storage_location": "pantry",
            "category": "other",
        }

        response = client.post("/grocery/bulk-purchase", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["inventory_items_created"] == len(test_units)

        # Verify all inventory items were created with correct units
        inventory_items = db_session.query(InventoryItem).filter(
            InventoryItem.added_by == test_user.id
        ).all()
        assert len(inventory_items) == len(test_units)

        created_units = {item.unit for item in inventory_items}
        assert created_units == set(test_units)


class TestCreateGroceryItem:
    """Tests for POST /grocery (create new grocery item)."""

    def test_create_success(self, client, auth_headers, test_user, db_session):
        """Should create a new grocery item with added_by set to current user."""
        payload = {
            "item_name": "Apples",
            "quantity": 5.0,
            "unit": "count",
            "source": "manual",
        }

        response = client.post("/grocery", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["item_name"] == "Apples"
        assert data["quantity"] == 5.0
        assert data["unit"] == "count"
        assert data["source"] == "manual"
        assert data["added_by"] == str(test_user.id)
        assert data["purchased"] is False
        assert data["id"] is not None

        # Verify in database (convert string ID to UUID)
        from uuid import UUID
        item_id = UUID(data["id"])
        item = db_session.query(GroceryListItem).filter(
            GroceryListItem.id == item_id
        ).first()
        assert item is not None
        assert item.added_by == test_user.id

    def test_create_with_target_store(self, client, auth_headers, test_user, db_session):
        """Should create grocery item with target store."""
        from src.db.models.store import Store

        # Create a test store (Store model doesn't have address field)
        store = Store(id=uuid4(), name="Test Store Grocery")
        db_session.add(store)
        db_session.commit()

        payload = {
            "item_name": "Bananas",
            "quantity": 3.0,
            "unit": "bunch",
            "source": "manual",
            "target_store": str(store.id),
        }

        response = client.post("/grocery", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["target_store"] == str(store.id)

    def test_create_invalid_unit(self, client, auth_headers):
        """Should return 422 if unit is invalid."""
        payload = {
            "item_name": "Test Item",
            "quantity": 1.0,
            "unit": "invalid_unit",
            "source": "manual",
        }

        response = client.post("/grocery", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_invalid_source(self, client, auth_headers):
        """Should return 422 if source is invalid."""
        payload = {
            "item_name": "Test Item",
            "quantity": 1.0,
            "unit": "count",
            "source": "invalid_source",
        }

        response = client.post("/grocery", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_negative_quantity(self, client, auth_headers):
        """Should return 422 if quantity is negative."""
        payload = {
            "item_name": "Test Item",
            "quantity": -1.0,
            "unit": "count",
            "source": "manual",
        }

        response = client.post("/grocery", json=payload, headers=auth_headers)

        assert response.status_code == 422

    def test_create_unauthenticated(self, client):
        """Should return 401 if no auth token provided."""
        payload = {
            "item_name": "Test Item",
            "quantity": 1.0,
            "unit": "count",
            "source": "manual",
        }

        response = client.post("/grocery", json=payload)

        assert response.status_code == 401


class TestListGroceryItems:
    """Tests for GET /grocery (list items with filters)."""

    def test_list_default_unpurchased_only(self, client, auth_headers, test_user, db_session):
        """Should return only unpurchased items by default."""
        # Create unpurchased items
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Milk",
            quantity=1.0,
            unit="gallon",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        # Create purchased item
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="Bread",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=True,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        response = client.get("/grocery", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["item_name"] == "Milk"
        assert data[0]["purchased"] is False

    def test_list_purchased_true_filter(self, client, auth_headers, test_user, db_session):
        """Should return purchased items when purchased=true."""
        # Create unpurchased item
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Milk",
            quantity=1.0,
            unit="gallon",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        # Create purchased item
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="Bread",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=True,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        response = client.get("/grocery?purchased=true", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["item_name"] == "Bread"
        assert data[0]["purchased"] is True

    def test_list_purchased_false_filter(self, client, auth_headers, test_user, db_session):
        """Should return unpurchased items when purchased=false."""
        # Create unpurchased item
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Milk",
            quantity=1.0,
            unit="gallon",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        # Create purchased item
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="Bread",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=True,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        response = client.get("/grocery?purchased=false", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["item_name"] == "Milk"

    def test_list_search_filter(self, client, auth_headers, test_user, db_session):
        """Should filter items by search term (case-insensitive partial match)."""
        # Create items with different names
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="Whole Milk",
            quantity=1.0,
            unit="gallon",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="Almond Milk",
            quantity=1.0,
            unit="quart",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        item3 = GroceryListItem(
            id=uuid4(),
            item_name="Bread",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        db_session.add_all([item1, item2, item3])
        db_session.commit()

        response = client.get("/grocery?search=milk", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        item_names = {item["item_name"] for item in data}
        assert "Whole Milk" in item_names
        assert "Almond Milk" in item_names
        assert "Bread" not in item_names

    def test_list_pagination(self, client, auth_headers, test_user, db_session):
        """Should support pagination with limit and offset."""
        # Create multiple items
        items = []
        for i in range(10):
            item = GroceryListItem(
                id=uuid4(),
                item_name=f"Item {i}",
                quantity=1.0,
                unit="count",
                source=GrocerySource.manual.value,
                added_by=test_user.id,
                purchased=False,
            )
            items.append(item)
        db_session.add_all(items)
        db_session.commit()

        # Test limit
        response = client.get("/grocery?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

        # Test offset
        response = client.get("/grocery?limit=5&offset=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    def test_list_shared_reads_cross_user(self, client, auth_headers, auth_headers2, test_user, test_user2, db_session):
        """Should return ALL items regardless of owner (shared/global reads)."""
        # Create items by different users
        item1 = GroceryListItem(
            id=uuid4(),
            item_name="User1 Item",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user.id,
            purchased=False,
        )
        item2 = GroceryListItem(
            id=uuid4(),
            item_name="User2 Item",
            quantity=1.0,
            unit="count",
            source=GrocerySource.manual.value,
            added_by=test_user2.id,
            purchased=False,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # User1 should see both items
        response = client.get("/grocery", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # User2 should also see both items
        response = client.get("/grocery", headers=auth_headers2)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_unauthenticated(self, client):
        """Should return 401 if no auth token provided."""
        response = client.get("/grocery")
        assert response.status_code == 401


class TestGetGroceryItemById:
    """Tests for GET /grocery/{id} (get single item)."""

    def test_get_success(self, client, auth_headers, test_grocery_item):
        """Should return single item by ID."""
        response = client.get(f"/grocery/{test_grocery_item.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_grocery_item.id)
        assert data["item_name"] == test_grocery_item.item_name

    def test_get_cross_user_allowed(self, client, auth_headers2, test_grocery_item):
        """Should allow any authenticated user to read any item (shared/global reads)."""
        # test_grocery_item was added by test_user, but test_user2 should be able to read it
        response = client.get(f"/grocery/{test_grocery_item.id}", headers=auth_headers2)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_grocery_item.id)

    def test_get_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.get(f"/grocery/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_unauthenticated(self, client, test_grocery_item):
        """Should return 401 if no auth token provided."""
        response = client.get(f"/grocery/{test_grocery_item.id}")
        assert response.status_code == 401


class TestUpdateGroceryItem:
    """Tests for PUT /grocery/{id} (update item - owner-restricted)."""

    def test_update_success(self, client, auth_headers, test_grocery_item, db_session):
        """Should update item when owner makes the request."""
        payload = {
            "item_name": "Updated Milk",
            "quantity": 2.0,
        }

        response = client.put(
            f"/grocery/{test_grocery_item.id}",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Updated Milk"
        assert data["quantity"] == 2.0
        assert data["unit"] == test_grocery_item.unit  # Unchanged

        # Verify in database
        db_session.refresh(test_grocery_item)
        assert test_grocery_item.item_name == "Updated Milk"
        assert test_grocery_item.quantity == 2.0

    def test_update_partial(self, client, auth_headers, test_grocery_item, db_session):
        """Should support partial updates (only provided fields updated)."""
        original_quantity = test_grocery_item.quantity

        payload = {
            "item_name": "Partially Updated",
        }

        response = client.put(
            f"/grocery/{test_grocery_item.id}",
            json=payload,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Partially Updated"
        assert data["quantity"] == original_quantity  # Unchanged

    def test_update_cross_user_forbidden(self, client, auth_headers2, test_grocery_item):
        """Should return 404 when non-owner tries to update (owner-restricted writes)."""
        # test_grocery_item was added by test_user, test_user2 should NOT be able to update it
        payload = {
            "item_name": "Hacked",
        }

        response = client.put(
            f"/grocery/{test_grocery_item.id}",
            json=payload,
            headers=auth_headers2
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        payload = {"item_name": "Test"}

        response = client.put(f"/grocery/{fake_id}", json=payload, headers=auth_headers)

        assert response.status_code == 404

    def test_update_unauthenticated(self, client, test_grocery_item):
        """Should return 401 if no auth token provided."""
        payload = {"item_name": "Test"}
        response = client.put(f"/grocery/{test_grocery_item.id}", json=payload)
        assert response.status_code == 401


class TestDeleteGroceryItem:
    """Tests for DELETE /grocery/{id} (delete item - owner-restricted)."""

    def test_delete_success(self, client, auth_headers, test_grocery_item, db_session):
        """Should delete item when owner makes the request."""
        item_id = test_grocery_item.id

        response = client.delete(f"/grocery/{item_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify item is deleted from database
        item = db_session.query(GroceryListItem).filter(
            GroceryListItem.id == item_id
        ).first()
        assert item is None

    def test_delete_cross_user_forbidden(self, client, auth_headers2, test_grocery_item, db_session):
        """Should return 404 when non-owner tries to delete (owner-restricted writes)."""
        # test_grocery_item was added by test_user, test_user2 should NOT be able to delete it
        response = client.delete(
            f"/grocery/{test_grocery_item.id}",
            headers=auth_headers2
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Verify item still exists
        db_session.refresh(test_grocery_item)
        assert test_grocery_item is not None

    def test_delete_not_found(self, client, auth_headers):
        """Should return 404 if item doesn't exist."""
        fake_id = uuid4()
        response = client.delete(f"/grocery/{fake_id}", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_unauthenticated(self, client, test_grocery_item):
        """Should return 401 if no auth token provided."""
        response = client.delete(f"/grocery/{test_grocery_item.id}")
        assert response.status_code == 401
