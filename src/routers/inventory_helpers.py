"""
Helper functions for inventory item ownership verification.

Centralizes ownership validation logic to reduce code duplication across
inventory CRUD endpoints and maintain consistent error handling.
"""

from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models.user import User
from src.db.models.inventory_item import InventoryItem


def verify_inventory_item_ownership(
    item_id: UUID,
    current_user: User,
    db: Session,
) -> InventoryItem:
    """
    Verify that an inventory item exists and belongs to the current user.

    Used by update and delete endpoints that enforce ownership at the
    database query level for efficiency.

    Args:
        item_id: UUID of the inventory item to verify
        current_user: Authenticated user making the request
        db: Database session

    Returns:
        InventoryItem: The item if it exists and belongs to current user

    Raises:
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.added_by == current_user.id,
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    return item
