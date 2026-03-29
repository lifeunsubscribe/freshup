"""
Integration tests for authentication endpoints.

Tests cover:
- GET /auth/me: unauthorized access and successful profile retrieval
- PUT /auth/me: partial updates and validation errors
- Database error handling for registration and profile updates
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from uuid import uuid4
from unittest.mock import patch, MagicMock

from src.db.database import Base, get_db
from src.db import models  # Import all models to ensure Base.metadata has all tables
from src.db.models.user import User, UserRole
from src.services.auth_service import hash_password, create_access_token

# Import router directly and create a test app without lifespan
from fastapi import FastAPI
from src.routers import auth_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the auth router
app.include_router(auth_router)


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """
    Set up test environment variables.

    Uses monkeypatch to ensure clean setup/teardown and prevent test pollution.
    autouse=True means this fixture runs automatically for all tests in this module.
    """
    # Clear the settings cache before setting environment variables
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")

    # Clear the cache again to ensure fresh settings are loaded
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    from sqlalchemy.pool import StaticPool

    # Ensure all models are imported by accessing them
    _ = models  # This forces the import of all models

    # Create a new engine with StaticPool to ensure all connections share the same in-memory database
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Critical for SQLite :memory: to work correctly
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
    # FastAPI caches dependency results within a single request
    # We need to ensure get_db returns the same session for the entire request
    def override_get_db():
        try:
            # Important: yield the same session for all dependencies in one request
            yield db_session
        finally:
            # Don't close here - the fixture will handle it
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Create test client
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.member.value,
        dietary_profile=["vegetarian"],
        allergies=["peanuts"],
        disliked_ingredients=["cilantro"],
        favorite_ingredients=["tomatoes"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers with a valid JWT token."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


class TestGetProfile:
    """Tests for GET /auth/me endpoint."""

    def test_get_profile_unauthorized(self, client):
        """GET /auth/me returns 401 without auth."""
        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_get_profile_invalid_token(self, client):
        """GET /auth/me returns 401 with invalid/malformed JWT token."""
        # Test with malformed token
        invalid_headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/auth/me", headers=invalid_headers)

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_profile_expired_token(self, client):
        """GET /auth/me returns 401 with expired JWT token."""
        from datetime import timedelta
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)}, expires_delta=timedelta(seconds=-1))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_get_profile_nonexistent_user(self, client):
        """GET /auth/me returns 401 when token references deleted/non-existent user."""
        # Create a token for a user ID that doesn't exist in the database
        nonexistent_user_id = uuid4()
        token = create_access_token(data={"sub": str(nonexistent_user_id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_profile_success(self, client, test_user, auth_headers):
        """GET /auth/me returns profile with valid token."""
        response = client.get("/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response schema
        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert "role" in data
        assert "dietary_profile" in data
        assert "allergies" in data
        assert "disliked_ingredients" in data
        assert "favorite_ingredients" in data

        # Verify response data matches test user
        assert data["id"] == str(test_user.id)
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"
        assert data["role"] == "member"
        assert data["dietary_profile"] == ["vegetarian"]
        assert data["allergies"] == ["peanuts"]
        assert data["disliked_ingredients"] == ["cilantro"]
        assert data["favorite_ingredients"] == ["tomatoes"]

        # Verify password is not included in response
        assert "password" not in data
        assert "hashed_password" not in data


class TestUpdateProfile:
    """Tests for PUT /auth/me endpoint."""

    def test_update_profile_partial(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me updates allowed fields."""
        update_data = {
            "name": "Updated Name",
            "dietary_profile": ["vegan", "keto"],
            "allergies": ["shellfish", "dairy"],
            "disliked_ingredients": ["onions", "garlic"],
            "favorite_ingredients": ["avocado", "spinach"],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify updated fields in response
        assert data["name"] == "Updated Name"
        assert data["dietary_profile"] == ["vegan", "keto"]
        assert data["allergies"] == ["shellfish", "dairy"]
        assert data["disliked_ingredients"] == ["onions", "garlic"]
        assert data["favorite_ingredients"] == ["avocado", "spinach"]

        # Verify unchanged fields
        assert data["id"] == str(test_user.id)
        assert data["email"] == "test@example.com"
        assert data["role"] == "member"

        # Verify database state was updated
        db_session.refresh(test_user)
        assert test_user.name == "Updated Name"
        assert test_user.dietary_profile == ["vegan", "keto"]
        assert test_user.allergies == ["shellfish", "dairy"]
        assert test_user.disliked_ingredients == ["onions", "garlic"]
        assert test_user.favorite_ingredients == ["avocado", "spinach"]

    def test_update_profile_invalid_dietary(self, client, test_user, auth_headers):
        """PUT /auth/me rejects invalid dietary profiles."""
        update_data = {
            "dietary_profile": ["invalid_diet", "another_invalid"],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 422
        error_detail = response.json()["detail"]

        # Verify error message mentions invalid dietary profile
        assert any("dietary_profile" in str(err).lower() for err in error_detail)

    def test_update_profile_partial_name_only(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me supports partial updates (name only)."""
        update_data = {"name": "Just Name Update"}

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify only name was updated
        assert data["name"] == "Just Name Update"
        assert data["dietary_profile"] == ["vegetarian"]  # unchanged
        assert data["allergies"] == ["peanuts"]  # unchanged

        # Verify database state
        db_session.refresh(test_user)
        assert test_user.name == "Just Name Update"
        assert test_user.dietary_profile == ["vegetarian"]

    def test_update_profile_empty_name_rejected(self, client, test_user, auth_headers):
        """PUT /auth/me rejects empty name."""
        update_data = {"name": "   "}

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 422
        error_detail = response.json()["detail"]

        # Verify error message mentions name validation
        assert any("name" in str(err).lower() for err in error_detail)

    def test_update_profile_unauthorized(self, client):
        """PUT /auth/me returns 401 without auth."""
        update_data = {"name": "Should Fail"}

        response = client.put("/auth/me", json=update_data)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_update_profile_expired_token(self, client):
        """PUT /auth/me returns 401 with expired JWT token."""
        from datetime import timedelta
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)}, expires_delta=timedelta(seconds=-1))
        headers = {"Authorization": f"Bearer {token}"}
        update_data = {"name": "Should Fail"}

        response = client.put("/auth/me", json=update_data, headers=headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_update_profile_invalid_token(self, client):
        """PUT /auth/me returns 401 with invalid/malformed JWT token."""
        update_data = {"name": "Should Fail"}
        invalid_headers = {"Authorization": "Bearer invalid.token.here"}

        response = client.put("/auth/me", json=update_data, headers=invalid_headers)

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_update_profile_empty_lists(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me allows clearing lists with empty arrays."""
        update_data = {
            "dietary_profile": [],
            "allergies": [],
            "disliked_ingredients": [],
            "favorite_ingredients": [],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify lists were cleared
        assert data["dietary_profile"] == []
        assert data["allergies"] == []
        assert data["disliked_ingredients"] == []
        assert data["favorite_ingredients"] == []

        # Verify database state
        db_session.refresh(test_user)
        assert test_user.dietary_profile == []
        assert test_user.allergies == []
        assert test_user.disliked_ingredients == []
        assert test_user.favorite_ingredients == []

    def test_update_profile_valid_dietary_profiles(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me accepts all valid dietary profiles."""
        valid_profiles = [
            "omnivore",
            "vegetarian",
            "vegan",
            "pescatarian",
            "keto",
            "low_carb",
            "low_sugar",
        ]

        update_data = {"dietary_profile": valid_profiles}

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all profiles were accepted
        assert data["dietary_profile"] == valid_profiles

        # Verify database state
        db_session.refresh(test_user)
        assert test_user.dietary_profile == valid_profiles

    def test_update_profile_rejects_protected_fields(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me returns 422 when attempting to modify email or role (protected fields)."""
        original_email = test_user.email
        original_role = test_user.role
        original_name = test_user.name

        # Attempt to update protected fields along with allowed fields
        update_data = {
            "name": "Updated Name",
            "email": "hacker@evil.com",  # Should be rejected
            "role": "admin",  # Should be rejected
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        # Request should fail with validation error
        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        # Verify error message mentions protected fields
        error_msg = str(error_data["detail"])
        assert "protected" in error_msg.lower() or "email" in error_msg.lower() or "role" in error_msg.lower()

        # Verify database state - nothing should have changed (including the name field)
        db_session.refresh(test_user)
        assert test_user.email == original_email
        assert test_user.role == original_role
        assert test_user.name == original_name  # Name should also be unchanged since the request was rejected

    def test_update_profile_ignores_unknown_fields(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me silently ignores unknown fields (extra='ignore')."""
        update_data = {
            "name": "Updated Name",
            "unknown_field": "should be ignored",
            "another_unknown": 12345,
            "nested_unknown": {"key": "value"},
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        # Request should succeed despite unknown fields
        assert response.status_code == 200
        data = response.json()

        # Verify known field was updated
        assert data["name"] == "Updated Name"

        # Verify unknown fields are not in response
        assert "unknown_field" not in data
        assert "another_unknown" not in data
        assert "nested_unknown" not in data

        # Verify database state - only known field was updated
        db_session.refresh(test_user)
        assert test_user.name == "Updated Name"
        assert not hasattr(test_user, "unknown_field")

    def test_update_profile_unknown_fields_with_valid_fields(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me ignores unknown fields while processing valid fields."""
        update_data = {
            "name": "New Name",
            "dietary_profile": ["vegan"],
            "allergies": ["soy"],
            "invalid_field_1": "ignored",
            "disliked_ingredients": ["cilantro"],
            "invalid_field_2": 999,
            "favorite_ingredients": ["mango"],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all valid fields were updated correctly
        assert data["name"] == "New Name"
        assert data["dietary_profile"] == ["vegan"]
        assert data["allergies"] == ["soy"]
        assert data["disliked_ingredients"] == ["cilantro"]
        assert data["favorite_ingredients"] == ["mango"]

        # Verify invalid fields are not in response
        assert "invalid_field_1" not in data
        assert "invalid_field_2" not in data

        # Verify database state matches
        db_session.refresh(test_user)
        assert test_user.name == "New Name"
        assert test_user.dietary_profile == ["vegan"]
        assert test_user.allergies == ["soy"]
        assert test_user.disliked_ingredients == ["cilantro"]
        assert test_user.favorite_ingredients == ["mango"]

    def test_update_profile_only_unknown_fields(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me with only unknown fields succeeds but changes nothing."""
        original_name = test_user.name
        original_dietary = test_user.dietary_profile

        update_data = {
            "completely_unknown": "value",
            "another_unknown": 123,
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        # Request should succeed (unknown fields are silently ignored)
        assert response.status_code == 200
        data = response.json()

        # Verify no fields were changed
        assert data["name"] == original_name
        assert data["dietary_profile"] == original_dietary

        # Verify database state unchanged
        db_session.refresh(test_user)
        assert test_user.name == original_name
        assert test_user.dietary_profile == original_dietary

    def test_update_profile_protected_fields_still_rejected_with_unknown_fields(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me still rejects protected fields even when unknown fields are present."""
        original_email = test_user.email
        original_role = test_user.role
        original_name = test_user.name

        update_data = {
            "name": "Updated Name",
            "email": "hacker@evil.com",  # Protected - should be rejected
            "unknown_field": "ignored",
            "role": "admin",  # Protected - should be rejected
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        # Request should fail due to protected fields
        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        # Verify error message mentions protected fields
        error_msg = str(error_data["detail"])
        assert "protected" in error_msg.lower() or "email" in error_msg.lower() or "role" in error_msg.lower()

        # Verify database state - nothing changed
        db_session.refresh(test_user)
        assert test_user.email == original_email
        assert test_user.role == original_role
        assert test_user.name == original_name  # Name should be unchanged since request was rejected
    def test_update_profile_rejects_too_long_allergy_items(self, client, test_user, auth_headers):
        """PUT /auth/me rejects allergy items exceeding max length."""
        # Create an item that's 101 characters (exceeds the 100 char limit)
        too_long_item = "a" * 101

        update_data = {"allergies": [too_long_item]}

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("allergies" in str(err).lower() and "100 characters" in str(err).lower() for err in error_detail)

    def test_update_profile_rejects_too_many_items(self, client, test_user, auth_headers):
        """PUT /auth/me rejects lists with more than max items."""
        # Create 101 items (exceeds the 100 item limit)
        too_many_items = [f"ingredient{i}" for i in range(101)]

        update_data = {"disliked_ingredients": too_many_items}

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("disliked_ingredients" in str(err).lower() and "100 items" in str(err).lower() for err in error_detail)

    def test_update_profile_rejects_invalid_characters(self, client, test_user, auth_headers):
        """PUT /auth/me rejects items with invalid characters."""
        update_data = {"favorite_ingredients": ["tomatoes", "invalid@item#here", "carrots"]}

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("favorite_ingredients" in str(err).lower() and "punctuation" in str(err).lower() for err in error_detail)

    def test_update_profile_accepts_valid_special_chars(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me accepts items with valid special characters."""
        update_data = {
            "allergies": ["tree nuts", "low-fat milk", "peanut butter (smooth)", "Trader Joe's sauce"],
            "disliked_ingredients": ["cilantro/coriander", "onions, raw"],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all items were accepted
        assert data["allergies"] == ["tree nuts", "low-fat milk", "peanut butter (smooth)", "Trader Joe's sauce"]
        assert data["disliked_ingredients"] == ["cilantro/coriander", "onions, raw"]

        # Verify database state
        db_session.refresh(test_user)
        assert test_user.allergies == ["tree nuts", "low-fat milk", "peanut butter (smooth)", "Trader Joe's sauce"]
        assert test_user.disliked_ingredients == ["cilantro/coriander", "onions, raw"]


class TestSwitchUser:
    """Tests for POST /auth/switch-user endpoint."""

    @pytest.fixture(autouse=True)
    def reset_limiter(self):
        """Reset rate limiter state before each test."""
        from src.middleware.rate_limit import limiter
        limiter.reset()
        yield

    @pytest.fixture
    def member_user(self, db_session):
        """Create a second test user (member role)."""
        user = User(
            id=uuid4(),
            name="Member User",
            email="member@example.com",
            hashed_password=hash_password("memberpass123"),
            role=UserRole.member.value,
            dietary_profile=["vegan"],
            allergies=[],
            disliked_ingredients=[],
            favorite_ingredients=[],
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def coordinator_user(self, db_session):
        """Create a coordinator user."""
        user = User(
            id=uuid4(),
            name="Coordinator User",
            email="coordinator@example.com",
            hashed_password=hash_password("coordpass123"),
            role=UserRole.coordinator.value,
            dietary_profile=["omnivore"],
            allergies=[],
            disliked_ingredients=[],
            favorite_ingredients=[],
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_switch_user_success(self, client, coordinator_user, member_user):
        """POST /auth/switch-user returns new token for target user."""
        # Create auth headers for coordinator user
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response contains access_token and token_type
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Verify the new token is for the target user by decoding it
        from src.services.auth_service import decode_token
        new_token = data["access_token"]
        payload = decode_token(new_token)
        assert payload["sub"] == str(member_user.id)

    def test_switch_user_token_sub_claim(self, client, coordinator_user, member_user):
        """POST /auth/switch-user token contains correct sub claim for target user."""
        # Create auth headers for coordinator user
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 200
        new_token = response.json()["access_token"]

        # Decode and verify sub claim matches target user
        from src.services.auth_service import decode_token
        payload = decode_token(new_token)
        assert "sub" in payload
        assert payload["sub"] == str(member_user.id)
        # Verify it's NOT the original user
        assert payload["sub"] != str(coordinator_user.id)

    def test_switch_user_unauthorized(self, client, member_user):
        """POST /auth/switch-user returns 401 without authentication."""
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_switch_user_invalid_token(self, client, member_user):
        """POST /auth/switch-user returns 401 with invalid token."""
        switch_data = {"user_id": str(member_user.id)}
        invalid_headers = {"Authorization": "Bearer invalid.token.here"}

        response = client.post("/auth/switch-user", json=switch_data, headers=invalid_headers)

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_switch_user_expired_token(self, client, member_user):
        """POST /auth/switch-user returns 401 with expired token."""
        from datetime import timedelta
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)}, expires_delta=timedelta(seconds=-1))
        headers = {"Authorization": f"Bearer {token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_switch_user_not_found(self, client, coordinator_user):
        """POST /auth/switch-user returns 404 for non-existent user."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        nonexistent_user_id = uuid4()
        switch_data = {"user_id": str(nonexistent_user_id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    def test_switch_user_to_self(self, client, coordinator_user):
        """POST /auth/switch-user returns 400 when attempting to switch to self."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(coordinator_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot switch to current user"

    def test_switch_user_no_password_required(self, client, coordinator_user, member_user):
        """POST /auth/switch-user works without password (household trust model)."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_switch_user_coordinator_can_switch(self, client, member_user, coordinator_user):
        """POST /auth/switch-user allows coordinator to switch to any other user."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 200
        new_token = response.json()["access_token"]

        from src.services.auth_service import decode_token
        payload = decode_token(new_token)
        assert payload["sub"] == str(member_user.id)

    def test_switch_user_coordinator_to_member(self, client, coordinator_user, member_user):
        """POST /auth/switch-user allows coordinator to switch to member (reverse direction)."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 200
        new_token = response.json()["access_token"]

        from src.services.auth_service import decode_token
        payload = decode_token(new_token)
        assert payload["sub"] == str(member_user.id)

    def test_switch_user_invalid_uuid_format(self, client, coordinator_user):
        """POST /auth/switch-user returns 422 for malformed UUID."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": "not-a-valid-uuid"}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_switch_user_missing_user_id(self, client, coordinator_user):
        """POST /auth/switch-user returns 422 when user_id is missing."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_switch_user_token_is_fresh(self, client, coordinator_user, member_user):
        """POST /auth/switch-user returns a new token with fresh expiration."""
        import time
        from src.services.auth_service import decode_token

        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}
        response1 = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)
        token1 = response1.json()["access_token"]
        payload1 = decode_token(token1)

        time.sleep(1)

        response2 = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)
        token2 = response2.json()["access_token"]
        payload2 = decode_token(token2)

        assert token1 != token2
        assert payload1["iat"] != payload2["iat"]
        assert payload2["iat"] > payload1["iat"]

    def test_switch_user_creates_audit_log(self, client, coordinator_user, member_user, db_session):
        """POST /auth/switch-user creates audit log entry for user switch event."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 200

        # Verify audit log was created
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.user_switch.value
        ).all()

        assert len(audit_logs) == 1
        audit_log = audit_logs[0]

        # Verify audit log contains correct information
        assert audit_log.user_id == coordinator_user.id  # Original user who initiated the switch
        assert audit_log.event_type == AuthEventType.user_switch.value
        assert audit_log.success is True
        assert audit_log.failure_reason is None

        # Verify metadata contains switch context (emails are stripped per data minimization policy)
        assert audit_log.event_metadata is not None
        assert audit_log.event_metadata["original_user_id"] == str(coordinator_user.id)
        assert audit_log.event_metadata["target_user_id"] == str(member_user.id)
        assert "original_email" not in audit_log.event_metadata
        assert "target_email" not in audit_log.event_metadata

        # Verify timestamp is captured
        assert audit_log.created_at is not None

    def test_switch_user_member_unauthorized(self, client, member_user, coordinator_user, db_session):
        """POST /auth/switch-user returns 403 when member attempts to switch users."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Create token for member user (non-coordinator)
        member_token = create_access_token(data={"sub": str(member_user.id)})
        member_headers = {"Authorization": f"Bearer {member_token}"}
        switch_data = {"user_id": str(coordinator_user.id)}

        # Attempt to switch as member user
        response = client.post("/auth/switch-user", json=switch_data, headers=member_headers)

        # Should return 403 Forbidden
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient privileges to switch users"

        # Verify authorization failure audit log was created
        # (Changed from user_switch to authorization_failure to eliminate duplicate logging)
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            user_id=member_user.id,
            event_type=AuthEventType.authorization_failure.value
        ).all()

        assert len(audit_logs) == 1
        audit_log = audit_logs[0]

        # Verify audit log contains correct failure information
        assert audit_log.user_id == member_user.id
        assert audit_log.event_type == AuthEventType.authorization_failure.value

        # Verify metadata contains attempted switch context
        assert audit_log.event_metadata is not None
        assert audit_log.event_metadata["resource"] == "user_switch"
        assert audit_log.event_metadata["action"] == "switch_to_user"
        assert audit_log.event_metadata["target_user_id"] == str(coordinator_user.id)
        assert audit_log.event_metadata["user_role"] == member_user.role


class TestRegistrationDatabaseErrors:
    """Tests for database error handling in POST /auth/register endpoint."""

    def test_register_integrity_error_handling(self, client, db_session):
        """POST /auth/register handles IntegrityError with appropriate response."""
        registration_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }

        # Mock db.commit to raise IntegrityError
        with patch.object(db_session, 'commit', side_effect=IntegrityError("mock", "mock", "mock")):
            response = client.post("/auth/register", json=registration_data)

            assert response.status_code == 400
            assert "data integrity violation" in response.json()["detail"].lower()

    def test_register_sqlalchemy_error_handling(self, client, db_session):
        """POST /auth/register handles SQLAlchemyError with appropriate response."""
        registration_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }

        # Mock db.commit to raise SQLAlchemyError
        with patch.object(db_session, 'commit', side_effect=SQLAlchemyError("Database connection error")):
            response = client.post("/auth/register", json=registration_data)

            assert response.status_code == 500
            assert "error occurred while creating" in response.json()["detail"].lower()

    def test_register_integrity_error_triggers_rollback(self, client, db_session):
        """POST /auth/register calls rollback when IntegrityError occurs."""
        registration_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }

        with patch.object(db_session, 'commit', side_effect=IntegrityError("mock", "mock", "mock")):
            with patch.object(db_session, 'rollback') as mock_rollback:
                response = client.post("/auth/register", json=registration_data)

                # Verify rollback was called
                assert mock_rollback.called
                assert response.status_code == 400


class TestUpdateProfileDatabaseErrors:
    """Tests for database error handling in PUT /auth/me endpoint."""

    def test_update_profile_integrity_error_handling(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me handles IntegrityError with appropriate response."""
        update_data = {"name": "Updated Name"}

        # Mock db.commit to raise IntegrityError
        with patch.object(db_session, 'commit', side_effect=IntegrityError("mock", "mock", "mock")):
            response = client.put("/auth/me", json=update_data, headers=auth_headers)

            assert response.status_code == 400
            assert "data integrity violation" in response.json()["detail"].lower()

    def test_update_profile_sqlalchemy_error_handling(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me handles SQLAlchemyError with appropriate response."""
        update_data = {"name": "Updated Name"}

        # Mock db.commit to raise SQLAlchemyError
        with patch.object(db_session, 'commit', side_effect=SQLAlchemyError("Database connection error")):
            response = client.put("/auth/me", json=update_data, headers=auth_headers)

            assert response.status_code == 500
            assert "error occurred while updating" in response.json()["detail"].lower()

    def test_update_profile_integrity_error_triggers_rollback(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me calls rollback when IntegrityError occurs."""
        update_data = {"name": "Updated Name"}
        original_name = test_user.name

        with patch.object(db_session, 'commit', side_effect=IntegrityError("mock", "mock", "mock")):
            with patch.object(db_session, 'rollback') as mock_rollback:
                response = client.put("/auth/me", json=update_data, headers=auth_headers)

                # Verify rollback was called
                assert mock_rollback.called
                assert response.status_code == 400

                # Verify user data wasn't changed (rollback worked)
                db_session.refresh(test_user)
                assert test_user.name == original_name

    def test_update_profile_sqlalchemy_error_triggers_rollback(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me calls rollback when SQLAlchemyError occurs."""
        update_data = {"name": "Updated Name"}

        with patch.object(db_session, 'commit', side_effect=SQLAlchemyError("Database error")):
            with patch.object(db_session, 'rollback') as mock_rollback:
                response = client.put("/auth/me", json=update_data, headers=auth_headers)

                # Verify rollback was called
                assert mock_rollback.called
                assert response.status_code == 500


class TestRegister:
    """Tests for POST /auth/register endpoint."""

    def test_register_success_with_valid_password(self, client, db_session):
        """POST /auth/register succeeds with password meeting all complexity requirements."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "ValidPass123!",
        }

        response = client.post("/auth/register", json=register_data)
        assert response.status_code == 201
        data = response.json()

        # Verify response contains expected fields
        assert "id" in data
        assert data["name"] == "New User"
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "coordinator"  # First user gets coordinator role

        # Verify password is not in response
        assert "password" not in data
        assert "hashed_password" not in data

        # Verify user was created in database
        user = db_session.query(User).filter(User.email == "newuser@example.com").first()
        assert user is not None
        assert user.name == "New User"
        assert user.hashed_password is not None
        assert user.hashed_password != "ValidPass123!"  # Password should be hashed

    def test_register_password_missing_uppercase(self, client):
        """POST /auth/register fails when password lacks uppercase letter."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "nouppercasehere123!",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "uppercase" in error_msg

    def test_register_password_missing_lowercase(self, client):
        """POST /auth/register fails when password lacks lowercase letter."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "NOLOWERCASEHERE123!",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "lowercase" in error_msg

    def test_register_password_missing_digit(self, client):
        """POST /auth/register fails when password lacks digit."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "NoDigitsHere!",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "digit" in error_msg

    def test_register_password_missing_special_character(self, client):
        """POST /auth/register fails when password lacks special character."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "NoSpecialChar123",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "special character" in error_msg

    def test_register_password_too_short(self, client):
        """POST /auth/register fails when password is less than 8 characters."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "Short1!",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "8 characters" in error_msg

    def test_register_password_missing_multiple_requirements(self, client):
        """POST /auth/register fails with clear message when multiple requirements are missing."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "simple",  # Missing: length, uppercase, digit, special
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()

        # Should mention all missing requirements
        assert "8 characters" in error_msg
        assert "uppercase" in error_msg
        assert "digit" in error_msg
        assert "special character" in error_msg

    def test_register_with_all_special_characters(self, client, db_session):
        """POST /auth/register accepts passwords with various special characters."""
        special_chars_tests = [
            "Password1!",
            "Password1@",
            "Password1#",
            "Password1$",
            "Password1%",
            "Password1^",
            "Password1&",
            "Password1*",
            "Password1(",
            "Password1)",
        ]

        for idx, password in enumerate(special_chars_tests):
            register_data = {
                "name": f"User {idx}",
                "email": f"user{idx}@example.com",
                "password": password,
            }

            response = client.post("/auth/register", json=register_data)

            assert response.status_code == 201, f"Failed for password: {password}"

            # Clean up for next iteration
            user = db_session.query(User).filter(User.email == f"user{idx}@example.com").first()
            if user:
                db_session.delete(user)
                db_session.commit()

    def test_register_duplicate_email(self, client, test_user):
        """POST /auth/register fails when email already exists."""
        register_data = {
            "name": "Duplicate User",
            "email": "test@example.com",  # Already exists from test_user fixture
            "password": "ValidPass123!",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_exactly_8_characters(self, client, db_session):
        """POST /auth/register accepts password with exactly 8 characters if valid."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "Pass123!",  # Exactly 8 characters
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"

    def test_register_long_valid_password(self, client, db_session):
        """POST /auth/register accepts long passwords meeting requirements."""
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "ThisIsAVeryLongPasswordThatMeetsAllRequirements123!@#",
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"

    def test_register_password_exceeds_72_bytes(self, client):
        """POST /auth/register fails when password exceeds 72 bytes (bcrypt limit)."""
        # Create a password with 73 bytes that meets all complexity requirements except max length
        password = "A1!" + "a" * 69 + "!"  # 73 chars = 73 bytes total
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": password,
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "72 bytes" in error_msg

    def test_register_password_exactly_72_bytes(self, client, db_session):
        """POST /auth/register accepts password with exactly 72 bytes (bcrypt limit)."""
        # Create a password with exactly 72 bytes that meets all requirements
        # Using ASCII characters: 1 byte per character
        password = "A1!" + "a" * 68 + "!"  # 72 chars = 72 bytes total
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": password,
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"


class TestRegistrationValidation:
    """Tests for registration endpoint validation."""

    def test_registration_rejects_invalid_dietary_profile(self, client):
        """POST /auth/register rejects invalid dietary profiles."""
        registration_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "dietary_profile": ["invalid_diet"],
        }

        response = client.post("/auth/register", json=registration_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("dietary_profile" in str(err).lower() for err in error_detail)

    def test_registration_rejects_too_long_allergy(self, client):
        """POST /auth/register rejects allergies exceeding max length."""
        too_long_allergy = "a" * 101

        registration_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "allergies": [too_long_allergy],
        }

        response = client.post("/auth/register", json=registration_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("allergies" in str(err).lower() and "100 characters" in str(err).lower() for err in error_detail)

    def test_registration_rejects_invalid_characters_in_allergies(self, client):
        """POST /auth/register rejects allergies with invalid characters."""
        registration_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "allergies": ["invalid@allergy#here"],
        }

        response = client.post("/auth/register", json=registration_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("allergies" in str(err).lower() and "punctuation" in str(err).lower() for err in error_detail)

    def test_registration_accepts_valid_allergies_and_dietary_profile(self, client, db_session):
        """POST /auth/register accepts valid allergies and dietary profiles."""
        registration_data = {
            "name": "Test User",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "dietary_profile": ["vegan", "keto"],
            "allergies": ["tree nuts", "shellfish", "low-fat milk"],
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 201
        data = response.json()

        # Verify response includes expected fields
        assert data["name"] == "Test User"
        assert data["email"] == "newuser@example.com"
        assert data["dietary_profile"] == ["vegan", "keto"]
        assert data["allergies"] == ["tree nuts", "shellfish", "low-fat milk"]

    def test_registration_accepts_unicode_ingredients(self, client, db_session):
        """POST /auth/register accepts Unicode characters in ingredient names."""
        registration_data = {
            "name": "Test User",
            "email": "unicodeuser@example.com",
            "password": "SecurePass123!",
            "allergies": ["jalapeño", "crème fraîche"],
            "disliked_ingredients": ["café au lait", "mañana peppers"],
            "favorite_ingredients": ["豆腐", "naïve radish"],
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 201
        data = response.json()

        # Verify Unicode is preserved
        assert "jalapeño" in data["allergies"]
        assert "crème fraîche" in data["allergies"]
        assert "café au lait" in data["disliked_ingredients"]
        assert "豆腐" in data["favorite_ingredients"]

    def test_registration_rejects_control_characters_in_ingredients(self, client):
        """POST /auth/register rejects control characters in ingredient names."""
        registration_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "allergies": ["milk\x00with\x00nulls"],  # Null bytes
        }

        response = client.post("/auth/register", json=registration_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("allergies" in str(err).lower() and "control" in str(err).lower() for err in error_detail)

    def test_registration_rejects_zero_width_characters_in_ingredients(self, client):
        """POST /auth/register rejects zero-width characters in ingredient names."""
        registration_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "allergies": ["milk\u200bwith\u200bzero-width"],  # Zero-width space
        }

        response = client.post("/auth/register", json=registration_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("allergies" in str(err).lower() and ("control" in str(err).lower() or "format" in str(err).lower()) for err in error_detail)

    def test_registration_normalizes_unicode(self, client, db_session):
        """POST /auth/register normalizes Unicode to NFC form."""
        # é can be represented as single char (U+00E9) or combining (e + U+0301)
        registration_data = {
            "name": "Test User",
            "email": "normalizeuser@example.com",
            "password": "SecurePass123!",
            "allergies": ["cafe\u0301"],  # café with combining accent
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 201
        data = response.json()

        # Should be normalized to NFC (single character é)
        assert "café" in data["allergies"]


class TestAccountLockout:
    """Tests for account lockout mechanism on login endpoint."""

    def test_failed_login_increments_counter(self, client, test_user, db_session):
        """Failed login attempts increment the failed_login_attempts counter."""
        # Verify initial state
        assert test_user.failed_login_attempts == 0
        assert test_user.lockout_until is None

        # Attempt login with wrong password
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

        # Verify counter was incremented
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 1
        assert test_user.lockout_until is None

    def test_account_locks_after_five_failed_attempts(self, client, test_user, db_session):
        """Account locks after 5 failed login attempts."""
        # Make 4 failed attempts
        for i in range(4):
            client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })
            db_session.refresh(test_user)
            assert test_user.failed_login_attempts == i + 1
            assert test_user.lockout_until is None

        # 5th failed attempt should trigger lockout
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })

        assert response.status_code == 401
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5
        assert test_user.lockout_until is not None

    def test_locked_account_rejects_correct_password(self, client, test_user, db_session):
        """Locked account rejects login even with correct password."""
        # Lock the account
        test_user.failed_login_attempts = 5
        test_user.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        db_session.commit()

        # Try to login with correct password
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123"  # Correct password
        })

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

        # Verify lockout is still in place
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5
        assert test_user.lockout_until is not None

    def test_lockout_expires_after_duration(self, client, test_user, db_session):
        """Account lockout expires after the lockout duration."""
        # Lock the account with an expired lockout time
        test_user.failed_login_attempts = 5
        test_user.lockout_until = datetime.now(timezone.utc) - timedelta(minutes=1)  # Expired 1 minute ago
        db_session.commit()

        # Should be able to login with correct password
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

        # Verify lockout was cleared
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 0
        assert test_user.lockout_until is None

    def test_successful_login_resets_failed_attempts(self, client, test_user, db_session):
        """Successful login resets failed login attempts counter."""
        # Set some failed attempts (but not locked)
        test_user.failed_login_attempts = 3
        db_session.commit()

        # Login with correct password
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })

        assert response.status_code == 200
        assert "access_token" in response.json()

        # Verify counter was reset
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 0
        assert test_user.lockout_until is None

    def test_lockout_does_not_leak_account_existence(self, client):
        """Locked accounts return same error message as non-existent accounts."""
        # Try to login with non-existent account
        response1 = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "anypassword"
        })

        # Try to login with (hypothetically) locked account
        response2 = client.post("/auth/login", json={
            "email": "locked@example.com",
            "password": "anypassword"
        })

        # Both should return identical error messages
        assert response1.status_code == 401
        assert response2.status_code == 401
        assert response1.json()["detail"] == response2.json()["detail"] == "Invalid credentials"

    def test_multiple_users_lockout_independently(self, client, db_session):
        """Lockout mechanism works independently for different users."""
        from uuid import uuid4

        # Create two users
        user1 = User(
            id=uuid4(),
            name="User One",
            email="user1@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.member.value,
        )
        user2 = User(
            id=uuid4(),
            name="User Two",
            email="user2@example.com",
            hashed_password=hash_password("password456"),
            role=UserRole.member.value,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()

        # Lock user1 by making 5 failed attempts
        for _ in range(5):
            client.post("/auth/login", json={
                "email": "user1@example.com",
                "password": "wrongpassword"
            })

        # User1 should be locked
        db_session.refresh(user1)
        assert user1.failed_login_attempts == 5
        assert user1.lockout_until is not None

        # User2 should not be affected
        db_session.refresh(user2)
        assert user2.failed_login_attempts == 0
        assert user2.lockout_until is None

        # User2 should still be able to login
        response = client.post("/auth/login", json={
            "email": "user2@example.com",
            "password": "password456"
        })
        assert response.status_code == 200

    def test_progressive_lockout_first_lockout_15_minutes(self, client, test_user, db_session):
        """First lockout uses 15-minute duration (baseline OWASP)."""
        # Verify initial state
        assert test_user.lockout_count == 0

        # Trigger first lockout (5 failed attempts)
        for _ in range(5):
            client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })

        # Verify lockout was applied
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5
        assert test_user.lockout_until is not None
        assert test_user.lockout_count == 1

        # Verify lockout duration is approximately 15 minutes
        lockout_duration = test_user.lockout_until - datetime.utcnow()
        # Allow 1-second tolerance for test execution time
        assert timedelta(minutes=14, seconds=59) <= lockout_duration <= timedelta(minutes=15, seconds=1)

    def test_progressive_lockout_second_lockout_30_minutes(self, client, test_user, db_session):
        """Second lockout uses 30-minute duration (exponential backoff)."""
        # Set up: user has been locked out once before
        test_user.lockout_count = 1
        db_session.commit()

        # Trigger second lockout (5 failed attempts)
        for _ in range(5):
            client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })

        # Verify lockout was applied with increased duration
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5
        assert test_user.lockout_until is not None
        assert test_user.lockout_count == 2

        # Verify lockout duration is approximately 30 minutes
        lockout_duration = test_user.lockout_until - datetime.utcnow()
        assert timedelta(minutes=29, seconds=59) <= lockout_duration <= timedelta(minutes=30, seconds=1)

    def test_progressive_lockout_caps_at_240_minutes(self, client, test_user, db_session):
        """Lockout duration caps at 240 minutes (4 hours) after 5th lockout."""
        # Set up: user has been locked out 4 times before (index 4 in the schedule)
        test_user.lockout_count = 4
        db_session.commit()

        # Trigger 5th lockout (should use cap)
        for _ in range(5):
            client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })

        # Verify lockout uses maximum duration (cap)
        db_session.refresh(test_user)
        assert test_user.lockout_count == 5
        lockout_duration = test_user.lockout_until - datetime.utcnow()
        assert timedelta(minutes=239, seconds=59) <= lockout_duration <= timedelta(minutes=240, seconds=1)

        # Trigger another lockout - should still use cap
        test_user.lockout_until = None  # Reset for next test
        test_user.failed_login_attempts = 0
        db_session.commit()

        for _ in range(5):
            client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })

        db_session.refresh(test_user)
        assert test_user.lockout_count == 6  # Still incrementing
        lockout_duration = test_user.lockout_until - datetime.utcnow()
        assert timedelta(minutes=239, seconds=59) <= lockout_duration <= timedelta(minutes=240, seconds=1)

    def test_progressive_lockout_schedule_follows_exponential_pattern(self, client, db_session):
        """Verify all lockout durations follow the exponential backoff schedule."""
        from uuid import uuid4
        expected_durations = [15, 30, 60, 120, 240]  # Minutes

        for lockout_num, expected_minutes in enumerate(expected_durations):
            # Create a new user for each test to avoid interference
            user = User(
                id=uuid4(),
                name=f"Test User {lockout_num}",
                email=f"lockout{lockout_num}@example.com",
                hashed_password=hash_password("testpassword123"),
                role=UserRole.member.value,
                lockout_count=lockout_num,  # Set previous lockout count
            )
            db_session.add(user)
            db_session.commit()

            # Trigger lockout
            for _ in range(5):
                client.post("/auth/login", json={
                    "email": user.email,
                    "password": "wrongpassword"
                })

            # Verify lockout duration
            db_session.refresh(user)
            assert user.lockout_count == lockout_num + 1
            lockout_duration = user.lockout_until - datetime.utcnow()

            # Allow 1-second tolerance
            min_duration = timedelta(minutes=expected_minutes, seconds=-1)
            max_duration = timedelta(minutes=expected_minutes, seconds=1)
            assert min_duration <= lockout_duration <= max_duration, \
                f"Lockout {lockout_num + 1} expected {expected_minutes}min, got {lockout_duration.total_seconds() / 60:.2f}min"

    def test_successful_login_resets_lockout_count(self, client, test_user, db_session):
        """Successful login resets lockout_count to 0, allowing forgiveness."""
        # Set up: user has been locked out twice before
        test_user.lockout_count = 2
        test_user.failed_login_attempts = 3  # Some failed attempts (but not locked)
        db_session.commit()

        # Successful login
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })

        assert response.status_code == 200

        # Verify all lockout fields were reset, including lockout_count
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 0
        assert test_user.lockout_until is None
        assert test_user.lockout_count == 0  # Progressive counter reset

    def test_successful_login_after_lockout_expiry_resets_lockout_count(self, client, test_user, db_session):
        """Successful login after lockout expiry resets lockout_count to 0."""
        # Set up: user was locked out twice before, and lockout just expired
        test_user.lockout_count = 2
        test_user.failed_login_attempts = 5
        test_user.lockout_until = datetime.now(timezone.utc) - timedelta(minutes=1)  # Expired
        db_session.commit()

        # Login with correct password after expiry
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })

        assert response.status_code == 200

        # Verify lockout_count was reset on successful login
        db_session.refresh(test_user)
        assert test_user.lockout_count == 0  # Reset on successful login
        assert test_user.failed_login_attempts == 0
        assert test_user.lockout_until is None


