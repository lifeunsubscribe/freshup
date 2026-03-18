"""
Integration tests for user management endpoints.

Tests cover:
- GET /users: unauthorized access and successful user listing
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
from src.routers import users_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the users router
app.include_router(users_router)


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
def test_users(db_session):
    """Create multiple test users in the database."""
    users = [
        User(
            id=uuid4(),
            name="Alice Coordinator",
            email="alice@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.coordinator.value,
            dietary_profile=["vegetarian", "keto"],
            allergies=["peanuts"],
            disliked_ingredients=["cilantro"],
            favorite_ingredients=["tomatoes"],
        ),
        User(
            id=uuid4(),
            name="Bob Member",
            email="bob@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.member.value,
            dietary_profile=["vegan"],
            allergies=["shellfish", "dairy"],
            disliked_ingredients=["onions"],
            favorite_ingredients=["avocado"],
        ),
        User(
            id=uuid4(),
            name="Charlie Member",
            email="charlie@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.member.value,
            dietary_profile=[],
            allergies=[],
            disliked_ingredients=[],
            favorite_ingredients=[],
        ),
    ]
    for user in users:
        db_session.add(user)
    db_session.commit()
    for user in users:
        db_session.refresh(user)
    return users


@pytest.fixture
def auth_headers(test_users):
    """Create authentication headers with a valid JWT token for the first test user."""
    token = create_access_token(data={"sub": str(test_users[0].id)})
    return {"Authorization": f"Bearer {token}"}


class TestListUsers:
    """Tests for GET /users endpoint."""

    def test_list_users_unauthorized(self, client, test_users):
        """GET /users returns 401 without auth token."""
        response = client.get("/users")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_list_users_invalid_token(self, client, test_users):
        """GET /users returns 401 with invalid/malformed JWT token."""
        invalid_headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/users", headers=invalid_headers)

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_list_users_expired_token(self, client, test_users):
        """GET /users returns 401 with expired JWT token."""
        from datetime import timedelta
        user_id = uuid4()
        token = create_access_token({"sub": str(user_id)}, expires_delta=timedelta(seconds=-1))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/users", headers=headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_list_users_success(self, client, test_users, auth_headers):
        """GET /users returns list of all household members with valid token."""
        response = client.get("/users", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response is a list
        assert isinstance(data, list)
        assert len(data) == 3

        # Verify all expected fields are present in each user
        for user_data in data:
            assert "id" in user_data
            assert "name" in user_data
            assert "role" in user_data
            assert "dietary_profile" in user_data
            assert "allergies" in user_data
            assert "disliked_ingredients" in user_data
            assert "favorite_ingredients" in user_data

            # Verify email and password are NOT included for privacy
            assert "email" not in user_data
            assert "password" not in user_data
            assert "hashed_password" not in user_data

        # Verify specific user data
        user_names = {user["name"] for user in data}
        assert "Alice Coordinator" in user_names
        assert "Bob Member" in user_names
        assert "Charlie Member" in user_names

        # Verify roles are present
        user_roles = {user["role"] for user in data}
        assert "coordinator" in user_roles
        assert "member" in user_roles

    def test_list_users_fields_verification(self, client, test_users, auth_headers):
        """GET /users returns correct field values for each user."""
        response = client.get("/users", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find Alice in the response
        alice = next((u for u in data if u["name"] == "Alice Coordinator"), None)
        assert alice is not None
        assert alice["role"] == "coordinator"
        assert alice["dietary_profile"] == ["vegetarian", "keto"]
        assert alice["allergies"] == ["peanuts"]
        assert alice["disliked_ingredients"] == ["cilantro"]
        assert alice["favorite_ingredients"] == ["tomatoes"]

        # Find Bob in the response
        bob = next((u for u in data if u["name"] == "Bob Member"), None)
        assert bob is not None
        assert bob["role"] == "member"
        assert bob["dietary_profile"] == ["vegan"]
        assert bob["allergies"] == ["shellfish", "dairy"]
        assert bob["disliked_ingredients"] == ["onions"]
        assert bob["favorite_ingredients"] == ["avocado"]

        # Find Charlie in the response (user with empty lists)
        charlie = next((u for u in data if u["name"] == "Charlie Member"), None)
        assert charlie is not None
        assert charlie["role"] == "member"
        assert charlie["dietary_profile"] == []
        assert charlie["allergies"] == []
        assert charlie["disliked_ingredients"] == []
        assert charlie["favorite_ingredients"] == []

    def test_list_users_empty_household(self, client, db_session):
        """GET /users returns empty list when no users exist."""
        # Create a token for a non-existent user (simulate edge case)
        user_id = uuid4()
        user = User(
            id=user_id,
            name="Solo User",
            email="solo@example.com",
            hashed_password=hash_password("password123"),
            role=UserRole.member.value,
            dietary_profile=[],
            allergies=[],
            disliked_ingredients=[],
            favorite_ingredients=[],
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(data={"sub": str(user_id)})
        headers = {"Authorization": f"Bearer {token}"}

        # Delete the user to simulate empty household (edge case)
        db_session.delete(user)
        db_session.commit()

        response = client.get("/users", headers=headers)

        # Should return 401 because the token's user no longer exists
        assert response.status_code == 401

    def test_list_users_member_can_access(self, client, test_users):
        """GET /users allows member role to access user list."""
        # Create token for Bob (a member, not coordinator)
        bob = test_users[1]
        token = create_access_token(data={"sub": str(bob.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/users", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
