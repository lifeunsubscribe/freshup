"""
Unit tests for task_service.py

Tests cover:
- get_task_by_id: Returns task when user_id matches
- get_task_by_id: Returns None when user_id doesn't match
- get_task_by_id: Returns None when task_id doesn't exist
"""

import pytest
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.database import Base
from src.db import models
from src.db.models.processing_task import ProcessingTask, TaskType, TaskStatus
from src.services.task_service import get_task_by_id


# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


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
def user_id():
    """Create a test user ID."""
    return uuid4()


@pytest.fixture
def other_user_id():
    """Create another test user ID."""
    return uuid4()


@pytest.fixture
def test_task(db_session, user_id):
    """Create a test processing task."""
    task = ProcessingTask(
        id=uuid4(),
        user_id=user_id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.pending.value,
        input_reference="s3://bucket/receipts/test-receipt.jpg",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


class TestGetTaskById:
    """Tests for get_task_by_id service function."""

    def test_returns_task_when_user_id_matches(self, db_session, user_id, test_task):
        """Test that get_task_by_id returns task when user_id matches."""
        result = get_task_by_id(test_task.id, user_id, db_session)

        assert result is not None
        assert result.id == test_task.id
        assert result.user_id == user_id
        assert result.task_type == TaskType.receipt_parse.value
        assert result.status == TaskStatus.pending.value

    def test_returns_none_when_user_id_does_not_match(self, db_session, other_user_id, test_task):
        """Test that get_task_by_id returns None when user_id doesn't match."""
        # Try to get task with wrong user_id
        result = get_task_by_id(test_task.id, other_user_id, db_session)

        assert result is None

    def test_returns_none_when_task_id_does_not_exist(self, db_session, user_id):
        """Test that get_task_by_id returns None when task_id doesn't exist."""
        nonexistent_task_id = uuid4()
        result = get_task_by_id(nonexistent_task_id, user_id, db_session)

        assert result is None

    def test_multi_tenant_isolation(self, db_session, user_id, other_user_id):
        """Test that users cannot access tasks from other users."""
        # Create task for user1
        task1 = ProcessingTask(
            id=uuid4(),
            user_id=user_id,
            task_type=TaskType.receipt_parse.value,
            status=TaskStatus.completed.value,
            input_reference="s3://bucket/receipts/user1-receipt.jpg",
            result_reference='{"store_name": "Store A"}',
        )
        db_session.add(task1)

        # Create task for user2
        task2 = ProcessingTask(
            id=uuid4(),
            user_id=other_user_id,
            task_type=TaskType.receipt_parse.value,
            status=TaskStatus.completed.value,
            input_reference="s3://bucket/receipts/user2-receipt.jpg",
            result_reference='{"store_name": "Store B"}',
        )
        db_session.add(task2)
        db_session.commit()

        # User1 can access their own task
        result1 = get_task_by_id(task1.id, user_id, db_session)
        assert result1 is not None
        assert result1.id == task1.id

        # User1 cannot access user2's task
        result2 = get_task_by_id(task2.id, user_id, db_session)
        assert result2 is None

        # User2 can access their own task
        result3 = get_task_by_id(task2.id, other_user_id, db_session)
        assert result3 is not None
        assert result3.id == task2.id

        # User2 cannot access user1's task
        result4 = get_task_by_id(task1.id, other_user_id, db_session)
        assert result4 is None

    def test_task_metadata_field_is_optional(self, db_session, user_id):
        """Test that task_metadata field can be None and can store JSON data."""
        # Create task without metadata
        task_without_metadata = ProcessingTask(
            id=uuid4(),
            user_id=user_id,
            task_type=TaskType.receipt_parse.value,
            status=TaskStatus.pending.value,
            input_reference="s3://bucket/receipts/no-metadata.jpg",
        )
        db_session.add(task_without_metadata)
        db_session.commit()
        db_session.refresh(task_without_metadata)

        # Verify task_metadata is None by default
        assert task_without_metadata.task_metadata is None

        # Create task with metadata
        metadata = {"store_hint": "Costco", "location": "Seattle"}
        task_with_metadata = ProcessingTask(
            id=uuid4(),
            user_id=user_id,
            task_type=TaskType.receipt_parse.value,
            status=TaskStatus.pending.value,
            input_reference="s3://bucket/receipts/with-metadata.jpg",
            task_metadata=metadata,
        )
        db_session.add(task_with_metadata)
        db_session.commit()
        db_session.refresh(task_with_metadata)

        # Verify task_metadata is stored correctly
        assert task_with_metadata.task_metadata is not None
        assert task_with_metadata.task_metadata == metadata
        assert task_with_metadata.task_metadata["store_hint"] == "Costco"
        assert task_with_metadata.task_metadata["location"] == "Seattle"