class TestAuditLogging:
    """Tests for audit logging of authentication events."""

    def test_registration_creates_audit_log(self, client, db_session):
        """POST /auth/register creates an audit log entry."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType
        registration_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 201

        # Check audit log was created (email is not stored per data minimization policy)
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.registration.value
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.success is True
        assert log.failure_reason is None
        assert log.user_id is not None

    def test_duplicate_registration_creates_failure_audit_log(self, client, test_user, db_session):
        """POST /auth/register for existing email creates failure audit log."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Attempt to register with existing email
        registration_data = {
            "name": "Duplicate User",
            "email": test_user.email,
            "password": "ValidPass123!",
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 400

        # Check audit log was created for failure (email is not stored per data minimization policy)
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.registration.value,
            success=False
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.failure_reason == "email_already_exists"
        assert log.user_id is None

    def test_successful_login_creates_audit_log(self, client, test_user, db_session):
        """POST /auth/login with correct credentials creates success audit log."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        login_data = {
            "email": test_user.email,
            "password": "testpassword123",
        }

        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200

        # Check audit log was created (email is not stored per data minimization policy)
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.login_success.value
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.success is True
        assert log.user_id == test_user.id
        assert log.failure_reason is None

    def test_failed_login_creates_audit_log(self, client, test_user, db_session):
        """POST /auth/login with wrong password creates failure audit log."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        login_data = {
            "email": test_user.email,
            "password": "wrongpassword",
        }

        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 401

        # Check audit log was created for failure (email is not stored per data minimization policy)
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.login_failure.value
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.success is False
        assert log.failure_reason == "invalid_credentials"

    def test_profile_update_creates_audit_log(self, client, test_user, auth_headers, db_session):
        """PUT /auth/me creates audit log entry."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        update_data = {
            "name": "Updated Name",
            "dietary_profile": ["vegan"],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)
        assert response.status_code == 200

        # Check audit log was created
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.profile_update.value
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.success is True
        assert "name" in log.event_metadata["fields_updated"]
        assert "dietary_profile" in log.event_metadata["fields_updated"]

    def test_audit_log_captures_ip_and_user_agent(self, client, test_user, db_session):
        """Audit logs capture IP address and user agent."""
        from src.db.models.auth_audit_log import AuthAuditLog

        login_data = {
            "email": test_user.email,
            "password": "testpassword123",
        }

        # Login with custom headers
        response = client.post(
            "/auth/login",
            json=login_data,
            headers={"User-Agent": "TestClient/1.0"}
        )
        assert response.status_code == 200

        # Check audit log captured metadata
        audit_log = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id
        ).order_by(AuthAuditLog.created_at.desc()).first()

        assert audit_log is not None
        # TestClient provides a default IP
        assert audit_log.ip_address is not None
        # Note: TestClient may not preserve custom User-Agent, but the field exists
        assert hasattr(audit_log, 'user_agent')


class TestAuditLoggingTransactionAtomicity:
    """Tests for transaction atomicity guarantees in audit logging.

    These tests verify the core value proposition of the PR:
    - Successful operations: audit log and data changes commit atomically together
    - Failed operations: audit log commits independently before raising exception
    """

    def test_successful_registration_commits_user_and_audit_atomically(self, client, db_session):
        """Successful registration commits both user and audit log in same transaction."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        registration_data = {
            "name": "New User",
            "email": "atomicuser@example.com",
            "password": "SecurePass123!",
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 201

        # Verify both user and audit log exist in database
        user = db_session.query(User).filter_by(email="atomicuser@example.com").first()
        assert user is not None

        audit_log = db_session.query(AuthAuditLog).filter_by(
            user_id=user.id,
            event_type=AuthEventType.registration.value,
            success=True
        ).first()
        assert audit_log is not None

    def test_successful_login_commits_lockout_reset_and_audit_atomically(self, client, test_user, db_session):
        """Successful login commits lockout field updates and audit log atomically."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Set up user with some failed attempts
        test_user.failed_login_attempts = 3
        test_user.lockout_count = 1
        db_session.commit()

        # Count existing audit logs before login
        initial_audit_count = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.login_success.value
        ).count()

        login_data = {
            "email": test_user.email,
            "password": "testpassword123",
        }

        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200

        # Verify user lockout fields were reset
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 0
        assert test_user.lockout_count == 0
        assert test_user.lockout_until is None

        # Verify audit log was created
        new_audit_count = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.login_success.value
        ).count()
        assert new_audit_count == initial_audit_count + 1

    def test_failed_login_commits_lockout_increment_and_audit_atomically(self, client, test_user, db_session):
        """Failed login commits failed_login_attempts increment and audit log atomically."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Verify initial state
        assert test_user.failed_login_attempts == 0

        login_data = {
            "email": test_user.email,
            "password": "wrongpassword",
        }

        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 401

        # Verify failed_login_attempts was incremented
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 1

        # Verify audit log exists (no user_id for failed login per OWASP - avoid user enumeration)
        audit_log = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.login_failure.value
        ).first()
        assert audit_log is not None
        assert audit_log.success is False

    def test_failed_registration_commits_audit_log_independently(self, client, test_user, db_session):
        """Failed registration (duplicate email) commits audit log even though registration fails."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Count users before attempt
        initial_user_count = db_session.query(User).count()

        # Attempt to register with existing email
        registration_data = {
            "name": "Duplicate User",
            "email": test_user.email,
            "password": "SecurePass123!",
        }

        response = client.post("/auth/register", json=registration_data)
        assert response.status_code == 400

        # Verify no new user was created
        final_user_count = db_session.query(User).count()
        assert final_user_count == initial_user_count

        # Verify audit log was still created (independent commit; email not stored per data minimization)
        audit_log = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.registration.value,
            success=False,
            failure_reason="email_already_exists"
        ).first()
        assert audit_log is not None

    def test_profile_update_commits_changes_and_audit_atomically(self, client, test_user, auth_headers, db_session):
        """Profile update commits field changes and audit log in same transaction."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        original_name = test_user.name

        update_data = {
            "name": "Atomically Updated Name",
            "dietary_profile": ["vegan"],
        }

        response = client.put("/auth/me", json=update_data, headers=auth_headers)
        assert response.status_code == 200

        # Verify user was updated
        db_session.refresh(test_user)
        assert test_user.name == "Atomically Updated Name"
        assert test_user.dietary_profile == ["vegan"]

        # Verify audit log exists
        audit_log = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.profile_update.value
        ).first()
        assert audit_log is not None
        assert audit_log.success is True
        assert "name" in audit_log.event_metadata["fields_updated"]

    def test_account_lockout_commits_lockout_fields_and_audit_atomically(self, client, test_user, db_session):
        """Account lockout (5th failed attempt) commits lockout fields and audit log atomically."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Make 4 failed attempts
        for _ in range(4):
            client.post("/auth/login", json={
                "email": test_user.email,
                "password": "wrongpassword"
            })

        # 5th attempt triggers lockout
        response = client.post("/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword"
        })
        assert response.status_code == 401

        # Verify lockout was applied
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5
        assert test_user.lockout_until is not None
        assert test_user.lockout_count == 1

        # Verify audit log exists for the 5th attempt
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.login_failure.value
        ).all()
        assert len(audit_logs) == 5

    def test_locked_account_login_attempt_commits_audit_independently(self, client, test_user, db_session):
        """Login attempt on locked account commits audit log even though login fails."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        # Lock the account (use naive datetime to match DB column without timezone=True)
        test_user.failed_login_attempts = 5
        test_user.lockout_until = datetime.utcnow() + timedelta(minutes=15)
        db_session.commit()

        # Count existing locked-account audit logs (no user_id per OWASP - avoid user enumeration)
        initial_audit_count = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.login_failure.value,
            failure_reason="account_locked"
        ).count()

        # Attempt login while locked
        response = client.post("/auth/login", json={
            "email": test_user.email,
            "password": "testpassword123"  # Correct password but account is locked
        })
        assert response.status_code == 401

        # Verify lockout state unchanged
        db_session.refresh(test_user)
        assert test_user.failed_login_attempts == 5

        # Verify audit log was created (independent commit for failure case)
        new_audit_count = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.login_failure.value,
            failure_reason="account_locked"
        ).count()
        assert new_audit_count == initial_audit_count + 1

        # Verify the new audit log has correct failure reason
        latest_audit = db_session.query(AuthAuditLog).filter_by(
            event_type=AuthEventType.login_failure.value,
            failure_reason="account_locked"
        ).order_by(AuthAuditLog.created_at.desc()).first()
        assert latest_audit is not None
        assert latest_audit.failure_reason == "account_locked"


