"""
Receipt processing endpoints for FreshUp.

Provides endpoints for users to confirm parsed receipt data and add items
to their inventory. All endpoints are scoped to the authenticated user.

Logging Policy:
    User-provided item names are NOT logged as they may contain sensitive
    health information (e.g., prescription names, dietary restrictions).
    Logs include operational metadata (user_id, task_id, timestamps) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.schemas.receipt import (
    ReceiptConfirmRequest,
    ReceiptConfirmResponse,
)
from src.schemas.inventory import InventoryItemResponse
from src.services.receipt_service import confirm_receipt_items
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"])


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
