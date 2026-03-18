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

    def test_switch_user_success(self, client, test_user, member_user, auth_headers):
        """POST /auth/switch-user returns new token for target user."""
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)

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

    def test_switch_user_token_sub_claim(self, client, test_user, coordinator_user, auth_headers):
        """POST /auth/switch-user token contains correct sub claim for target user."""
        switch_data = {"user_id": str(coordinator_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)

        assert response.status_code == 200
        new_token = response.json()["access_token"]

        # Decode and verify sub claim matches target user
        from src.services.auth_service import decode_token
        payload = decode_token(new_token)
        assert "sub" in payload
        assert payload["sub"] == str(coordinator_user.id)
        # Verify it's NOT the original user
        assert payload["sub"] != str(test_user.id)

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

    def test_switch_user_not_found(self, client, auth_headers):
        """POST /auth/switch-user returns 404 for non-existent user."""
        nonexistent_user_id = uuid4()
        switch_data = {"user_id": str(nonexistent_user_id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    def test_switch_user_to_self(self, client, test_user, auth_headers):
        """POST /auth/switch-user returns 400 when attempting to switch to self."""
        switch_data = {"user_id": str(test_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot switch to current user"

    def test_switch_user_no_password_required(self, client, test_user, member_user, auth_headers):
        """POST /auth/switch-user works without password (household trust model)."""
        switch_data = {"user_id": str(member_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_switch_user_any_user_can_switch(self, client, member_user, coordinator_user):
        """POST /auth/switch-user allows any authenticated user to switch to any other user."""
        member_token = create_access_token(data={"sub": str(member_user.id)})
        member_headers = {"Authorization": f"Bearer {member_token}"}
        switch_data = {"user_id": str(coordinator_user.id)}

        response = client.post("/auth/switch-user", json=switch_data, headers=member_headers)

        assert response.status_code == 200
        new_token = response.json()["access_token"]

        from src.services.auth_service import decode_token
        payload = decode_token(new_token)
        assert payload["sub"] == str(coordinator_user.id)

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

    def test_switch_user_invalid_uuid_format(self, client, auth_headers):
        """POST /auth/switch-user returns 422 for malformed UUID."""
        switch_data = {"user_id": "not-a-valid-uuid"}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_switch_user_missing_user_id(self, client, auth_headers):
        """POST /auth/switch-user returns 422 when user_id is missing."""
        switch_data = {}

        response = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_switch_user_token_is_fresh(self, client, test_user, member_user, auth_headers):
        """POST /auth/switch-user returns a new token with fresh expiration."""
        import time
        from src.services.auth_service import decode_token

        switch_data = {"user_id": str(member_user.id)}
        response1 = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)
        token1 = response1.json()["access_token"]
        payload1 = decode_token(token1)

        time.sleep(1)

        response2 = client.post("/auth/switch-user", json=switch_data, headers=auth_headers)
        token2 = response2.json()["access_token"]
        payload2 = decode_token(token2)

        assert token1 != token2
        assert payload1["iat"] != payload2["iat"]
        assert payload2["iat"] > payload1["iat"]


class TestRegistrationDatabaseErrors:
    """Tests for database error handling in POST /auth/register endpoint."""

    def test_register_integrity_error_handling(self, client, db_session):
        """POST /auth/register handles IntegrityError with appropriate response."""
        registration_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "securepassword123",
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
            "password": "securepassword123",
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
            "password": "securepassword123",
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

    def test_register_password_exceeds_128_characters(self, client):
        """POST /auth/register fails when password exceeds 128 characters."""
        # Create a password with 129 characters that meets all complexity requirements except max length
        password = "A1!" + "a" * 125 + "!"  # 129 chars total
        register_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": password,
        }

        response = client.post("/auth/register", json=register_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_msg = str(error_detail).lower()
        assert "128 characters" in error_msg

    def test_register_password_exactly_128_characters(self, client, db_session):
        """POST /auth/register accepts password with exactly 128 characters if valid."""
        # Create a password with exactly 128 characters that meets all requirements
        password = "A1!" + "a" * 124 + "!"  # 128 chars total
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
            "password": "testpassword123",
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
            "password": "testpassword123",
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
            "password": "testpassword123",
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
            "password": "testpassword123",
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