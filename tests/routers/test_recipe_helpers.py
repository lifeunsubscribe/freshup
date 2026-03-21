"""
Unit tests for recipe_helpers module.

Tests cover:
- verify_recipe_ownership: Basic ownership verification
- verify_recipe_ownership_with_system_check: Enhanced verification with system recipe protection
- Error cases: missing recipes, wrong owner, system recipes
- Security: prevents leaking recipe existence through different error codes
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.services.auth_service import hash_password
from src.routers.recipe_helpers import (
    verify_recipe_ownership,
    verify_recipe_ownership_with_system_check,
)


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
def user_recipe(db_session, test_user):
    """Create a recipe owned by test_user."""
    recipe = Recipe(
        id=uuid4(),
        name="User's Recipe",
        source_type="manual",
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def user2_recipe(db_session, test_user2):
    """Create a recipe owned by test_user2."""
    recipe = Recipe(
        id=uuid4(),
        name="User 2's Recipe",
        source_type="manual",
        created_by=test_user2.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def system_recipe(db_session):
    """Create a system recipe (created_by is NULL)."""
    recipe = Recipe(
        id=uuid4(),
        name="System Recipe",
        source_type="manual",
        created_by=None,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


class TestVerifyRecipeOwnership:
    """Test verify_recipe_ownership function."""

    def test_verify_ownership_success(self, db_session, test_user, user_recipe):
        """Test successful ownership verification."""
        result = verify_recipe_ownership(user_recipe.id, test_user, db_session)

        assert result is not None
        assert result.id == user_recipe.id
        assert result.created_by == test_user.id

    def test_verify_ownership_recipe_not_found(self, db_session, test_user):
        """Test verification fails when recipe doesn't exist."""
        non_existent_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership(non_existent_id, test_user, db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"

    def test_verify_ownership_wrong_owner(self, db_session, test_user, test_user2, user2_recipe):
        """Test verification fails when recipe belongs to another user."""
        # test_user tries to access user2_recipe
        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership(user2_recipe.id, test_user, db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"

    def test_verify_ownership_system_recipe_returns_404(self, db_session, test_user, system_recipe):
        """Test that system recipes return 404 (not accessible, no owner match)."""
        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership(system_recipe.id, test_user, db_session)

        # System recipe has created_by=NULL, so ownership filter fails -> 404
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"

    def test_verify_ownership_consistent_error_for_security(self, db_session, test_user, test_user2, user2_recipe):
        """Test that wrong owner and non-existent recipes return same error (prevents info leak)."""
        non_existent_id = uuid4()

        # Get error for non-existent recipe
        with pytest.raises(HTTPException) as exc_info_1:
            verify_recipe_ownership(non_existent_id, test_user, db_session)

        # Get error for recipe owned by another user
        with pytest.raises(HTTPException) as exc_info_2:
            verify_recipe_ownership(user2_recipe.id, test_user, db_session)

        # Both should return identical errors to prevent leaking recipe existence
        assert exc_info_1.value.status_code == exc_info_2.value.status_code == 404
        assert exc_info_1.value.detail == exc_info_2.value.detail == "Recipe not found"


class TestVerifyRecipeOwnershipWithSystemCheck:
    """Test verify_recipe_ownership_with_system_check function."""

    def test_verify_with_system_check_success(self, db_session, test_user, user_recipe):
        """Test successful ownership verification with system check."""
        result = verify_recipe_ownership_with_system_check(user_recipe.id, test_user, db_session)

        assert result is not None
        assert result.id == user_recipe.id
        assert result.created_by == test_user.id

    def test_verify_with_system_check_recipe_not_found(self, db_session, test_user):
        """Test verification fails when recipe doesn't exist."""
        non_existent_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership_with_system_check(non_existent_id, test_user, db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"

    def test_verify_with_system_check_system_recipe_returns_403(self, db_session, test_user, system_recipe):
        """Test that system recipes return 403 Forbidden."""
        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership_with_system_check(system_recipe.id, test_user, db_session)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Cannot modify system recipes"

    def test_verify_with_system_check_wrong_owner(self, db_session, test_user, test_user2, user2_recipe):
        """Test verification fails when recipe belongs to another user."""
        # test_user tries to access user2_recipe
        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership_with_system_check(user2_recipe.id, test_user, db_session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"

    def test_verify_with_system_check_three_way_distinction(
        self, db_session, test_user, test_user2, user2_recipe, system_recipe
    ):
        """Test that function properly distinguishes between three error cases."""
        # Case 1: Recipe doesn't exist -> 404
        non_existent_id = uuid4()
        with pytest.raises(HTTPException) as exc_info_1:
            verify_recipe_ownership_with_system_check(non_existent_id, test_user, db_session)
        assert exc_info_1.value.status_code == 404
        assert exc_info_1.value.detail == "Recipe not found"

        # Case 2: System recipe (created_by is NULL) -> 403
        with pytest.raises(HTTPException) as exc_info_2:
            verify_recipe_ownership_with_system_check(system_recipe.id, test_user, db_session)
        assert exc_info_2.value.status_code == 403
        assert exc_info_2.value.detail == "Cannot modify system recipes"

        # Case 3: Recipe belongs to another user -> 404
        with pytest.raises(HTTPException) as exc_info_3:
            verify_recipe_ownership_with_system_check(user2_recipe.id, test_user, db_session)
        assert exc_info_3.value.status_code == 404
        assert exc_info_3.value.detail == "Recipe not found"

    def test_verify_with_system_check_security_no_leak_for_other_users(
        self, db_session, test_user, test_user2, user2_recipe
    ):
        """Test that wrong owner and non-existent recipes return same error (prevents info leak)."""
        non_existent_id = uuid4()

        # Get error for non-existent recipe
        with pytest.raises(HTTPException) as exc_info_1:
            verify_recipe_ownership_with_system_check(non_existent_id, test_user, db_session)

        # Get error for recipe owned by another user
        with pytest.raises(HTTPException) as exc_info_2:
            verify_recipe_ownership_with_system_check(user2_recipe.id, test_user, db_session)

        # Both should return identical 404 errors to prevent leaking recipe existence
        assert exc_info_1.value.status_code == exc_info_2.value.status_code == 404
        assert exc_info_1.value.detail == exc_info_2.value.detail == "Recipe not found"

    def test_verify_with_system_check_multiple_users_same_recipe(
        self, db_session, test_user, test_user2, user_recipe
    ):
        """Test that only the actual owner can access the recipe."""
        # Owner should succeed
        result = verify_recipe_ownership_with_system_check(user_recipe.id, test_user, db_session)
        assert result.id == user_recipe.id

        # Non-owner should get 404
        with pytest.raises(HTTPException) as exc_info:
            verify_recipe_ownership_with_system_check(user_recipe.id, test_user2, db_session)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"


class TestSecurityConsistency:
    """Test security-critical behavior across both functions."""

    def test_both_functions_prevent_info_leak(self, db_session, test_user, test_user2, user2_recipe):
        """Test that both functions don't leak recipe existence to unauthorized users."""
        non_existent_id = uuid4()

        # Test verify_recipe_ownership
        with pytest.raises(HTTPException) as exc_info_1a:
            verify_recipe_ownership(non_existent_id, test_user, db_session)
        with pytest.raises(HTTPException) as exc_info_1b:
            verify_recipe_ownership(user2_recipe.id, test_user, db_session)

        # Both should return same error
        assert exc_info_1a.value.status_code == exc_info_1b.value.status_code == 404
        assert exc_info_1a.value.detail == exc_info_1b.value.detail

        # Test verify_recipe_ownership_with_system_check
        with pytest.raises(HTTPException) as exc_info_2a:
            verify_recipe_ownership_with_system_check(non_existent_id, test_user, db_session)
        with pytest.raises(HTTPException) as exc_info_2b:
            verify_recipe_ownership_with_system_check(user2_recipe.id, test_user, db_session)

        # Both should return same error
        assert exc_info_2a.value.status_code == exc_info_2b.value.status_code == 404
        assert exc_info_2a.value.detail == exc_info_2b.value.detail

    def test_system_recipe_handling_difference(self, db_session, test_user, system_recipe):
        """Test that the two functions handle system recipes differently."""
        # verify_recipe_ownership: system recipe returns 404 (no owner match)
        with pytest.raises(HTTPException) as exc_info_1:
            verify_recipe_ownership(system_recipe.id, test_user, db_session)
        assert exc_info_1.value.status_code == 404

        # verify_recipe_ownership_with_system_check: system recipe returns 403
        with pytest.raises(HTTPException) as exc_info_2:
            verify_recipe_ownership_with_system_check(system_recipe.id, test_user, db_session)
        assert exc_info_2.value.status_code == 403
        assert exc_info_2.value.detail == "Cannot modify system recipes"
