"""
Integration tests for receipt endpoints.

Tests cover:
- POST /receipts: submit receipt text for async LLM parsing
- POST /receipts/upload: upload receipt image for OCR and LLM parsing
- POST /receipts/{task_id}/confirm: confirm receipt items and create inventory
- Task validation: existence, status, ownership
- Multi-tenant isolation: users can only confirm their own tasks
- Authentication requirements
- Input validation: empty items, invalid enums, receipt text length, etc.
"""

import io
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
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
from src.services.ocr_service import OCRError

from fastapi import FastAPI
from src.routers import receipts_router, tasks_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the receipts and tasks routers
app.include_router(receipts_router)
app.include_router(tasks_router)


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


# --- Receipt Image Upload Tests ---

# --- Success Cases ---


def test_upload_receipt_image_jpeg_success(client, db_session, test_user, auth_headers):
    """Test successful JPEG receipt image upload with OCR extraction."""
    # Create a mock JPEG image file
    image_content = b"fake-jpeg-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    mock_ocr_text = "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99\nMilk 4.59\nTotal: $8.58"

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        mock_ocr.return_value = mock_ocr_text
        mock_s3_client = MagicMock()
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "image uploaded" in data["message"].lower()

    # Verify task exists in database with metadata
    task_id = UUID(data["task_id"])
    task = db_session.query(ProcessingTask).filter(
        ProcessingTask.id == task_id
    ).first()
    assert task is not None
    assert task.user_id == test_user.id
    assert task.task_type == TaskType.receipt_parse.value
    assert task.status == TaskStatus.pending.value

    # Verify input_reference contains OCR text
    input_data = json.loads(task.input_reference)
    assert input_data["receipt_text"] == mock_ocr_text
    assert input_data["store_name"] is None

    # Verify task_metadata contains image source info
    assert task.task_metadata is not None
    assert task.task_metadata["source"] == "image"
    assert "minio_path" in task.task_metadata
    assert f"receipts/{test_user.id}/" in task.task_metadata["minio_path"]
    assert task.task_metadata["minio_path"].endswith(".jpg")

    # Verify OCR service was called with image bytes
    mock_ocr.assert_called_once_with(image_content)

    # Verify MinIO upload was called
    mock_s3_client.put_object.assert_called_once()
    call_args = mock_s3_client.put_object.call_args
    assert call_args.kwargs["Body"] == image_content
    assert call_args.kwargs["ContentType"] == "image/jpeg"


def test_upload_receipt_image_png_success(client, db_session, test_user, auth_headers):
    """Test successful PNG receipt image upload."""
    # Create a mock PNG image file
    image_content = b"fake-png-image-data"
    image_file = ("receipt.png", io.BytesIO(image_content), "image/png")

    mock_ocr_text = "TARGET\n04/05/2026\nApples 5.99\nBread 2.49\nTotal: $8.48"

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        mock_ocr.return_value = mock_ocr_text
        mock_s3_client = MagicMock()
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data

    # Verify task metadata has .png extension
    task_id = UUID(data["task_id"])
    task = db_session.query(ProcessingTask).filter(
        ProcessingTask.id == task_id
    ).first()
    assert task.task_metadata["minio_path"].endswith(".png")


def test_upload_receipt_image_with_store_hint(client, db_session, test_user, auth_headers):
    """Test receipt image upload with store_hint parameter."""
    image_content = b"fake-jpeg-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    mock_ocr_text = "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99"

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        mock_ocr.return_value = mock_ocr_text
        mock_s3_client = MagicMock()
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload?store_hint=Costco",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 202
    data = response.json()

    # Verify store_hint is stored in task metadata
    task_id = UUID(data["task_id"])
    task = db_session.query(ProcessingTask).filter(
        ProcessingTask.id == task_id
    ).first()
    input_data = json.loads(task.input_reference)
    assert input_data["store_name"] == "Costco"
    assert task.task_metadata["store_hint"] == "Costco"


# --- Error Cases: File Type Validation ---