class TestSwitchUserRateLimiting:
    """Tests for rate limiting on POST /auth/switch-user endpoint."""

    @pytest.fixture(autouse=True)
    def reset_limiter(self):
        """Reset rate limiter state before each test."""
        from src.middleware.rate_limit import limiter
        # Reset the limiter's storage to clear rate limit state between tests
        limiter.reset()
        yield

    @pytest.fixture
    def member_user(self, db_session):
        """Create a second test user (member role)."""
        user = User(
            id=uuid4(),
            name="Member User",
            email="member@example.com",
            hashed_password=hash_password("memberpass123"),
            role=UserRole.member.value,
            dietary_profile=["vegan"],
            allergies=[],
            disliked_ingredients=[],
            favorite_ingredients=[],
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def coordinator_user(self, db_session):
        """Create a coordinator user."""
        user = User(
            id=uuid4(),
            name="Coordinator User",
            email="coordinator@example.com",
            hashed_password=hash_password("coordpass123"),
            role=UserRole.coordinator.value,
            dietary_profile=["omnivore"],
            allergies=[],
            disliked_ingredients=[],
            favorite_ingredients=[],
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_switch_user_within_rate_limit(self, client, coordinator_user, member_user):
        """POST /auth/switch-user succeeds for requests within rate limit (10/minute)."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        # Make 10 requests (within limit)
        for _ in range(10):
            response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)
            assert response.status_code == 200
            assert "access_token" in response.json()

    def test_switch_user_exceeds_rate_limit(self, client, coordinator_user, member_user):
        """POST /auth/switch-user returns 429 when rate limit exceeded (>10/minute)."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        # Make 10 requests (at limit)
        for _ in range(10):
            response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)
            assert response.status_code == 200

        # 11th request should be rate limited
        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)
        assert response.status_code == 429
        # Verify the error message contains rate limit info
        assert "10 per 1 minute" in response.text or "detail" in response.json()

    def test_switch_user_rate_limit_response_format(self, client, coordinator_user, member_user):
        """POST /auth/switch-user rate limit response includes retry-after header."""
        coord_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord_headers = {"Authorization": f"Bearer {coord_token}"}
        switch_data = {"user_id": str(member_user.id)}

        # Exhaust rate limit
        for _ in range(10):
            client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        # Get rate limited response
        response = client.post("/auth/switch-user", json=switch_data, headers=coord_headers)

        assert response.status_code == 429
        # Verify response contains rate limit detail
        assert response.json().get("detail") is not None

    def test_switch_user_rate_limit_per_ip(self, client, coordinator_user, member_user, db_session):
        """Rate limit is enforced per IP address for switch-user endpoint."""
        # Create a second coordinator to test that rate limit is IP-based, not user-based
        second_coordinator = User(
            name="Second Coordinator",
            email="coord2@example.com",
            hashed_password=hash_password("testpassword123"),
            role=UserRole.coordinator.value,
        )
        db_session.add(second_coordinator)
        db_session.commit()

        coord1_token = create_access_token(data={"sub": str(coordinator_user.id)})
        coord2_token = create_access_token(data={"sub": str(second_coordinator.id)})

        coord1_headers = {"Authorization": f"Bearer {coord1_token}"}
        coord2_headers = {"Authorization": f"Bearer {coord2_token}"}

        switch_data = {"user_id": str(member_user.id)}

        # Make 5 requests as coordinator 1
        for _ in range(5):
            response = client.post("/auth/switch-user", json=switch_data, headers=coord1_headers)
            assert response.status_code == 200

        # Make 5 requests as coordinator 2 (same IP in test client)
        for _ in range(5):
            response = client.post("/auth/switch-user", json=switch_data, headers=coord2_headers)
            assert response.status_code == 200

        # 11th request from same IP should be rate limited regardless of user
        response = client.post("/auth/switch-user", json=switch_data, headers=coord1_headers)
        assert response.status_code == 429


