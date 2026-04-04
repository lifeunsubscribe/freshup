"""
Integration tests for receipt endpoints.

Tests cover:
- POST /receipts: submit receipt text for async LLM parsing
- POST /receipts/{task_id}/confirm: confirm receipt items and create inventory
- Task validation: existence, status, ownership
- Multi-tenant isolation: users can only confirm their own tasks
- Authentication requirements
- Input validation: empty items, invalid enums, receipt text length, etc.
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4, UUID
from datetime import datetime, timezone

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.inventory_item import InventoryItem, Category, UnitType, StorageLocation
from src.db.models.processing_task import ProcessingTask, TaskStatus, TaskType
from src.services.auth_service import hash_password, create_access_token

from fastapi import FastAPI
from src.routers import receipts_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the receipts router
app.include_router(receipts_router)


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
        name="testuser",
        hashed_password=hash_password("testpassword"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    """Create another test user for multi-tenant isolation tests."""
    user = User(
        id=uuid4(),
        email="other@example.com",
        name="otheruser",
        hashed_password=hash_password("otherpassword"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate authentication headers for test user."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(other_user):
    """Generate authentication headers for other user."""
    token = create_access_token({"sub": str(other_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def completed_task(db_session, test_user):
    """Create a completed processing task for test user."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.completed.value,
        input_reference="s3://receipts/test-receipt.jpg",
        result_reference="s3://parsed/test-receipt.json",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def pending_task(db_session, test_user):
    """Create a pending processing task for test user."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.pending.value,
        input_reference="s3://receipts/test-receipt.jpg",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def other_user_task(db_session, other_user):
    """Create a completed task for other user (multi-tenant test)."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=other_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.completed.value,
        input_reference="s3://receipts/other-receipt.jpg",
        result_reference="s3://parsed/other-receipt.json",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


# --- Receipt Submission Tests ---

# --- Success Cases ---


