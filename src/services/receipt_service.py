"""
Service layer for receipt processing operations.

Provides business logic for receipt submission, confirmation, and inventory
item creation from parsed receipt data.
"""

import json
import logging
from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.models.processing_task import ProcessingTask, TaskStatus, TaskType
from src.db.models.inventory_item import InventoryItem
from src.schemas.receipt import ReceiptInventoryCandidate
from src.schemas.inventory import InventoryItemCreate
from src.services.task_service import get_task_by_id
from src.services.inventory_service import create_inventory_items_bulk

logger = logging.getLogger(__name__)


def submit_receipt(
    receipt_text: str,
    user_id: UUID,
    db: Session,
    store_name: Optional[str] = None,
) -> ProcessingTask:
    """
    Submit receipt text for async LLM parsing.

    Creates a ProcessingTask with task_type='receipt_parse' and stores
    the receipt text and optional store name as JSON in input_reference.
    The background task worker will pick up and process this task.

    Args:
        receipt_text: Receipt text content (digital copy-paste or OCR output)
        user_id: ID of the authenticated user submitting the receipt
        db: Database session
        store_name: Optional store name for store-specific parsing hints

    Returns:
        ProcessingTask: Created task with status='pending'

    Raises:
        HTTPException(500): If database error occurs during task creation
    """
    # Create JSON input_reference matching task worker expectations
    # (see task_worker.py lines 68-83 for JSON format parsing)
    input_data = {
        "receipt_text": receipt_text,
        "store_name": store_name
    }
    input_reference = json.dumps(input_data)

    # Create ProcessingTask
    task = ProcessingTask(
        user_id=user_id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.pending.value,
        input_reference=input_reference,
    )

    db.add(task)

    try:
        db.commit()
        db.refresh(task)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during receipt submission for user {user_id}")
        logger.debug(f"Integrity error occurred during receipt submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt submission failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during receipt submission for user {user_id}")
        logger.debug(f"Database error occurred during receipt submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting the receipt"
        )

    # Sanitize store_name for logging to prevent log injection
    safe_store_name = store_name.replace('\n', ' ').replace('\r', ' ') if store_name else None
    logger.info(
        f"Receipt submitted for processing: user_id={user_id}, "
        f"task_id={task.id}, store_name={safe_store_name}"
    )

    return task


def confirm_receipt_items(
    task_id: UUID,
    candidates: list[ReceiptInventoryCandidate],
    user_id: UUID,
    db: Session
) -> list[InventoryItem]:
    """
    Confirm receipt inventory candidates and create inventory items.

    Validates that the task exists, belongs to the user, and has completed successfully
    before creating inventory items from the confirmed candidates.

    Multi-tenant isolation: Service layer validates task ownership to ensure users
    can only confirm their own receipt parsing tasks (defense-in-depth).

    Args:
        task_id: ID of the receipt parsing task to confirm
        candidates: List of user-reviewed inventory candidates to create
        user_id: ID of the authenticated user
        db: Database session

    Returns:
        List of created InventoryItem objects

    Raises:
        HTTPException(404): If task doesn't exist or doesn't belong to user
        HTTPException(400): If task status is not "completed"
    """
    # Retrieve task with multi-tenant isolation (defense-in-depth)
    task = get_task_by_id(task_id, user_id, db)

    if not task:
        logger.warning(f"Task {task_id} not found for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt parsing task not found"
        )

    # Validate task has completed successfully
    if task.status != TaskStatus.completed.value:
        logger.warning(
            f"Attempt to confirm non-completed task {task_id} "
            f"(status: {task.status}) by user {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot confirm receipt: task status is '{task.status}', must be 'completed'"
        )

    # Convert candidates to InventoryItemCreate schemas
    items_to_create = [
        InventoryItemCreate(
            name=candidate.name,
            quantity=candidate.quantity,
            unit=candidate.unit,
            category=candidate.category,
            storage_location=candidate.storage_location,
            price=candidate.price,
            added_by=user_id,  # Will be overridden by service layer for security
        )
        for candidate in candidates
    ]

    # Create inventory items atomically
    created_items = create_inventory_items_bulk(items_to_create, user_id, db)

    logger.info(
        f"Confirmed {len(created_items)} items from task {task_id} for user {user_id}"
    )

    return created_items