def test_upload_receipt_image_invalid_file_type(client, auth_headers):
    """Test receipt upload rejects non-image file types."""
    # Create a PDF file (invalid type)
    pdf_content = b"%PDF-1.4 fake pdf content"
    pdf_file = ("document.pdf", io.BytesIO(pdf_content), "application/pdf")

    response = client.post(
        "/receipts/upload",
        files={"file": pdf_file},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "invalid file type" in response.json()["detail"].lower()
    assert "jpeg" in response.json()["detail"].lower() or "png" in response.json()["detail"].lower()


def test_upload_receipt_image_text_file(client, auth_headers):
    """Test receipt upload rejects text files."""
    text_content = b"this is a text file"
    text_file = ("receipt.txt", io.BytesIO(text_content), "text/plain")

    response = client.post(
        "/receipts/upload",
        files={"file": text_file},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "invalid file type" in response.json()["detail"].lower()


def test_upload_receipt_image_exceeds_size_limit(client, auth_headers):
    """Test receipt upload rejects files exceeding 10MB size limit."""
    # Create a file larger than 10MB (10 * 1024 * 1024 bytes)
    oversized_content = b"x" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
    oversized_file = ("receipt.jpg", io.BytesIO(oversized_content), "image/jpeg")

    response = client.post(
        "/receipts/upload",
        files={"file": oversized_file},
        headers=auth_headers,
    )

    assert response.status_code == 413
    assert "file size" in response.json()["detail"].lower()
    assert "10mb" in response.json()["detail"].lower()


# --- Error Cases: OCR Failures ---


def test_upload_receipt_image_ocr_error(client, auth_headers):
    """Test receipt upload handles OCR processing errors."""
    image_content = b"corrupt-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        mock_ocr.side_effect = OCRError("Failed to read image: corrupt data")
        mock_s3_client = MagicMock()
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 500
    assert "failed to process image" in response.json()["detail"].lower()


def test_upload_receipt_image_insufficient_ocr_text(client, auth_headers):
    """Test receipt upload rejects images with insufficient OCR text."""
    image_content = b"blank-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        # OCR returns very short text (less than 10 chars)
        mock_ocr.return_value = "ABC"
        mock_s3_client = MagicMock()
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert "unable to extract" in response.json()["detail"].lower()


def test_upload_receipt_image_empty_ocr_text(client, auth_headers):
    """Test receipt upload rejects images with empty OCR text."""
    image_content = b"blank-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        # OCR returns empty text
        mock_ocr.return_value = ""
        mock_s3_client = MagicMock()
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert "unable to extract" in response.json()["detail"].lower()


# --- Error Cases: Authentication ---


def test_upload_receipt_image_no_auth(client):
    """Test receipt image upload requires authentication."""
    image_content = b"fake-jpeg-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    response = client.post(
        "/receipts/upload",
        files={"file": image_file},
    )

    assert response.status_code == 401


def test_upload_receipt_image_invalid_token(client):
    """Test receipt image upload fails with invalid token."""
    image_content = b"fake-jpeg-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    response = client.post(
        "/receipts/upload",
        files={"file": image_file},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


# --- Error Cases: MinIO Storage ---


def test_upload_receipt_image_minio_error(client, auth_headers):
    """Test receipt upload handles MinIO storage errors."""
    image_content = b"fake-jpeg-image-data"
    image_file = ("receipt.jpg", io.BytesIO(image_content), "image/jpeg")

    with patch("src.routers.receipts.OCRService.extract_text") as mock_ocr, \
         patch("src.routers.receipts.get_storage_client") as mock_storage:

        mock_ocr.return_value = "COSTCO WHOLESALE\n04/01/2026\nBananas 3.99"
        mock_s3_client = MagicMock()
        mock_s3_client.put_object.side_effect = Exception("S3 connection failed")
        mock_storage.return_value = mock_s3_client

        response = client.post(
            "/receipts/upload",
            files={"file": image_file},
            headers=auth_headers,
        )

    assert response.status_code == 500
    assert "error occurred" in response.json()["detail"].lower()


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


# --- Receipt Task Status Polling Tests ---

# --- Success Cases ---


def test_get_task_status_pending(client, pending_task, auth_headers):
    """Test retrieving pending receipt task status."""
    response = client.get(
        f"/tasks/{pending_task.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pending_task.id)
    assert data["status"] == "pending"
    assert data["parsed_result"] is None
    assert data["error_message"] is None
    assert data["completed_at"] is None
    assert "created_at" in data


def test_get_task_status_completed_with_result(client, db_session, test_user, auth_headers):
    """Test retrieving completed receipt task with parsed result."""
    # Create a completed task with valid ReceiptParseResult JSON
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.completed.value,
        input_reference='{"receipt_text": "test", "store_name": "Costco"}',
        result_reference=json.dumps({
            "store_name": "Costco Wholesale",
            "receipt_date": "2026-04-01",
            "line_items": [
                {
                    "item_name": "Bananas",
                    "quantity": 3.0,
                    "unit_price": 0.59,
                    "total_price": 1.77,
                    "category_guess": "produce"
                },
                {
                    "item_name": "Milk 1 Gallon",
                    "quantity": 2.0,
                    "unit_price": 4.59,
                    "total_price": 9.18,
                    "category_guess": "dairy"
                }
            ]
        }),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.get(
        f"/tasks/{task.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task.id)
    assert data["status"] == "completed"
    assert data["error_message"] is None
    assert data["completed_at"] is not None

    # Verify parsed_result is present and correct
    assert data["parsed_result"] is not None
    parsed = data["parsed_result"]
    assert parsed["store_name"] == "Costco Wholesale"
    assert parsed["receipt_date"] == "2026-04-01"
    assert len(parsed["line_items"]) == 2

    # Verify first line item
    item1 = parsed["line_items"][0]
    assert item1["item_name"] == "Bananas"
    assert item1["quantity"] == 3.0
    assert item1["unit_price"] == 0.59
    assert item1["total_price"] == 1.77
    assert item1["category_guess"] == "produce"

    # Verify second line item
    item2 = parsed["line_items"][1]
    assert item2["item_name"] == "Milk 1 Gallon"
    assert item2["quantity"] == 2.0


def test_get_task_status_processing(client, db_session, test_user, auth_headers):
    """Test retrieving processing receipt task status."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.processing.value,
        input_reference='{"receipt_text": "test", "store_name": "Target"}',
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.get(
        f"/tasks/{task.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task.id)
    assert data["status"] == "processing"
    assert data["parsed_result"] is None
    assert data["error_message"] is None
    assert data["completed_at"] is None


def test_get_task_status_failed(client, db_session, test_user, auth_headers):
    """Test retrieving failed receipt task with error message."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.failed.value,
        input_reference='{"receipt_text": "test", "store_name": "Walmart"}',
        error_message="LLM service unavailable: connection timeout",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.get(
        f"/tasks/{task.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task.id)
    assert data["status"] == "failed"
    assert data["parsed_result"] is None
    assert data["error_message"] == "LLM service unavailable: connection timeout"
    assert data["completed_at"] is None


# --- Error Cases ---


def test_get_task_status_not_found(client, auth_headers):
    """Test retrieving non-existent task returns 404."""
    fake_task_id = uuid4()
    response = client.get(
        f"/tasks/{fake_task_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_task_status_no_auth(client, pending_task):
    """Test retrieving task status requires authentication."""
    response = client.get(f"/tasks/{pending_task.id}")

    assert response.status_code == 401


def test_get_task_status_invalid_token(client, pending_task):
    """Test retrieving task status fails with invalid token."""
    response = client.get(
        f"/tasks/{pending_task.id}",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_get_task_status_other_user_task(client, other_user_task, auth_headers):
    """Test users cannot access tasks owned by other users."""
    response = client.get(
        f"/tasks/{other_user_task.id}",
        headers=auth_headers,
    )

    # Should return 404 to prevent information leakage
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_task_status_invalid_result_json(client, db_session, test_user, auth_headers):
    """Test retrieving completed task with malformed JSON in result_reference returns 500."""
    # Create a completed task with invalid JSON in result_reference
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.completed.value,
        input_reference='{"receipt_text": "test", "store_name": "Costco"}',
        result_reference='{"invalid": "json", "missing_closing_brace":',  # Malformed JSON
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = client.get(
        f"/tasks/{task.id}",
        headers=auth_headers,
    )

    # Should return 500 because result_reference should always be valid for completed tasks
    assert response.status_code == 500
    assert "failed to parse" in response.json()["detail"].lower()


def test_get_task_status_wrong_task_type(client, db_session, test_user, auth_headers):
    """Test retrieving task with non-receipt task type returns 400.

    Service layer defensive programming: Even though router validates task type,
    service functions should validate their preconditions to prevent misuse
    from other calling contexts.
    """
    # Create a task with a different task type (simulating future task types)
    # We bypass the enum by setting the task_type directly to a string
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type="recipe_scrape",  # Non-receipt task type
        status=TaskStatus.completed.value,
        input_reference='{"url": "https://example.com/recipe"}',
        result_reference='{"recipe": "data"}',
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    # Router checks task type first, so we're directly calling the endpoint
    # This simulates the service being called from another context
    response = client.get(
        f"/tasks/{task.id}",
        headers=auth_headers,
    )

    # Should return 400 from service layer validation
    assert response.status_code == 400
    assert "task type" in response.json()["detail"].lower()
    assert "receipt_parse" in response.json()["detail"].lower()


def test_confirm_receipt_wrong_task_type(client, db_session, test_user, auth_headers):
    """Test confirming task with non-receipt task type returns 400.

    Service layer defensive programming: Even though router would typically
    prevent this, service functions should validate their preconditions.
    """
    # Create a completed task with a different task type
    task = ProcessingTask(
        id=uuid4(),
        user_id=test_user.id,
        task_type="recipe_scrape",  # Non-receipt task type
        status=TaskStatus.completed.value,
        input_reference='{"url": "https://example.com/recipe"}',
        result_reference='{"recipe": "data"}',
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

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
        f"/receipts/{task.id}/confirm",
        json=request_data,
        headers=auth_headers,
    )

    # Should return 400 from service layer validation
    assert response.status_code == 400
    assert "task type" in response.json()["detail"].lower()
    assert "receipt_parse" in response.json()["detail"].lower()
