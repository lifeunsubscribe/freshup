"""
Grocery list CRUD endpoints for FreshUp.

Provides endpoints for users to manage their household grocery list,
including adding items, checking off purchases, and optionally creating
inventory items from purchased groceries.

Per ADR, any authenticated user can purchase/unpurchase any item —
this is a household coordination action, not owner-restricted.

Logging Policy:
    User-provided item names are NOT logged as they may contain sensitive
    health information (e.g., prescription names, dietary restrictions).
    Logs include operational metadata (user_id, item_id, timestamps) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.schemas.grocery import (
    GroceryItemResponse,
    BulkPurchaseRequest,
    BulkPurchaseResponse,
)
from src.middleware.auth import get_current_user
from src.services import grocery_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grocery", tags=["grocery"])


@router.put("/{item_id}/purchase", response_model=GroceryItemResponse)
def purchase_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a grocery item as purchased.

    Sets purchased=True, purchased_by=current_user, purchased_date=now.
    Any authenticated user can purchase any item (household coordination).

    Args:
        item_id: UUID of the grocery item to mark as purchased
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Updated grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist
        HTTPException(500): If database error occurs
    """
    return grocery_service.mark_purchased(item_id, current_user, db)


@router.put("/{item_id}/unpurchase", response_model=GroceryItemResponse)
def unpurchase_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reverse a grocery item purchase (mark as unpurchased).

    Sets purchased=False, purchased_by=None, purchased_date=None.
    Any authenticated user can unpurchase any item (household coordination).

    Args:
        item_id: UUID of the grocery item to mark as unpurchased
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Updated grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist
        HTTPException(500): If database error occurs
    """
    return grocery_service.mark_unpurchased(item_id, current_user, db)


@router.post("/bulk-purchase", response_model=BulkPurchaseResponse)
def bulk_purchase_items(
    request_data: BulkPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark multiple grocery items as purchased in a single atomic transaction.

    Optionally creates inventory items from purchased groceries when
    create_inventory_item=True. If any item_id is not found, the entire
    transaction is rolled back (all-or-nothing semantics).

    When create_inventory_item=True, storage_location and category are REQUIRED
    (enforced by schema validation - returns 422 if missing).

    Inventory items created with:
    - name = grocery item_name
    - quantity = grocery quantity
    - unit = grocery unit
    - storage_location = request storage_location
    - category = request category
    - added_by = current_user

    Args:
        request_data: Bulk purchase request with item IDs and optional inventory creation params
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        BulkPurchaseResponse: List of updated grocery items and count of inventory items created

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If any item_id is not found (entire batch fails)
        HTTPException(422): If create_inventory_item=True but storage_location or category missing
        HTTPException(500): If database error occurs
    """
    updated_items, inventory_count = grocery_service.bulk_purchase(
        item_ids=request_data.item_ids,
        current_user=current_user,
        db=db,
        create_inventory_item=request_data.create_inventory_item,
        storage_location=request_data.storage_location,
        category=request_data.category,
    )

    return BulkPurchaseResponse(
        items=updated_items,
        inventory_items_created=inventory_count
    )
