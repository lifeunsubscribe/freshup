"""
Task status endpoints for FreshUp.

Provides endpoints for checking the status of async processing tasks
(e.g., receipt parsing, recipe scraping). Clients poll these endpoints
to check task completion.
"""

import logging
from typing import Union
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.processing_task import TaskType
from src.schemas.task import ProcessingTaskResponse
from src.schemas.receipt import ReceiptTaskStatusResponse
from src.services.task_service import get_task_by_id
from src.services.receipt_service import get_receipt_task_status
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=Union[ReceiptTaskStatusResponse, ProcessingTaskResponse], status_code=status.HTTP_200_OK)
def get_task_status(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the status of a processing task.

    Returns the current status of a task and its result (if completed) or error (if failed).
    For receipt parsing tasks, includes parsed ReceiptParseResult when status is 'completed'.
    Requires authentication. Users can only access their own tasks.

    Args:
        task_id: UUID of the task to retrieve
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        ReceiptTaskStatusResponse (for receipt tasks) or ProcessingTaskResponse (for other tasks)
        with task status, metadata, and result/error if applicable

    Raises:
        HTTPException 404: Task not found or not owned by current user
        HTTPException 401: Unauthorized (no valid token)
        HTTPException 500: If result parsing fails for receipt tasks
    """
    # Service layer enforces user_id filtering for defense-in-depth
    task = get_task_by_id(task_id, current_user.id, db)

    if not task:
        # Return 404 for both not-found and unauthorized to prevent information disclosure
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found"
        )

    # For receipt parsing tasks, return parsed result when completed
    if task.task_type == TaskType.receipt_parse.value:
        try:
            receipt_status = get_receipt_task_status(task_id, current_user.id, db)
            if receipt_status:
                return receipt_status
            # Fallback to generic response if parsing fails (shouldn't happen)
            logger.warning(
                f"Receipt task {task_id} returned None from get_receipt_task_status, falling back to generic response. "
                f"Task status: {task.status}, has result_reference: {task.result_reference is not None}"
            )
            return ProcessingTaskResponse.model_validate(task)
        except RuntimeError as e:
            # Handle malformed result_reference JSON in completed tasks
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse receipt result: {str(e)}"
            )

    # For other task types, return generic response
    return ProcessingTaskResponse.model_validate(task)
