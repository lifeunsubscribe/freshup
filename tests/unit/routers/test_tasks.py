"""
Unit tests for task status endpoints.

Tests cover:
- GET /tasks/{task_id}: pending, completed, failed, not found, unauthorized
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.processing_task import ProcessingTask, TaskType, TaskStatus
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import tasks_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

app.include_router(tasks_router)

# In-memory SQLite for testing
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

    _ = models

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid4(),
        name="testuser",
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers with valid JWT token."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pending_task(db_session, test_user):
    """Create a pending processing task."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.pending.value,
        input_reference="s3://bucket/receipts/test-receipt.jpg",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def completed_task(db_session, test_user):
    """Create a completed processing task with result."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.completed.value,
        input_reference="s3://bucket/receipts/completed-receipt.jpg",
        result_reference='{"store_name": "Whole Foods", "total": 45.67, "items": []}',
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def failed_task(db_session, test_user):
    """Create a failed processing task with error."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.failed.value,
        input_reference="s3://bucket/receipts/bad-receipt.jpg",
        error_message="Unable to parse receipt: image quality too low",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


class TestGetTaskStatus:
    """Tests for GET /tasks/{task_id} endpoint."""

    def test_get_pending_task(self, client, auth_headers, pending_task):
        """Test retrieving a pending task."""
        response = client.get(f"/tasks/{pending_task.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(pending_task.id)
        assert data["task_type"] == TaskType.receipt_parse.value
        assert data["status"] == TaskStatus.pending.value
        assert data["input_reference"] == pending_task.input_reference
        assert data["result_reference"] is None
        assert data["error_message"] is None
        assert data["completed_at"] is None
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_completed_task_with_result(self, client, auth_headers, completed_task):
        """Test retrieving a completed task with result."""
        response = client.get(f"/tasks/{completed_task.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(completed_task.id)
        assert data["status"] == TaskStatus.completed.value
        assert data["result_reference"] is not None
        assert data["result_reference"] == completed_task.result_reference
        assert data["error_message"] is None
        assert data["completed_at"] is not None

    def test_get_failed_task_with_error(self, client, auth_headers, failed_task):
        """Test retrieving a failed task with error message."""
        response = client.get(f"/tasks/{failed_task.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(failed_task.id)
        assert data["status"] == TaskStatus.failed.value
        assert data["error_message"] is not None
        assert data["error_message"] == failed_task.error_message
        assert data["result_reference"] is None

    def test_get_nonexistent_task(self, client, auth_headers):
        """Test retrieving a task that doesn't exist returns 404."""
        nonexistent_id = uuid4()
        response = client.get(f"/tasks/{nonexistent_id}", headers=auth_headers)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_task_unauthorized(self, client, pending_task):
        """Test accessing task without authentication returns 401."""
        response = client.get(f"/tasks/{pending_task.id}")

        assert response.status_code == 401
        data = response.json()
        assert "not authenticated" in data["detail"].lower()

    def test_get_task_invalid_token(self, client, pending_task):
        """Test accessing task with invalid token returns 401."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get(f"/tasks/{pending_task.id}", headers=headers)

        assert response.status_code == 401

    def test_get_task_with_processing_status(self, client, auth_headers, db_session, test_user):
        """Test retrieving a task that is currently processing."""
        task = ProcessingTask(
            id=uuid4(),
            user_id=test_user.id,
            task_type=TaskType.receipt_parse.value,
            status=TaskStatus.processing.value,
            input_reference="s3://bucket/receipts/processing-receipt.jpg",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.get(f"/tasks/{task.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TaskStatus.processing.value
        assert data["result_reference"] is None
        assert data["error_message"] is None
        assert data["completed_at"] is None

    def test_get_task_owned_by_another_user(self, client, db_session):
        """Test that users cannot access tasks owned by other users."""
        # Create another user
        other_user = User(
            id=uuid4(),
            name="otheruser",
            email="other@example.com",
            hashed_password=hash_password("otherpassword123"),
            role=UserRole.member.value,
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        # Create a task owned by the other user
        other_task = ProcessingTask(
            id=uuid4(),
            user_id=other_user.id,
            task_type=TaskType.receipt_parse.value,
            status=TaskStatus.completed.value,
            input_reference="s3://bucket/receipts/other-user-receipt.jpg",
            result_reference='{"store_name": "Target", "total": 100.00, "items": []}',
        )
        db_session.add(other_task)
        db_session.commit()
        db_session.refresh(other_task)

        # Create a test user with their own auth token
        test_user = User(
            id=uuid4(),
            name="testuser",
            email="test@example.com",
            hashed_password=hash_password("testpassword123"),
            role=UserRole.member.value,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Create auth headers for test user
        token = create_access_token(data={"sub": str(test_user.id)})
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Try to access the other user's task
        response = client.get(f"/tasks/{other_task.id}", headers=auth_headers)

        # Should return 404 to prevent information disclosure
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
