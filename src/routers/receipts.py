"""
Receipt processing endpoints for FreshUp.

Provides endpoints for users to submit receipts for async LLM parsing and
confirm parsed receipt data to add items to their inventory. All endpoints
are scoped to the authenticated user.

Logging Policy:
    Receipt text content is NOT logged as it may contain sensitive information
    (e.g., prescription names, dietary restrictions). Logs include operational
    metadata (user_id, task_id, timestamps) for debugging while protecting
    user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.schemas.receipt import (
    ReceiptSubmitRequest,
    ReceiptSubmitResponse,
    ReceiptConfirmRequest,
    ReceiptConfirmResponse,
)
from src.schemas.inventory import InventoryItemResponse
from src.services.receipt_service import submit_receipt, confirm_receipt_items
from src.middleware.auth import get_current_user
from src.exceptions import DomainException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post(
    "",
    response_model=ReceiptSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def submit_receipt_for_processing(
    request: ReceiptSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit receipt text for async LLM parsing.

    Accepts receipt text (e.g., from Costco digital receipt copy-paste) and
    optional store name, creates a ProcessingTask for background LLM parsing,
    and returns 202 Accepted with task ID for status polling.

    This is text-only input for digital receipts. File upload is handled
    separately in Phase 4B.

    Multi-tenant isolation: Task is created with current_user.id for ownership.

    Args:
        request: ReceiptSubmitRequest with receipt_text and optional store_name
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        ReceiptSubmitResponse with task_id, status='pending', and message

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If receipt_text is empty, too short, or too long
        HTTPException(500): If database error occurs during task creation
    """
    try:
        # Submit receipt via service layer
        task = submit_receipt(
            receipt_text=request.receipt_text,
            user_id=current_user.id,
            db=db,
            store_name=request.store_name,
        )

        return ReceiptSubmitResponse(
            task_id=task.id,
            status=task.status,
            message="Receipt submitted for processing"
        )

    except DomainException as e:
        # Convert domain exceptions to HTTPException
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        # Convert runtime errors to 500
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{task_id}/confirm",
    response_model=ReceiptConfirmResponse,
    status_code=status.HTTP_201_CREATED
)
def confirm_receipt(
    task_id: UUID,
    request: ReceiptConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm receipt inventory candidates and create inventory items.

    Users review parsed receipt items, optionally edit quantities/categories,
    and confirm to add items to their inventory. This endpoint creates
    InventoryItem records from the confirmed candidates.

    Multi-tenant isolation: Only the user who created the parsing task can
    confirm its items. Task ownership is validated at the service layer.

    Args:
        task_id: UUID of the receipt parsing task to confirm
        request: ReceiptConfirmRequest with list of inventory candidates
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        ReceiptConfirmResponse with created item count and full item details

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If task doesn't exist or doesn't belong to user
        HTTPException(400): If task status is not "completed"
        HTTPException(422): If validation fails (empty items, invalid enums, etc.)
        HTTPException(500): If database error occurs during creation
    """
    try:
        # Confirm items via service layer (validates task ownership and status)
        created_items = confirm_receipt_items(
            task_id=task_id,
            candidates=request.items,
            user_id=current_user.id,
            db=db
        )

        # Convert to response schemas
        items_response = [
            InventoryItemResponse.model_validate(item)
            for item in created_items
        ]

        logger.info(
            f"User {current_user.id} confirmed {len(created_items)} items "
            f"from task {task_id}"
        )

        return ReceiptConfirmResponse(
            created_count=len(created_items),
            items=items_response
        )

    except DomainException as e:
        # Convert domain exceptions to HTTPException
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        # Convert runtime errors to 500
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    except IntegrityError as e:
        logger.error(
            f"Integrity error during receipt confirmation for user {current_user.id}, "
            f"task {task_id}"
        )
        logger.debug(f"Integrity error occurred during receipt confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt confirmation failed due to data integrity violation"
        )

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during receipt confirmation for user {current_user.id}, "
            f"task {task_id}"
        )
        logger.debug(f"Database error occurred during receipt confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while confirming the receipt"
        )
