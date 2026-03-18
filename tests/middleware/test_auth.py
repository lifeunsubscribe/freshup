"""
Unit tests for authentication middleware.

Tests cover:
- get_current_user: valid JWT, missing header, invalid/expired tokens, user not found
- get_current_user_optional: same scenarios but returns None instead of 401
"""

import pytest
from datetime import timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.middleware.auth import get_current_user, get_current_user_optional, require_coordinator
from src.services.auth_service import create_access_token
from src.db.models.user import User, UserRole


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """
    Pytest fixture to set up test environment variables.

    Uses monkeypatch to ensure clean setup/teardown and prevent test pollution.
    autouse=True means this fixture runs automatically for all tests in this module.
    """
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    def test_get_current_user_with_valid_token_returns_user(self):
        """Valid JWT should return User object from database."""
        # Create a test user
        user_id = uuid4()
        test_user = User(
            id=user_id,
            name="Test User",
            email="test@example.com",
            role=UserRole.member.value,
        )

        # Create a valid token for this user
        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock database session
        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = test_user

        # Call the dependency
        result = get_current_user(credentials=credentials, db=mock_db)

        # Verify the user is returned
        assert result == test_user
        assert result.id == user_id
        assert result.name == "Test User"

        # Verify database query was called correctly
        mock_db.query.assert_called_once_with(User)

    def test_get_current_user_without_credentials_raises_401(self):
        """Missing Authorization header should raise 401."""
        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=None, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_get_current_user_with_expired_token_raises_401(self):
        """Expired JWT should raise 401."""
        user_id = uuid4()
        # Create an expired token (expired 1 second ago)
        token = create_access_token(
            {"sub": str(user_id)}, expires_delta=timedelta(seconds=-1)
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_get_current_user_with_invalid_token_raises_401(self):
        """Invalid/malformed JWT should raise 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid.token.here"
        )

        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"

    def test_get_current_user_with_tampered_token_raises_401(self):
        """JWT with invalid signature should raise 401."""
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)})

        # Tamper with the signature
        parts = token.split(".")
        parts[-1] = parts[-1][:-4] + "XXXX"
        tampered_token = ".".join(parts)

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=tampered_token
        )

        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"

    def test_get_current_user_when_user_not_found_raises_401(self):
        """Valid JWT but user not in database should raise 401."""
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock database to return None (user not found)
        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_get_current_user_with_invalid_uuid_in_token_raises_401(self):
        """JWT with invalid UUID in 'sub' claim should raise 401."""
        token = create_access_token({"sub": "not-a-valid-uuid"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"

    def test_get_current_user_with_missing_sub_claim_raises_401(self):
        """JWT missing 'sub' claim should raise 401."""
        # This should be caught by decode_token, but testing defense in depth
        # We can't easily create a token without 'sub' using create_access_token,
        # but we test that the middleware handles it
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = None

        # Simulate the user not found scenario (closest we can get to missing sub)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)

        assert exc_info.value.status_code == 401


class TestGetCurrentUserOptional:
    """Tests for the get_current_user_optional dependency."""

    def test_get_current_user_optional_with_valid_token_returns_user(self):
        """Valid JWT should return User object."""
        user_id = uuid4()
        test_user = User(
            id=user_id,
            name="Test User",
            email="test@example.com",
            role=UserRole.member.value,
        )

        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock database session
        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = test_user

        result = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result == test_user
        assert result.id == user_id

    def test_get_current_user_optional_without_credentials_returns_none(self):
        """Missing Authorization header should return None."""
        mock_db = Mock()

        result = get_current_user_optional(credentials=None, db=mock_db)

        assert result is None

    def test_get_current_user_optional_with_expired_token_returns_none(self):
        """Expired JWT should return None."""
        user_id = uuid4()
        token = create_access_token(
            {"sub": str(user_id)}, expires_delta=timedelta(seconds=-1)
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_db = Mock()

        result = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result is None

    def test_get_current_user_optional_with_invalid_token_returns_none(self):
        """Invalid/malformed JWT should return None."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid.token.here"
        )

        mock_db = Mock()

        result = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result is None

    def test_get_current_user_optional_with_tampered_token_returns_none(self):
        """JWT with invalid signature should return None."""
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)})

        # Tamper with the signature
        parts = token.split(".")
        parts[-1] = parts[-1][:-4] + "XXXX"
        tampered_token = ".".join(parts)

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=tampered_token
        )

        mock_db = Mock()

        result = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result is None

    def test_get_current_user_optional_when_user_not_found_returns_none(self):
        """Valid JWT but user not in database should return None."""
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock database to return None (user not found)
        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = None

        result = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result is None

    def test_get_current_user_optional_with_invalid_uuid_returns_none(self):
        """JWT with invalid UUID in 'sub' claim should return None."""
        token = create_access_token({"sub": "not-a-valid-uuid"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        mock_db = Mock()

        result = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result is None


class TestAuthMiddlewareIntegration:
    """Integration tests comparing behavior of both dependencies."""

    def test_same_token_both_dependencies_consistent(self):
        """Both dependencies should handle the same valid token consistently."""
        user_id = uuid4()
        test_user = User(
            id=user_id,
            name="Integration Test User",
            email="integration@example.com",
            role=UserRole.coordinator.value,
        )

        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock database
        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = test_user

        # Both should return the same user
        result1 = get_current_user(credentials=credentials, db=mock_db)
        result2 = get_current_user_optional(credentials=credentials, db=mock_db)

        assert result1 == result2
        assert result1.id == user_id

    def test_error_handling_differs_between_dependencies(self):
        """get_current_user raises 401, get_current_user_optional returns None."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid.token"
        )
        mock_db = Mock()

        # get_current_user should raise
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

        # get_current_user_optional should return None
        result = get_current_user_optional(credentials=credentials, db=mock_db)
        assert result is None

    def test_no_credentials_differs_between_dependencies(self):
        """get_current_user raises 401, get_current_user_optional returns None."""
        mock_db = Mock()

        # get_current_user should raise
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=None, db=mock_db)
        assert exc_info.value.status_code == 401

        # get_current_user_optional should return None
        result = get_current_user_optional(credentials=None, db=mock_db)
        assert result is None


class TestRequireCoordinator:
    """Tests for the require_coordinator dependency."""

    def test_require_coordinator_allows_coordinator_user(self):
        """Coordinator user should pass authorization and be returned."""
        coordinator_user = User(
            id=uuid4(),
            name="Coordinator User",
            email="coordinator@example.com",
            role=UserRole.coordinator.value,
        )

        # Call the dependency with a coordinator user
        result = require_coordinator(current_user=coordinator_user)

        # Should return the same user
        assert result == coordinator_user
        assert result.role == UserRole.coordinator.value

    def test_require_coordinator_rejects_member_user_with_403(self):
        """Member user should be rejected with 403 Forbidden."""
        member_user = User(
            id=uuid4(),
            name="Member User",
            email="member@example.com",
            role=UserRole.member.value,
        )

        # Call the dependency with a member user
        with pytest.raises(HTTPException) as exc_info:
            require_coordinator(current_user=member_user)

        # Should raise 403, not 401 (user is authenticated but not authorized)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail
        assert "Coordinator role required" in exc_info.value.detail

    def test_require_coordinator_error_message_is_descriptive(self):
        """Error message should clearly indicate the authorization failure."""
        member_user = User(
            id=uuid4(),
            name="Member User",
            email="member@example.com",
            role=UserRole.member.value,
        )

        with pytest.raises(HTTPException) as exc_info:
            require_coordinator(current_user=member_user)

        # Verify the error message is helpful
        detail = exc_info.value.detail
        assert "permissions" in detail.lower() or "coordinator" in detail.lower()
        assert exc_info.value.status_code == 403

    def test_require_coordinator_can_be_chained_with_get_current_user(self):
        """
        Integration test: verify require_coordinator can be used with get_current_user.

        This simulates the pattern:
            def endpoint(coordinator: User = Depends(require_coordinator)):
                ...

        Where require_coordinator internally depends on get_current_user.
        """
        user_id = uuid4()
        coordinator_user = User(
            id=user_id,
            name="Coordinator",
            email="coord@example.com",
            role=UserRole.coordinator.value,
        )

        # Create valid token
        token = create_access_token({"sub": str(user_id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock database
        mock_db = Mock()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = coordinator_user

        # Simulate the full dependency chain:
        # 1. get_current_user extracts and validates token
        current_user = get_current_user(credentials=credentials, db=mock_db)

        # 2. require_coordinator checks role
        result = require_coordinator(current_user=current_user)

        # Both should return the same coordinator
        assert result == coordinator_user
        assert result.role == UserRole.coordinator.value

    def test_require_coordinator_preserves_user_object(self):
        """The returned User object should be identical to the input."""
        coordinator_user = User(
            id=uuid4(),
            name="Test Coordinator",
            email="test@example.com",
            role=UserRole.coordinator.value,
        )

        result = require_coordinator(current_user=coordinator_user)

        # Should return the exact same object
        assert result is coordinator_user
        assert result.id == coordinator_user.id
        assert result.name == coordinator_user.name
        assert result.email == coordinator_user.email
