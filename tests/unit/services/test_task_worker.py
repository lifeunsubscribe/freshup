"""
Unit tests for background task worker.

Tests cover:
- Successful receipt parsing task processing
- Ollama unavailable (task stays pending)
- LLM validation failure after retries (task marked failed)
- Unexpected errors (task marked failed)
- Graceful shutdown on CancelledError
- Multiple task processing
- Empty queue handling

All tests mock OllamaClient and database operations.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.task_worker import (
    process_receipt_task,
    process_pending_tasks,
    background_task_worker,
    recover_stale_tasks
)
from src.db.models.processing_task import ProcessingTask, TaskStatus, TaskType
from src.schemas.receipt import ReceiptParseResult, ReceiptLineItem
from src.services.llm.exceptions import LLMUnavailableError, LLMResponseError


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    monkeypatch.setenv("TASK_POLL_INTERVAL_SECONDS", "1")  # Fast polling for tests

    get_settings.cache_clear()


@pytest.fixture
def mock_task():
    """Create a mock ProcessingTask."""
    task = MagicMock(spec=ProcessingTask)
    task.id = uuid4()
    task.task_type = TaskType.receipt_parse.value
    task.status = TaskStatus.pending.value
    task.input_reference = "Costco\n2024-03-29\nBananas $3.99\nMilk $4.49"
    task.result_reference = None
    task.error_message = None
    task.created_at = datetime.now(timezone.utc)
    task.completed_at = None
    task.retry_count = 0
    return task


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.commit = MagicMock()
    session.close = MagicMock()
    session.execute = MagicMock()
    return session


@pytest.fixture
def mock_ollama_client():
    """Create a mock OllamaClient."""
    client = AsyncMock()
    client.complete = AsyncMock()
    client.is_available = AsyncMock(return_value=True)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock()
    return client


@pytest.fixture
def sample_receipt_result():
    """Create a sample ReceiptParseResult."""
    return ReceiptParseResult(
        store_name="Costco",
        receipt_date="2024-03-29",
        line_items=[
            ReceiptLineItem(
                item_name="Bananas",
                quantity=1.0,
                unit_price=None,
                total_price=3.99,
                category_guess="produce"
            ),
            ReceiptLineItem(
                item_name="Milk",
                quantity=1.0,
                unit_price=None,
                total_price=4.49,
                category_guess="dairy"
            )
        ]
    )


@pytest.mark.asyncio
async def test_process_receipt_task_success(
    mock_task,
    mock_session,
    mock_ollama_client,
    sample_receipt_result
):
    """Test successful receipt task processing."""
    # Configure mock to return valid result
    mock_ollama_client.complete.return_value = sample_receipt_result

    # Process the task
    await process_receipt_task(mock_task, mock_session, mock_ollama_client)

    # Verify OllamaClient was called correctly
    mock_ollama_client.complete.assert_called_once()
    call_args = mock_ollama_client.complete.call_args[1]
    assert "Costco" in call_args["prompt"]  # Receipt text in prompt
    assert call_args["response_schema"] == ReceiptParseResult

    # Verify task was updated correctly
    assert mock_task.status == TaskStatus.completed.value
    assert mock_task.result_reference is not None
    assert "Costco" in mock_task.result_reference  # JSON contains store name
    assert mock_task.completed_at is not None

    # Verify session commit was called
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_receipt_task_ollama_unavailable(
    mock_task,
    mock_session,
    mock_ollama_client
):
    """Test handling of Ollama unavailability - task should stay pending."""
    # Configure mock to raise LLMUnavailableError
    mock_ollama_client.complete.side_effect = LLMUnavailableError(
        "Failed to connect to Ollama"
    )

    # Process should raise LLMUnavailableError
    with pytest.raises(LLMUnavailableError):
        await process_receipt_task(mock_task, mock_session, mock_ollama_client)

    # Task status should not be modified (stays pending)
    # Session commit should not be called
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_process_receipt_task_validation_failure(
    mock_task,
    mock_session,
    mock_ollama_client
):
    """Test handling of LLM validation failure - task should be marked failed."""
    # Configure mock to raise LLMResponseError
    validation_errors = ["Missing required field: store_name", "Invalid JSON format"]
    mock_ollama_client.complete.side_effect = LLMResponseError(
        "Validation failed after retries",
        response='{"invalid": "data"}',
        validation_errors=validation_errors
    )

    # Process should raise LLMResponseError
    with pytest.raises(LLMResponseError):
        await process_receipt_task(mock_task, mock_session, mock_ollama_client)

    # Task status should not be modified (handled by caller)
    # Session commit should not be called
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_process_pending_tasks_success(
    mock_task,
    sample_receipt_result
):
    """Test processing of pending tasks - successful case."""
    # Mock database query to return one pending task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.complete.return_value = sample_receipt_result
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory):
        with patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client):
            with patch("src.services.task_worker.recover_stale_tasks", return_value=0):
                await process_pending_tasks()

    # Verify task was updated to completed
    assert mock_task.status == TaskStatus.completed.value
    assert mock_task.result_reference is not None
    assert mock_task.completed_at is not None

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_tasks_ollama_unavailable():
    """Test handling when Ollama is unavailable - tasks should stay pending."""
    # Mock database query (no execution needed if Ollama is down)
    mock_session = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient - unavailable
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = False
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    # Mock recover_stale_tasks since it runs before Ollama check
    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory):
        with patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client):
            with patch("src.services.task_worker.recover_stale_tasks", return_value=0):
                await process_pending_tasks()

    # Verify no task query was executed (early return after Ollama check)
    # Note: recover_stale_tasks is mocked, so no actual execute calls
    mock_session.execute.assert_not_called()

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_tasks_validation_failure(mock_task):
    """Test handling of validation failure - task should be marked failed."""
    # Mock database query to return one pending task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient - validation failure
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.complete.side_effect = LLMResponseError(
        "Validation failed",
        validation_errors=["Invalid schema"]
    )
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory):
        with patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client):
            with patch("src.services.task_worker.recover_stale_tasks", return_value=0):
                await process_pending_tasks()

    # Verify task was marked as failed
    assert mock_task.status == TaskStatus.failed.value
    assert mock_task.error_message is not None
    assert "Validation failed" in mock_task.error_message
    assert mock_task.completed_at is not None

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_tasks_ollama_unavailable_during_processing(mock_task):
    """Test handling when Ollama becomes unavailable during processing."""
    # Mock database query to return one pending task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient - becomes unavailable during processing
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.complete.side_effect = LLMUnavailableError(
        "Connection lost"
    )
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory):
        with patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client):
            with patch("src.services.task_worker.recover_stale_tasks", return_value=0):
                await process_pending_tasks()

    # Verify task was reverted to pending
    assert mock_task.status == TaskStatus.pending.value

    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_tasks_no_tasks():
    """Test handling when no pending tasks exist."""
    # Mock database query to return empty list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory):
        with patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client):
            with patch("src.services.task_worker.recover_stale_tasks", return_value=0):
                await process_pending_tasks()

    # Verify no errors occurred
    # Verify session was closed
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_background_task_worker_graceful_shutdown():
    """Test graceful shutdown of background worker on CancelledError."""
    # Mock process_pending_tasks to track calls
    call_count = 0

    async def mock_process_pending_tasks():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate some work

    with patch("src.services.task_worker.process_pending_tasks", side_effect=mock_process_pending_tasks):
        # Start worker
        worker_task = asyncio.create_task(background_task_worker())

        # Let it run for a bit
        await asyncio.sleep(0.5)

        # Cancel the worker
        worker_task.cancel()

        # Wait for graceful shutdown
        with pytest.raises(asyncio.CancelledError):
            await worker_task

        # Verify worker was called at least once
        assert call_count >= 1


@pytest.mark.asyncio
async def test_background_task_worker_handles_errors():
    """Test that background worker continues running after errors."""
    call_count = 0

    async def mock_process_pending_tasks():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Raise error on first call
            raise RuntimeError("Simulated error")
        # Succeed on subsequent calls

    with patch("src.services.task_worker.process_pending_tasks", side_effect=mock_process_pending_tasks), \
         patch("src.services.task_worker.settings") as mock_settings:
        mock_settings.task_poll_interval_seconds = 0.1

        # Start worker
        worker_task = asyncio.create_task(background_task_worker())

        # Let it run through error and recover
        await asyncio.sleep(0.5)

        # Cancel the worker
        worker_task.cancel()

        # Wait for graceful shutdown
        with pytest.raises(asyncio.CancelledError):
            await worker_task

        # Verify worker recovered and continued
        assert call_count >= 2, "Worker should have recovered and continued after error"


@pytest.mark.asyncio
async def test_process_pending_tasks_unexpected_error(mock_task):
    """Test handling of unexpected errors - task should be marked failed."""
    # Mock database query to return one pending task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient - unexpected error
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.complete.side_effect = RuntimeError("Unexpected error")
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory):
        with patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client):
            with patch("src.services.task_worker.recover_stale_tasks", return_value=0):
                await process_pending_tasks()

    # Verify task was marked as failed
    assert mock_task.status == TaskStatus.failed.value
    assert mock_task.error_message is not None
    assert "Unexpected error" in mock_task.error_message
    assert mock_task.completed_at is not None

    # Verify session was closed
    mock_session.close.assert_called_once()


def test_recover_stale_tasks_no_stale_tasks():
    """Test stale task recovery when no tasks are stale."""
    # Mock database query to return empty list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()

    # Recover stale tasks
    recovered_count = recover_stale_tasks(mock_session)

    # Verify no tasks were recovered
    assert recovered_count == 0
    mock_session.commit.assert_not_called()


def test_recover_stale_tasks_with_stale_tasks():
    """Test stale task recovery when tasks exceed timeout."""
    from datetime import timedelta

    # Create mock stale task (processing for 10 minutes)
    stale_task = MagicMock(spec=ProcessingTask)
    stale_task.id = uuid4()
    stale_task.status = TaskStatus.processing.value
    stale_task.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_task.retry_count = 0

    # Mock database query to return stale task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()

    # Recover stale tasks
    recovered_count = recover_stale_tasks(mock_session)

    # Verify task was recovered and retry_count incremented
    assert recovered_count == 1
    assert stale_task.status == TaskStatus.pending.value
    assert stale_task.processing_started_at is None
    assert stale_task.retry_count == 1
    mock_session.commit.assert_called_once()


def test_recover_stale_tasks_multiple_tasks():
    """Test stale task recovery with multiple stale tasks."""
    from datetime import timedelta

    # Create multiple mock stale tasks
    stale_task1 = MagicMock(spec=ProcessingTask)
    stale_task1.id = uuid4()
    stale_task1.status = TaskStatus.processing.value
    stale_task1.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_task1.retry_count = 0

    stale_task2 = MagicMock(spec=ProcessingTask)
    stale_task2.id = uuid4()
    stale_task2.status = TaskStatus.processing.value
    stale_task2.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    stale_task2.retry_count = 1

    # Mock database query to return both tasks
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_task1, stale_task2]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()

    # Recover stale tasks
    recovered_count = recover_stale_tasks(mock_session)

    # Verify both tasks were recovered and retry_counts incremented
    assert recovered_count == 2
    assert stale_task1.status == TaskStatus.pending.value
    assert stale_task1.processing_started_at is None
    assert stale_task1.retry_count == 1
    assert stale_task2.status == TaskStatus.pending.value
    assert stale_task2.processing_started_at is None
    assert stale_task2.retry_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_tasks_calls_recovery():
    """Test that process_pending_tasks calls stale task recovery."""
    # Mock database query to return no pending tasks
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    # Mock recover_stale_tasks to track if it's called
    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory), \
         patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client), \
         patch("src.services.task_worker.recover_stale_tasks") as mock_recover:
        mock_recover.return_value = 0

        await process_pending_tasks()

        # Verify recovery was called
        mock_recover.assert_called_once_with(mock_session)


@pytest.mark.asyncio
async def test_process_pending_tasks_sets_processing_started_at(mock_task, sample_receipt_result):
    """Test that processing_started_at is set when task status changes to processing."""
    # Mock database query to return one pending task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.complete.return_value = sample_receipt_result
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory), \
         patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client), \
         patch("src.services.task_worker.recover_stale_tasks", return_value=0):
        await process_pending_tasks()

    # Verify processing_started_at was set
    assert mock_task.processing_started_at is not None
    assert isinstance(mock_task.processing_started_at, datetime)


@pytest.mark.asyncio
async def test_process_pending_tasks_clears_processing_started_at_on_unavailable(mock_task):
    """Test that processing_started_at is cleared when reverting to pending on LLM unavailable."""
    # Mock database query to return one pending task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()
    mock_session.close = MagicMock()

    # Mock session factory
    mock_session_factory = MagicMock(return_value=mock_session)

    # Mock OllamaClient - becomes unavailable during processing
    mock_ollama_client = AsyncMock()
    mock_ollama_client.is_available.return_value = True
    mock_ollama_client.complete.side_effect = LLMUnavailableError("Connection lost")
    mock_ollama_client.__aenter__.return_value = mock_ollama_client
    mock_ollama_client.__aexit__.return_value = None

    with patch("src.services.task_worker.get_session_factory", return_value=mock_session_factory), \
         patch("src.services.task_worker.OllamaClient", return_value=mock_ollama_client), \
         patch("src.services.task_worker.recover_stale_tasks", return_value=0):
        await process_pending_tasks()

    # Verify task was reverted to pending and processing_started_at was cleared
    assert mock_task.status == TaskStatus.pending.value
    assert mock_task.processing_started_at is None


def test_recover_stale_tasks_retry_limit_exceeded():
    """Test that tasks exceeding retry limit are marked as failed."""
    from datetime import timedelta
    from src.config import get_settings

    settings = get_settings()

    # Create mock stale task that has already hit retry limit
    stale_task = MagicMock(spec=ProcessingTask)
    stale_task.id = uuid4()
    stale_task.status = TaskStatus.processing.value
    stale_task.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_task.retry_count = settings.task_max_retry_count  # Already at limit

    # Mock database query to return stale task
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()

    # Recover stale tasks
    recovered_count = recover_stale_tasks(mock_session)

    # Verify task was marked as failed (not retried)
    assert recovered_count == 1
    assert stale_task.status == TaskStatus.failed.value
    assert stale_task.error_message is not None
    assert "retry limit" in stale_task.error_message.lower()
    assert stale_task.completed_at is not None
    # retry_count should NOT be incremented when task fails
    assert stale_task.retry_count == settings.task_max_retry_count
    mock_session.commit.assert_called_once()


def test_recover_stale_tasks_mixed_retry_scenarios():
    """Test recovery with mix of tasks: some to retry, some to fail."""
    from datetime import timedelta
    from src.config import get_settings

    settings = get_settings()

    # Create task 1: below retry limit (will be retried)
    task1 = MagicMock(spec=ProcessingTask)
    task1.id = uuid4()
    task1.status = TaskStatus.processing.value
    task1.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    task1.retry_count = 1

    # Create task 2: at retry limit (will be failed)
    task2 = MagicMock(spec=ProcessingTask)
    task2.id = uuid4()
    task2.status = TaskStatus.processing.value
    task2.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    task2.retry_count = settings.task_max_retry_count

    # Create task 3: below retry limit (will be retried)
    task3 = MagicMock(spec=ProcessingTask)
    task3.id = uuid4()
    task3.status = TaskStatus.processing.value
    task3.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    task3.retry_count = 0

    # Mock database query to return all tasks
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [task1, task2, task3]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()

    # Recover stale tasks
    recovered_count = recover_stale_tasks(mock_session)

    # Verify all tasks were processed
    assert recovered_count == 3

    # Task 1: should be retried (retry_count incremented)
    assert task1.status == TaskStatus.pending.value
    assert task1.processing_started_at is None
    assert task1.retry_count == 2

    # Task 2: should be failed (at limit)
    assert task2.status == TaskStatus.failed.value
    assert task2.error_message is not None
    assert task2.completed_at is not None
    assert task2.retry_count == settings.task_max_retry_count

    # Task 3: should be retried (retry_count incremented)
    assert task3.status == TaskStatus.pending.value
    assert task3.processing_started_at is None
    assert task3.retry_count == 1

    mock_session.commit.assert_called_once()


def test_recover_stale_tasks_zero_retry_limit():
    """Test recovery when retry limit is set to 0 (no retries allowed)."""
    from datetime import timedelta

    # Create stale task with retry_count = 0
    stale_task = MagicMock(spec=ProcessingTask)
    stale_task.id = uuid4()
    stale_task.status = TaskStatus.processing.value
    stale_task.processing_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_task.retry_count = 0

    # Mock database query
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_task]

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit = MagicMock()

    # Temporarily set retry limit to 0
    with patch("src.services.task_worker.settings") as mock_settings:
        mock_settings.task_max_retry_count = 0
        mock_settings.task_processing_timeout_seconds = 300

        # Recover stale tasks
        recovered_count = recover_stale_tasks(mock_session)

    # With limit=0 and retry_count=0, task should be failed (0 >= 0)
    assert recovered_count == 1
    assert stale_task.status == TaskStatus.failed.value
    assert stale_task.error_message is not None
    mock_session.commit.assert_called_once()
