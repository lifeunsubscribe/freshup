"""
Task status endpoints for FreshUp.

Provides endpoints for checking the status of async processing tasks
(e.g., receipt parsing, recipe scraping). Clients poll these endpoints
to check task completion.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.schemas.task import ProcessingTaskResponse
from src.services.task_service import get_task_by_id
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=ProcessingTaskResponse, status_code=status.HTTP_200_OK)
def get_task_status(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the status of a processing task.

    Returns the current status of a task and its result (if completed) or error (if failed).
    Requires authentication. Users can only access their own tasks.

    Args:
        task_id: UUID of the task to retrieve
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        ProcessingTaskResponse with task status, metadata, and result/error if applicable

    Raises:
        HTTPException 404: Task not found or not owned by current user
        HTTPException 401: Unauthorized (no valid token)
    """
    # Service layer enforces user_id filtering for defense-in-depth
    task = get_task_by_id(task_id, current_user.id, db)

    if not task:
        # Return 404 for both not-found and unauthorized to prevent information disclosure
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found"
        )

    return ProcessingTaskResponse.model_validate(task)