def test_submit_receipt_success(client, db_session, test_user, auth_headers):
    """Test successful receipt submission creates ProcessingTask."""
    request_data = {
        "receipt_text": "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99\nMilk 4.59",
        "store_name": "Costco"
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert data["message"] == "Receipt submitted for processing"

    # Verify task exists in database
    # Convert string UUID from JSON response to UUID object for database query
    task_id = UUID(data["task_id"])
    task = db_session.query(ProcessingTask).filter(
        ProcessingTask.id == task_id
    ).first()
    assert task is not None
    assert task.user_id == test_user.id
    assert task.task_type == TaskType.receipt_parse.value
    assert task.status == TaskStatus.pending.value

    # Verify input_reference contains JSON with receipt_text and store_name
    input_data = json.loads(task.input_reference)
    assert input_data["receipt_text"] == request_data["receipt_text"]
    assert input_data["store_name"] == request_data["store_name"]


def test_submit_receipt_without_store_name(client, db_session, test_user, auth_headers):
    """Test receipt submission without store_name (optional field)."""
    request_data = {
        "receipt_text": "Generic Store\n04/01/2026\nBananas 3.99"
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"

    # Verify task exists with null store_name
    # Convert string UUID from JSON response to UUID object for database query
    task_id = UUID(data["task_id"])
    task = db_session.query(ProcessingTask).filter(
        ProcessingTask.id == task_id
    ).first()
    input_data = json.loads(task.input_reference)
    assert input_data["receipt_text"] == request_data["receipt_text"]
    assert input_data["store_name"] is None


# --- Error Cases: Authentication ---


def test_submit_receipt_no_auth(client):
    """Test receipt submission requires authentication."""
    request_data = {
        "receipt_text": "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99"
    }

    response = client.post(
        "/receipts",
        json=request_data,
    )

    assert response.status_code == 401


def test_submit_receipt_invalid_token(client):
    """Test receipt submission fails with invalid token."""
    request_data = {
        "receipt_text": "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99"
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


# --- Error Cases: Multi-Tenant Isolation ---


def test_submit_receipt_creates_task_for_authenticated_user_only(
    client, db_session, test_user, other_user, auth_headers
):
    """Test that submitted receipts create tasks owned by the authenticated user only.

    Multi-tenant isolation: Verify that when a user submits a receipt, the created
    task belongs to them and not to any other user in the system.
    """
    request_data = {
        "receipt_text": "TARGET\n04/01/2026\nApples 5.99\nBread 2.49",
        "store_name": "Target"
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 202
    data = response.json()
    task_id = UUID(data["task_id"])

    # Verify task exists and belongs to authenticated user (test_user)
    task = db_session.query(ProcessingTask).filter(
        ProcessingTask.id == task_id
    ).first()
    assert task is not None
    assert task.user_id == test_user.id

    # Verify task does NOT belong to other_user
    assert task.user_id != other_user.id

    # Verify other_user has no tasks
    other_user_tasks = db_session.query(ProcessingTask).filter(
        ProcessingTask.user_id == other_user.id
    ).all()
    assert len(other_user_tasks) == 0


# --- Error Cases: Validation ---


def test_submit_receipt_empty_text(client, auth_headers):
    """Test receipt submission fails when receipt_text is empty."""
    request_data = {
        "receipt_text": ""
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_submit_receipt_whitespace_only(client, auth_headers):
    """Test receipt submission fails when receipt_text is whitespace only."""
    request_data = {
        "receipt_text": "   \n\t   "
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_submit_receipt_too_short(client, auth_headers):
    """Test receipt submission fails when receipt_text is too short (< 10 chars)."""
    request_data = {
        "receipt_text": "short"
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_submit_receipt_too_long(client, auth_headers):
    """Test receipt submission fails when receipt_text exceeds max length."""
    request_data = {
        "receipt_text": "X" * 50001  # Exceeds max_length=50000
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_submit_receipt_empty_store_name(client, auth_headers):
    """Test receipt submission fails when store_name is empty string."""
    request_data = {
        "receipt_text": "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99",
        "store_name": ""
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_submit_receipt_whitespace_store_name(client, auth_headers):
    """Test receipt submission fails when store_name is whitespace only."""
    request_data = {
        "receipt_text": "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99",
        "store_name": "   "
    }

    response = client.post(
        "/receipts",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


# --- Receipt Confirmation Tests ---

# --- Success Cases ---


def test_confirm_receipt_success(client, db_session, test_user, completed_task, auth_headers):
    """Test successful receipt confirmation creates inventory items."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
            {
                "name": "Milk",
                "quantity": 1.0,
                "unit": "gallon",
                "category": "dairy",
                "storage_location": "fridge",
                "price": 3.99,
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["created_count"] == 2
    assert len(data["items"]) == 2

    # Verify first item
    item1 = data["items"][0]
    assert item1["name"] == "Bananas"
    assert item1["quantity"] == 2.0
    assert item1["unit"] == "bunch"
    assert item1["category"] == "produce"
    assert item1["storage_location"] == "pantry"
    assert item1["added_by"] == str(test_user.id)
    assert "id" in item1
    assert "date_added" in item1

    # Verify second item
    item2 = data["items"][1]
    assert item2["name"] == "Milk"
    assert item2["quantity"] == 1.0
    assert item2["unit"] == "gallon"
    assert item2["category"] == "dairy"
    assert item2["storage_location"] == "fridge"
    assert item2["price"] == 3.99
    assert item2["added_by"] == str(test_user.id)

    # Verify items exist in database
    db_items = db_session.query(InventoryItem).filter(
        InventoryItem.added_by == test_user.id
    ).all()
    assert len(db_items) == 2


def test_confirm_receipt_with_partial_override(client, db_session, test_user, completed_task, auth_headers):
    """Test that users can override specific fields from parsed receipt."""
    request_data = {
        "items": [
            {
                "name": "Organic Bananas",  # User edited name
                "quantity": 3.0,  # User edited quantity
                "unit": "bunch",
                "category": "produce",
                "storage_location": "fridge",  # User changed storage location
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["created_count"] == 1

    item = data["items"][0]
    assert item["name"] == "Organic Bananas"
    assert item["quantity"] == 3.0
    assert item["storage_location"] == "fridge"


# --- Error Cases: Task Not Found ---


def test_confirm_receipt_task_not_found(client, auth_headers):
    """Test confirmation fails when task doesn't exist."""
    fake_task_id = uuid4()
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{fake_task_id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# --- Error Cases: Task Not Completed ---


def test_confirm_receipt_task_not_completed(client, pending_task, auth_headers):
    """Test confirmation fails when task status is not 'completed'."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{pending_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "completed" in response.json()["detail"].lower()
    assert "pending" in response.json()["detail"].lower()


# --- Error Cases: Multi-Tenant Isolation ---


def test_confirm_receipt_task_owned_by_other_user(client, other_user_task, auth_headers):
    """Test users cannot confirm tasks owned by other users."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{other_user_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    # Should return 404 (not 403) to prevent information leakage
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# --- Error Cases: Authentication ---


def test_confirm_receipt_no_auth(client, completed_task):
    """Test confirmation requires authentication."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
    )

    assert response.status_code == 401


def test_confirm_receipt_invalid_token(client, completed_task):
    """Test confirmation fails with invalid token."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


# --- Error Cases: Validation ---


def test_confirm_receipt_empty_items(client, completed_task, auth_headers):
    """Test confirmation fails when items array is empty."""
    request_data = {"items": []}

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_invalid_unit(client, completed_task, auth_headers):
    """Test confirmation fails when unit is not a valid UnitType enum."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "invalid_unit",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_invalid_category(client, completed_task, auth_headers):
    """Test confirmation fails when category is not a valid Category enum."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "invalid_category",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_invalid_storage_location(client, completed_task, auth_headers):
    """Test confirmation fails when storage_location is not a valid StorageLocation enum."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "invalid_location",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_negative_quantity(client, completed_task, auth_headers):
    """Test confirmation fails when quantity is negative."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": -1.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_zero_quantity(client, completed_task, auth_headers):
    """Test confirmation fails when quantity is zero."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 0.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_negative_price(client, completed_task, auth_headers):
    """Test confirmation fails when price is negative."""
    request_data = {
        "items": [
            {
                "name": "Bananas",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
                "price": -5.99,
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_confirm_receipt_empty_name(client, completed_task, auth_headers):
    """Test confirmation fails when name is empty or whitespace."""
    request_data = {
        "items": [
            {
                "name": "   ",
                "quantity": 2.0,
                "unit": "bunch",
                "category": "produce",
                "storage_location": "pantry",
            },
        ]
    }

    response = client.post(
        f"/receipts/{completed_task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    assert response.status_code == 422
