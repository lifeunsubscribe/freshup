"""
Unit tests for generic ownership verification utilities.

This module tests the security-critical verify_ownership function that enforces
ownership checks across multiple routers. Tests cover:
- Successful ownership verification
- Entity not found scenarios
- Ownership violations (entity belongs to another user)
- Invalid ownership field handling
- Different entity types and ownership field names
"""

import pytest
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db.models.user import User, UserRole
from src.db.models.inventory_item import InventoryItem, Category, UnitType, StorageLocation
from src.utils.ownership import verify_ownership
from src.services.auth_service import hash_password


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
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
def user_alice(db_session):
    """Create a test user (Alice) for ownership tests."""
    user = User(
        id=uuid4(),
        name="Alice",
        email="alice@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_bob(db_session):
    """Create a second test user (Bob) for cross-user access tests."""
    user = User(
        id=uuid4(),
        name="Bob",
        email="bob@example.com",
        hashed_password=hash_password("password456"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def alice_inventory_item(db_session, user_alice):
    """Create an inventory item owned by Alice."""
    item = InventoryItem(
        id=uuid4(),
        name="Alice's Milk",
        quantity=1.0,
        unit=UnitType.l.value,
        category=Category.dairy.value,
        storage_location=StorageLocation.fridge.value,
        added_by=user_alice.id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def bob_inventory_item(db_session, user_bob):
    """Create an inventory item owned by Bob."""
    item = InventoryItem(
        id=uuid4(),
        name="Bob's Bread",
        quantity=2.0,
        unit=UnitType.count.value,
        category=Category.grain.value,
        storage_location=StorageLocation.pantry.value,
        added_by=user_bob.id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


class TestVerifyOwnershipSuccess:
    """Test successful ownership verification scenarios."""

    def test_verify_ownership_returns_entity_when_owner_matches(
        self, db_session, user_alice, alice_inventory_item
    ):
        """Test that verify_ownership returns the entity when user owns it."""
        result = verify_ownership(
            entity_class=InventoryItem,
            entity_id=alice_inventory_item.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            entity_name="Inventory item",
        )

        assert result is not None
        assert result.id == alice_inventory_item.id
        assert result.name == "Alice's Milk"
        assert result.added_by == user_alice.id

    def test_verify_ownership_with_custom_entity_name(
        self, db_session, user_alice, alice_inventory_item
    ):
        """Test that custom entity_name is accepted (used in error messages)."""
        result = verify_ownership(
            entity_class=InventoryItem,
            entity_id=alice_inventory_item.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            entity_name="Custom Item Name",
        )

        assert result is not None
        assert result.id == alice_inventory_item.id


class TestVerifyOwnershipNotFound:
    """Test scenarios where entity is not found."""

    def test_verify_ownership_raises_404_when_entity_not_found(
        self, db_session, user_alice
    ):
        """Test that verify_ownership raises 404 when entity doesn't exist."""
        non_existent_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=non_existent_id,
                ownership_field="added_by",
                current_user=user_alice,
                db=db_session,
                entity_name="Inventory item",
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Inventory item not found"

    def test_verify_ownership_uses_custom_entity_name_in_error(
        self, db_session, user_alice
    ):
        """Test that custom entity_name appears in error message."""
        non_existent_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=non_existent_id,
                ownership_field="added_by",
                current_user=user_alice,
                db=db_session,
                entity_name="Recipe",
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Recipe not found"


class TestVerifyOwnershipCrossUserAccess:
    """Test ownership violations when entity belongs to another user."""

    def test_verify_ownership_raises_404_when_user_not_owner(
        self, db_session, user_alice, user_bob, bob_inventory_item
    ):
        """Test that verify_ownership raises 404 when accessing another user's entity."""
        # Alice tries to access Bob's item
        with pytest.raises(HTTPException) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=bob_inventory_item.id,
                ownership_field="added_by",
                current_user=user_alice,
                db=db_session,
                entity_name="Inventory item",
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Inventory item not found"

    def test_verify_ownership_prevents_cross_user_access_both_ways(
        self, db_session, user_alice, user_bob, alice_inventory_item, bob_inventory_item
    ):
        """Test that ownership check works bidirectionally."""
        # Alice can access her own item
        alice_result = verify_ownership(
            entity_class=InventoryItem,
            entity_id=alice_inventory_item.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            entity_name="Inventory item",
        )
        assert alice_result.id == alice_inventory_item.id

        # Bob can access his own item
        bob_result = verify_ownership(
            entity_class=InventoryItem,
            entity_id=bob_inventory_item.id,
            ownership_field="added_by",
            current_user=user_bob,
            db=db_session,
            entity_name="Inventory item",
        )
        assert bob_result.id == bob_inventory_item.id

        # Alice cannot access Bob's item
        with pytest.raises(HTTPException) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=bob_inventory_item.id,
                ownership_field="added_by",
                current_user=user_alice,
                db=db_session,
                entity_name="Inventory item",
            )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

        # Bob cannot access Alice's item
        with pytest.raises(HTTPException) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=alice_inventory_item.id,
                ownership_field="added_by",
                current_user=user_bob,
                db=db_session,
                entity_name="Inventory item",
            )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestVerifyOwnershipInvalidField:
    """Test handling of invalid ownership field names."""

    def test_verify_ownership_raises_value_error_for_invalid_field(
        self, db_session, user_alice, alice_inventory_item
    ):
        """Test that verify_ownership raises ValueError when ownership_field doesn't exist."""
        with pytest.raises(ValueError) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=alice_inventory_item.id,
                ownership_field="nonexistent_field",
                current_user=user_alice,
                db=db_session,
                entity_name="Inventory item",
            )

        assert "does not have field 'nonexistent_field'" in str(exc_info.value)
        assert "InventoryItem" in str(exc_info.value)

    def test_verify_ownership_validates_field_before_query(
        self, db_session, user_alice
    ):
        """Test that field validation happens before database query."""
        # Use a non-existent entity ID with an invalid field
        # The ValueError should be raised before any 404 error
        non_existent_id = uuid4()

        with pytest.raises(ValueError) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=non_existent_id,
                ownership_field="invalid_field",
                current_user=user_alice,
                db=db_session,
                entity_name="Inventory item",
            )

        assert "does not have field 'invalid_field'" in str(exc_info.value)


class TestVerifyOwnershipDifferentFields:
    """Test that verify_ownership works with different ownership field names."""

    def test_verify_ownership_with_added_by_field(
        self, db_session, user_alice, alice_inventory_item
    ):
        """Test verify_ownership with 'added_by' field (InventoryItem uses this)."""
        result = verify_ownership(
            entity_class=InventoryItem,
            entity_id=alice_inventory_item.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            entity_name="Inventory item",
        )

        assert result is not None
        assert result.added_by == user_alice.id


class TestVerifyOwnershipEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_verify_ownership_with_default_entity_name(
        self, db_session, user_alice, alice_inventory_item
    ):
        """Test that default entity_name 'Resource' is used when not specified."""
        result = verify_ownership(
            entity_class=InventoryItem,
            entity_id=alice_inventory_item.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            # entity_name not specified, should default to "Resource"
        )

        assert result is not None

    def test_verify_ownership_default_entity_name_in_error(
        self, db_session, user_alice
    ):
        """Test that default entity_name 'Resource' appears in error when not specified."""
        non_existent_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            verify_ownership(
                entity_class=InventoryItem,
                entity_id=non_existent_id,
                ownership_field="added_by",
                current_user=user_alice,
                db=db_session,
                # entity_name not specified, should default to "Resource"
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Resource not found"

    def test_verify_ownership_multiple_items_same_user(
        self, db_session, user_alice
    ):
        """Test that verify_ownership works correctly with multiple items from same user."""
        # Create multiple items for Alice
        item1 = InventoryItem(
            id=uuid4(),
            name="Item 1",
            quantity=1.0,
            unit=UnitType.count.value,
            category=Category.other.value,
            storage_location=StorageLocation.pantry.value,
            added_by=user_alice.id,
        )
        item2 = InventoryItem(
            id=uuid4(),
            name="Item 2",
            quantity=2.0,
            unit=UnitType.count.value,
            category=Category.other.value,
            storage_location=StorageLocation.pantry.value,
            added_by=user_alice.id,
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # Verify Alice can access both items
        result1 = verify_ownership(
            entity_class=InventoryItem,
            entity_id=item1.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            entity_name="Inventory item",
        )
        assert result1.id == item1.id
        assert result1.name == "Item 1"

        result2 = verify_ownership(
            entity_class=InventoryItem,
            entity_id=item2.id,
            ownership_field="added_by",
            current_user=user_alice,
            db=db_session,
            entity_name="Inventory item",
        )
        assert result2.id == item2.id
        assert result2.name == "Item 2"
