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
from src.schemas.receipt import ReceiptTaskStatusResponse
from src.services.receipt_service import get_receipt_task_status
from src.middleware.auth import get_current_user
from src.exceptions import DomainException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=ReceiptTaskStatusResponse, status_code=status.HTTP_200_OK)
def get_task_status(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the status of a receipt parsing task.

    Returns the current status of a receipt parsing task and its result (if completed) or error (if failed).
    Includes parsed ReceiptParseResult when status is 'completed'.
    Requires authentication. Users can only access their own tasks.

    Args:
        task_id: UUID of the task to retrieve
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        ReceiptTaskStatusResponse with task status, metadata, and parsed result/error if applicable

    Raises:
        HTTPException 400: Task type is not "receipt_parse"
        HTTPException 404: Task not found or not owned by current user
        HTTPException 401: Unauthorized (no valid token)
        HTTPException 500: If result parsing fails for completed task
    """
    try:
        # Call receipt service which validates task type and ownership (defense-in-depth)
        receipt_status = get_receipt_task_status(task_id, current_user.id, db)

        if not receipt_status:
            # Return 404 for both not-found and unauthorized to prevent information disclosure
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found"
            )

        return receipt_status

    except DomainException as e:
        # Convert domain exceptions to HTTPException
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        # Convert runtime errors to 500
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
