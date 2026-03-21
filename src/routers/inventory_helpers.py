"""
Helper functions for inventory item ownership verification.

Centralizes ownership validation logic to reduce code duplication across
inventory CRUD endpoints and maintain consistent error handling.
"""

from uuid import UUID
from sqlalchemy.orm import Session

from src.db.models.user import User
from src.db.models.inventory_item import InventoryItem
from src.utils.ownership import verify_ownership


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
    return verify_ownership(
        entity_class=InventoryItem,
        entity_id=item_id,
        ownership_field='added_by',
        current_user=current_user,
        db=db,
        entity_name="Inventory item"
    )
