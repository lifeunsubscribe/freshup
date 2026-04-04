"""
Service layer for inventory item operations.

Provides business logic for creating and managing inventory items,
including bulk operations for receipt confirmation.
"""

import logging
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.models.inventory_item import InventoryItem, Shareability
from src.schemas.inventory import InventoryItemCreate

logger = logging.getLogger(__name__)


def create_inventory_items_bulk(
    items_data: list[InventoryItemCreate],
    user_id: UUID,
    db: Session
) -> list[InventoryItem]:
    """
    Create multiple inventory items in a single transaction.

    Used by receipt confirmation to atomically create all confirmed items.
    If any item fails validation or creation, the entire transaction is rolled back
    to maintain data consistency.

    Args:
        items_data: List of inventory item creation schemas
        user_id: ID of the user creating the items (added_by field)
        db: Database session

    Returns:
        List of created InventoryItem objects with generated IDs

    Raises:
        IntegrityError: If data integrity constraint is violated
        SQLAlchemyError: If database operation fails
    """
    created_items = []

    try:
        for item_data in items_data:
            # Create inventory item, overriding added_by with authenticated user
            item_dict = item_data.model_dump(exclude={'added_by'})
            new_item = InventoryItem(
                **item_dict,
                added_by=user_id,
            )
            db.add(new_item)
            created_items.append(new_item)

        # Commit all items atomically
        db.commit()

        # Refresh all items to get generated IDs and defaults
        for item in created_items:
            db.refresh(item)

        logger.info(f"Created {len(created_items)} inventory items for user {user_id}")
        return created_items

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during bulk inventory item creation for user {user_id}")
        logger.debug(f"Integrity error occurred during bulk inventory item creation: {e}")
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during bulk inventory item creation for user {user_id}")
        logger.debug(f"Database error occurred during bulk inventory item creation: {e}")
        raise