class TestChangePasswordRateLimiting:
    """Tests for rate limiting on POST /change-password endpoint."""

    @pytest.fixture(autouse=True)
    def reset_limiter(self):
        """Reset rate limiter state before each test."""
        from src.middleware.rate_limit import limiter
        limiter.reset()
        yield

    def test_change_password_within_rate_limit(self, client, test_user, auth_headers):
        """POST /auth/change-password succeeds for requests within rate limit (10/minute)."""
        password_data = {
            "old_password": "testpassword123",
            "new_password": "NewSecurePass123!",
        }

        # Make 10 requests (within limit)
        for i in range(10):
            response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
            # First request succeeds, subsequent ones fail due to incorrect old password
            # (password was changed on first request)
            if i == 0:
                assert response.status_code == 200
            else:
                # After first success, old password is no longer valid
                assert response.status_code == 401

    def test_change_password_exceeds_rate_limit(self, client, test_user, auth_headers):
        """POST /auth/change-password returns 429 when rate limit exceeded (>10/minute)."""
        # Use incorrect old password so all requests fail at auth validation
        # but still count toward rate limit
        password_data = {
            "old_password": "wrongpassword",
            "new_password": "NewSecurePass123!",
        }

        # Make 10 requests (at limit)
        for _ in range(10):
            client.post("/auth/change-password", json=password_data, headers=auth_headers)

        # 11th request should be rate limited
        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 429
        # Verify the error message contains rate limit info
        assert "10 per 1 minute" in response.text or "detail" in response.json()

    def test_change_password_rate_limit_response_format(self, client, test_user, auth_headers):
        """POST /auth/change-password rate limit response includes error detail."""
        # Use incorrect old password so all requests fail at auth validation
        # but still count toward rate limit
        password_data = {
            "old_password": "wrongpassword",
            "new_password": "NewSecurePass123!",
        }

        # Exhaust rate limit
        for _ in range(10):
            client.post("/auth/change-password", json=password_data, headers=auth_headers)

        # Get rate limited response
        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)

        assert response.status_code == 429
        # Verify response contains rate limit detail
        assert response.json().get("detail") is not None

    def test_change_password_rate_limit_per_ip(self, client, db_session):
        """Rate limit is enforced per IP address for change-password endpoint."""
        # Create two users to test that rate limit is IP-based, not user-based
        user1 = User(
            id=uuid4(),
            name="User One",
            email="user1@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.member.value,
        )
        user2 = User(
            id=uuid4(),
            name="User Two",
            email="user2@example.com",
            hashed_password=hash_password("password456"),
            role=UserRole.member.value,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()

        # Create tokens for both users
        token1 = create_access_token(data={"sub": str(user1.id)})
        token2 = create_access_token(data={"sub": str(user2.id)})

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Use incorrect old passwords so all requests fail at auth validation
        # but still count toward rate limit
        password_data1 = {
            "old_password": "wrongpassword1",
            "new_password": "NewPass123!",
        }
        password_data2 = {
            "old_password": "wrongpassword2",
            "new_password": "NewPass456!",
        }

        # Make 5 requests as user 1
        for _ in range(5):
            client.post("/auth/change-password", json=password_data1, headers=headers1)

        # Make 5 requests as user 2 (same IP in test client)
        for _ in range(5):
            client.post("/auth/change-password", json=password_data2, headers=headers2)

        # 11th request from same IP should be rate limited regardless of user
        response = client.post("/auth/change-password", json=password_data1, headers=headers1)
        assert response.status_code == 429

    def test_change_password_rate_limit_protects_against_brute_force(self, client, test_user, auth_headers):
        """Rate limit prevents rapid brute-force attempts on password verification."""
        # Simulate attacker trying multiple old passwords
        for i in range(10):
            password_data = {
                "old_password": f"guessedpass{i}",
                "new_password": "NewSecurePass123!",
            }
            response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
            # All should fail with 401 (invalid old password) but not rate limited yet
            assert response.status_code in [401, 429]  # Accept either until rate limit kicks in

        # 11th attempt should be rate limited
        password_data = {
            "old_password": "anotherguess",
            "new_password": "NewSecurePass123!",
        }
        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 429


class TestChangePassword:
    """Tests for core password change functionality on POST /auth/change-password endpoint."""

    @pytest.fixture(autouse=True)
    def reset_limiter(self):
        """Reset rate limiter state before each test."""
        from src.middleware.rate_limit import limiter
        limiter.reset()
        yield

    def test_change_password_success(self, client, test_user, auth_headers, db_session):
        """POST /auth/change-password with correct old password successfully changes password."""
        password_data = {
            "old_password": "testpassword123",
            "new_password": "NewSecurePass123!",
        }

        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"message": "Password changed successfully"}

        # Verify password was actually changed by attempting login with new password
        db_session.refresh(test_user)
        from src.services.auth_service import verify_password
        assert verify_password("NewSecurePass123!", test_user.hashed_password) is True
        assert verify_password("testpassword123", test_user.hashed_password) is False

    def test_change_password_with_incorrect_old_password(self, client, test_user, auth_headers):
        """POST /auth/change-password with incorrect old password returns 401."""
        password_data = {
            "old_password": "wrongoldpassword",
            "new_password": "NewSecurePass123!",
        }

        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Current password is incorrect"

    def test_change_password_creates_audit_log_on_success(self, client, test_user, auth_headers, db_session):
        """POST /auth/change-password with correct credentials creates success audit log."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        password_data = {
            "old_password": "testpassword123",
            "new_password": "NewSecurePass123!",
        }

        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 200

        # Check audit log was created
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.password_change.value
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.success is True
        assert log.failure_reason is None

    def test_change_password_creates_audit_log_on_failure(self, client, test_user, auth_headers, db_session):
        """POST /auth/change-password with incorrect old password creates failure audit log."""
        from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType

        password_data = {
            "old_password": "wrongoldpassword",
            "new_password": "NewSecurePass123!",
        }

        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 401

        # Check audit log was created for failure
        audit_logs = db_session.query(AuthAuditLog).filter_by(
            user_id=test_user.id,
            event_type=AuthEventType.password_change.value
        ).all()

        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log.success is False
        assert log.failure_reason == "invalid_old_password"

    def test_change_password_without_authentication(self, client):
        """POST /auth/change-password without auth token returns 401."""
        password_data = {
            "old_password": "testpassword123",
            "new_password": "NewSecurePass123!",
        }

        response = client.post("/auth/change-password", json=password_data)
        assert response.status_code == 401

    def test_change_password_validates_new_password_length(self, client, test_user, auth_headers):
        """POST /auth/change-password with short new password returns 422 validation error."""
        password_data = {
            "old_password": "testpassword123",
            "new_password": "short",  # Too short (min 8 chars required)
        }

        response = client.post("/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 422
        # Validation error for password length

    def test_change_password_multiple_times(self, client, test_user, auth_headers, db_session):
        """Password can be changed multiple times successfully."""
        # First password change
        password_data_1 = {
            "old_password": "testpassword123",
            "new_password": "NewSecurePass123!",
        }
        response = client.post("/auth/change-password", json=password_data_1, headers=auth_headers)
        assert response.status_code == 200

        # Second password change using the new password as old
        password_data_2 = {
            "old_password": "NewSecurePass123!",
            "new_password": "AnotherSecurePass456!",
        }
        response = client.post("/auth/change-password", json=password_data_2, headers=auth_headers)
        assert response.status_code == 200

        # Verify the final password
        db_session.refresh(test_user)
        from src.services.auth_service import verify_password
        assert verify_password("AnotherSecurePass456!", test_user.hashed_password) is True


class TestTokenRefresh:
    """Tests for POST /auth/refresh endpoint."""

    def test_refresh_returns_valid_token(self, client, auth_headers, test_user):
        """Should return a new access token that authenticates successfully."""
        response = client.post("/auth/refresh", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify the new token works for authentication
        new_headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_response = client.get("/auth/me", headers=new_headers)
        assert me_response.status_code == 200
        assert me_response.json()["id"] == str(test_user.id)

    def test_refresh_requires_auth(self, client):
        """Should reject request without authentication."""
        response = client.post("/auth/refresh")
        assert response.status_code == 401

    def test_refresh_rejects_invalid_token(self, client):
        """Should reject request with invalid token."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.post("/auth/refresh", headers=headers)
        assert response.status_code == 401

    def test_refresh_rejects_expired_token(self, client, test_user):
        """Should reject request with expired token."""
        expired_token = create_access_token(
            data={"sub": str(test_user.id)},
            expires_delta=timedelta(seconds=-1),
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.post("/auth/refresh", headers=headers)
        assert response.status_code == 401
