"""
Integration tests for authentication endpoints.

Tests cover:
- GET /auth/me: unauthorized access and successful profile retrieval
- PUT /auth/me: partial updates and validation errors
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

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
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")


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
