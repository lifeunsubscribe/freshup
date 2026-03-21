"""
Unit tests for inventory_helpers module.

Tests cover:
- verify_inventory_item_ownership: Basic ownership verification
- Error cases: missing items, wrong owner
- Security: prevents leaking item existence through different error codes
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.inventory_item import InventoryItem
from src.services.auth_service import hash_password
from src.routers.inventory_helpers import verify_inventory_item_ownership


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
def user_inventory_item(db_session, test_user):
    """Create an inventory item owned by test_user."""
    item = InventoryItem(
        id=uuid4(),
        name="User's Item",
        quantity=5.0,
        unit="kg",
        category="produce",
        storage_location="fridge",
        added_by=test_user.id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def user2_inventory_item(db_session, test_user2):
    """Create an inventory item owned by test_user2."""
    item = InventoryItem(
        id=uuid4(),
        name="User 2's Item",
        quantity=3.0,
        unit="kg",
        category="produce",
        storage_location="pantry",
        added_by=test_user2.id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


class TestVerifyInventoryItemOwnership:
    """Test verify_inventory_item_ownership function."""

    def test_verify_ownership_success(self, db_session, test_user, user_inventory_item):
        """Test successful ownership verification."""
        result = verify_inventory_item_ownership(user_inventory_item.id, test_user, db_session)

        assert result is not None
        assert result.id == user_inventory_item.id
        assert result.added_by == test_user.id

    def test_verify_ownership_item_not_found(self, db_session, test_user):
        """Test verification fails when item doesn't exist."""
        non_existent_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            verify_inventory_item_ownership(non_existent_id, test_user, db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Inventory item not found"

    def test_verify_ownership_wrong_owner(self, db_session, test_user, test_user2, user2_inventory_item):
        """Test verification fails when item belongs to another user."""
        # test_user tries to access user2_inventory_item
        with pytest.raises(HTTPException) as exc_info:
            verify_inventory_item_ownership(user2_inventory_item.id, test_user, db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Inventory item not found"

    def test_verify_ownership_consistent_error_for_security(self, db_session, test_user, test_user2, user2_inventory_item):
        """Test that wrong owner and non-existent items return same error (prevents info leak)."""
        non_existent_id = uuid4()

        # Get error for non-existent item
        with pytest.raises(HTTPException) as exc_info_1:
            verify_inventory_item_ownership(non_existent_id, test_user, db_session)

        # Get error for item owned by another user
        with pytest.raises(HTTPException) as exc_info_2:
            verify_inventory_item_ownership(user2_inventory_item.id, test_user, db_session)

        # Both should return identical errors to prevent leaking item existence
        assert exc_info_1.value.status_code == exc_info_2.value.status_code == 404
        assert exc_info_1.value.detail == exc_info_2.value.detail == "Inventory item not found"

    def test_verify_ownership_multiple_users_same_item(
        self, db_session, test_user, test_user2, user_inventory_item
    ):
        """Test that only the actual owner can access the item."""
        # Owner should succeed
        result = verify_inventory_item_ownership(user_inventory_item.id, test_user, db_session)
        assert result.id == user_inventory_item.id

        # Non-owner should get 404
        with pytest.raises(HTTPException) as exc_info:
            verify_inventory_item_ownership(user_inventory_item.id, test_user2, db_session)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Inventory item not found"
