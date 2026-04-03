"""
Background task worker for processing async LLM tasks.

Polls for pending ProcessingTasks and processes them using OllamaClient.
Runs as an asyncio.create_task inside the FastAPI lifespan context manager.

Per ADR Section 2A: Background Task Processing
- Sequential processing (no parallelism at household scale)
- Graceful handling of Ollama unavailability (task stays pending)
- Graceful handling of validation failures (task marked failed)
- Automatic recovery of stale tasks (timeout-based, prevents race condition)
- Clean shutdown on cancellation
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.database import get_session_factory
from src.db.models.processing_task import ProcessingTask, TaskStatus, TaskType
from src.schemas.receipt import ReceiptParseResult
from src.services.llm.client import OllamaClient
from src.services.llm.exceptions import LLMUnavailableError, LLMResponseError
from src.services.llm.prompts.receipt import SYSTEM_PROMPT, create_user_prompt
from src.utils.sanitize import sanitize_exception_message

logger = logging.getLogger(__name__)
settings = get_settings()


async def process_receipt_task(
    task: ProcessingTask,
    session: Session,
    ollama_client: OllamaClient
) -> None:
    """
    Process a single receipt parsing task.

    Extracts receipt text from input_reference, sends to OllamaClient for parsing,
    and updates the task with the result or error.

    Args:
        task: The ProcessingTask to process
        session: Database session for updates
        ollama_client: OllamaClient instance for LLM operations

    Raises:
        LLMUnavailableError: If Ollama is unreachable (task should stay pending)
        LLMResponseError: If LLM response validation fails after retries
    """
    # Extract receipt text from input_reference
    # For now, input_reference contains the raw receipt text directly
    # In future, this could be a file path or S3 reference
    receipt_text = task.input_reference

    # Create user prompt from receipt text
    user_prompt = create_user_prompt(receipt_text)

    # Call Ollama to parse the receipt
    # This raises LLMUnavailableError or LLMResponseError on failure
    result: ReceiptParseResult = await ollama_client.complete(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
        response_schema=ReceiptParseResult
    )

    # Success! Serialize result to JSON and store
    result_json = result.model_dump_json()

    # Update task status
    task.status = TaskStatus.completed.value
    task.result_reference = result_json
    task.completed_at = datetime.now(timezone.utc)

    session.commit()

    logger.info(
        "Receipt parsing task completed",
        extra={
            "task_id": str(task.id),
            "store_name": result.store_name,
            "line_item_count": len(result.line_items)
        }
    )


def recover_stale_tasks(session: Session) -> int:
    """
    Recover tasks stuck in "processing" status beyond the timeout window.

    Detects tasks that have been in "processing" status longer than
    task_processing_timeout_seconds and either resets them to "pending"
    for retry or marks them as "failed" if retry limit exceeded.

    This prevents tasks from being stuck forever if the worker crashes
    between marking a task as "processing" and completing it, while also
    preventing infinite retry loops for tasks that consistently crash workers.

    Args:
        session: Database session for queries and updates

    Returns:
        Number of tasks processed (includes both retried and failed tasks)
    """
    # Calculate timeout threshold
    timeout_threshold = datetime.now(timezone.utc) - timedelta(
        seconds=settings.task_processing_timeout_seconds
    )

    # Query for stale processing tasks
    stmt = (
        select(ProcessingTask)
        .where(
            ProcessingTask.status == TaskStatus.processing.value,
            ProcessingTask.processing_started_at.isnot(None),
            ProcessingTask.processing_started_at < timeout_threshold
        )
    )
    result = session.execute(stmt)
    stale_tasks = result.scalars().all()

    if not stale_tasks:
        return 0

    # Process stale tasks: retry or fail based on retry count
    processed_count = 0
    for task in stale_tasks:
        # Check if retry limit exceeded
        if task.retry_count >= settings.task_max_retry_count:
            # Mark task as failed - retry limit exceeded
            logger.warning(
                "Task failed: retry limit exceeded",
                extra={
                    "task_id": str(task.id),
                    "retry_count": task.retry_count,
                    "max_retry_count": settings.task_max_retry_count,
                    "processing_started_at": task.processing_started_at.isoformat() if task.processing_started_at else None
                }
            )
            task.status = TaskStatus.failed.value
            task.error_message = (
                f"Task exceeded maximum retry limit ({settings.task_max_retry_count}) "
                f"after repeated stale task recovery attempts"
            )
            task.completed_at = datetime.now(timezone.utc)
        else:
            # Reset to pending and increment retry count
            logger.warning(
                "Recovering stale task stuck in processing",
                extra={
                    "task_id": str(task.id),
                    "retry_count": task.retry_count,
                    "processing_started_at": task.processing_started_at.isoformat() if task.processing_started_at else None,
                    "timeout_seconds": settings.task_processing_timeout_seconds
                }
            )
            task.status = TaskStatus.pending.value
            task.processing_started_at = None
            task.retry_count += 1

        processed_count += 1

    session.commit()

    logger.info(
        f"Processed {processed_count} stale task(s)",
        extra={"processed_count": processed_count}
    )

    return processed_count


async def process_pending_tasks() -> None:
    """
    Process all pending receipt_parse tasks sequentially.

    Queries for tasks with status='pending' and task_type='receipt_parse',
    processes each one, and updates status appropriately.

    Handles Ollama unavailability gracefully by skipping tasks and leaving
    them pending for the next poll interval.
    """
    # Create database session for this iteration
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        # Recover stale tasks before processing new ones
        recover_stale_tasks(session)

        # Create Ollama client
        async with OllamaClient() as ollama_client:
            # Check if Ollama is available before processing
            if not await ollama_client.is_available():
                logger.warning(
                    "Ollama is unavailable, skipping task processing this interval"
                )
                return

            # Query for pending receipt_parse tasks (oldest first)
            stmt = (
                select(ProcessingTask)
                .where(
                    ProcessingTask.status == TaskStatus.pending.value,
                    ProcessingTask.task_type == TaskType.receipt_parse.value
                )
                .order_by(ProcessingTask.created_at)
            )
            result = session.execute(stmt)
            pending_tasks = result.scalars().all()

            if not pending_tasks:
                logger.debug("No pending tasks to process")
                return

            logger.info(
                f"Processing {len(pending_tasks)} pending task(s)",
                extra={"task_count": len(pending_tasks)}
            )

            # Process each task sequentially
            for task in pending_tasks:
                try:
                    # Mark task as processing and record start time
                    task.status = TaskStatus.processing.value
                    task.processing_started_at = datetime.now(timezone.utc)
                    session.commit()

                    logger.info(
                        "Processing receipt task",
                        extra={"task_id": str(task.id)}
                    )

                    # Process the task
                    await process_receipt_task(task, session, ollama_client)

                except LLMUnavailableError as e:
                    # Ollama became unavailable during processing
                    # Revert task to pending and skip remaining tasks
                    logger.warning(
                        f"Ollama unavailable during task processing: {e}",
                        extra={"task_id": str(task.id)}
                    )
                    task.status = TaskStatus.pending.value
                    task.processing_started_at = None
                    session.commit()
                    break  # Stop processing, retry next interval

                except LLMResponseError as e:
                    # LLM validation failed after all retries
                    # Mark task as failed with sanitized error details
                    # Note: e.validation_errors are already sanitized by LLMResponseError.__init__
                    logger.error(
                        f"Receipt parsing validation failed: {e}",
                        extra={
                            "task_id": str(task.id),
                            "validation_errors": e.validation_errors
                        }
                    )
                    task.status = TaskStatus.failed.value
                    # Sanitize error message before storing (defense in depth)
                    task.error_message = sanitize_exception_message(f"Validation failed after retries: {str(e)}")
                    task.completed_at = datetime.now(timezone.utc)
                    session.commit()
                    # Continue to next task

                except Exception as e:
                    # Unexpected error - log and mark task as failed
                    logger.error(
                        f"Unexpected error processing task: {e}",
                        extra={"task_id": str(task.id)},
                        exc_info=True
                    )
                    task.status = TaskStatus.failed.value
                    # Sanitize error message before storing (may contain receipt data)
                    task.error_message = sanitize_exception_message(f"Unexpected error: {str(e)}")
                    task.completed_at = datetime.now(timezone.utc)
                    session.commit()
                    # Continue to next task

    finally:
        # Always close the session
        session.close()


async def background_task_worker() -> None:
    """
    Background worker that polls for pending tasks at regular intervals.

    Runs indefinitely until cancelled (on application shutdown).
    Handles CancelledError gracefully for clean shutdown.
    """
    logger.info(
        f"Background task worker started (poll interval: {settings.task_poll_interval_seconds}s)"
    )

    try:
        while True:
            try:
                # Process pending tasks
                await process_pending_tasks()

            except asyncio.CancelledError:
                # Shutdown signal received
                raise

            except Exception as e:
                # Log unexpected errors but keep worker running
                logger.error(
                    f"Error in task worker iteration: {e}",
                    exc_info=True
                )

            # Sleep until next poll interval
            await asyncio.sleep(settings.task_poll_interval_seconds)

    except asyncio.CancelledError:
        logger.info("Background task worker shutting down gracefully")
        raise  # Re-raise to signal completion
