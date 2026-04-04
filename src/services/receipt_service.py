"""
Service layer for receipt processing operations.

Provides business logic for receipt confirmation and inventory item creation
from parsed receipt data.
"""

import logging
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models.processing_task import ProcessingTask, TaskStatus
from src.db.models.inventory_item import InventoryItem
from src.schemas.receipt import ReceiptInventoryCandidate
from src.schemas.inventory import InventoryItemCreate
from src.services.task_service import get_task_by_id
from src.services.inventory_service import create_inventory_items_bulk

logger = logging.getLogger(__name__)


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
