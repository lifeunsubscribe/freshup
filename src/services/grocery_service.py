"""
Grocery list service for FreshUp.

Provides business logic for grocery list purchase operations,
including single item and bulk purchase actions with optional
inventory item creation.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from src.db.models.user import User
from src.db.models.grocery_list import GroceryListItem
from src.db.models.inventory_item import InventoryItem

logger = logging.getLogger(__name__)


def mark_purchased(
    item_id: UUID,
    current_user: User,
    db: Session,
) -> GroceryListItem:
    """
    Mark a grocery item as purchased.

    Sets purchased=True, purchased_by=current_user, purchased_date=now.
    Any authenticated user can purchase any item (household coordination).

    Args:
        item_id: UUID of the grocery item to mark as purchased
        current_user: Authenticated user performing the purchase
        db: Database session

    Returns:
        GroceryListItem: Updated grocery item

    Raises:
        HTTPException(404): If item doesn't exist
        HTTPException(500): If database error occurs
    """
    item = db.query(GroceryListItem).filter(GroceryListItem.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found"
        )

    # Update purchase fields
    item.purchased = True
    item.purchased_by = current_user.id
    item.purchased_date = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during grocery item purchase for user {current_user.id}")
        logger.debug(f"Database error occurred during grocery item purchase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while marking the item as purchased"
        )

    logger.info(
        f"Grocery item purchased: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return item


def mark_unpurchased(
    item_id: UUID,
    current_user: User,
    db: Session,
) -> GroceryListItem:
    """
    Reverse a grocery item purchase (mark as unpurchased).

    Sets purchased=False, purchased_by=None, purchased_date=None.
    Any authenticated user can unpurchase any item (household coordination).

    Args:
        item_id: UUID of the grocery item to mark as unpurchased
        current_user: Authenticated user performing the unpurchase
        db: Database session

    Returns:
        GroceryListItem: Updated grocery item

    Raises:
        HTTPException(404): If item doesn't exist
        HTTPException(500): If database error occurs
    """
    item = db.query(GroceryListItem).filter(GroceryListItem.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found"
        )

    # Clear purchase fields
    item.purchased = False
    item.purchased_by = None
    item.purchased_date = None

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during grocery item unpurchase for user {current_user.id}")
        logger.debug(f"Database error occurred during grocery item unpurchase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while marking the item as unpurchased"
        )

    logger.info(
        f"Grocery item unpurchased: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return item


def bulk_purchase(
    item_ids: list[UUID],
    current_user: User,
    db: Session,
    create_inventory_item: bool = False,
    storage_location: Optional[str] = None,
    category: Optional[str] = None,
) -> tuple[list[GroceryListItem], int]:
    """
    Mark multiple grocery items as purchased in a single atomic transaction.

    Optionally creates inventory items from purchased groceries when
    create_inventory_item=True. If any item_id is not found, the entire
    transaction is rolled back.

    Args:
        item_ids: List of grocery item UUIDs to mark as purchased
        current_user: Authenticated user performing the bulk purchase
        db: Database session
        create_inventory_item: Whether to create inventory items (default: False)
        storage_location: Storage location for inventory items (required if create_inventory_item=True)
        category: Category for inventory items (required if create_inventory_item=True)

    Returns:
        tuple[list[GroceryListItem], int]: Updated grocery items and count of inventory items created

    Raises:
        HTTPException(404): If any item_id is not found (entire batch fails)
        HTTPException(500): If database error occurs
    """
    updated_items = []
    inventory_count = 0
    purchase_time = datetime.now(timezone.utc)

    try:
        # Atomic transaction: fetch all items in a single query
        # This ensures all-or-nothing semantics - either all items are purchased or none are
        items = db.query(GroceryListItem).filter(GroceryListItem.id.in_(item_ids)).all()

        # Verify all requested items were found
        if len(items) != len(item_ids):
            found_ids = {item.id for item in items}
            missing_ids = [item_id for item_id in item_ids if item_id not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grocery item not found: {missing_ids[0]}"
            )

        # Mark all items as purchased
        for item in items:
            # Track if item was already purchased (to prevent duplicate inventory creation)
            was_already_purchased = item.purchased

            item.purchased = True
            item.purchased_by = current_user.id
            item.purchased_date = purchase_time

            updated_items.append(item)

            # Optionally create inventory item (only if not already purchased)
            if create_inventory_item and not was_already_purchased:
                # Create inventory item from grocery item
                inventory_item = InventoryItem(
                    name=item.item_name,
                    quantity=item.quantity,
                    unit=item.unit,
                    storage_location=storage_location,  # type: ignore - validated by schema
                    category=category,  # type: ignore - validated by schema
                    added_by=current_user.id,
                )
                db.add(inventory_item)
                inventory_count += 1

        # Commit all changes atomically
        db.commit()

        # Refresh all items to get updated data
        for item in updated_items:
            db.refresh(item)

    except HTTPException:
        # Re-raise HTTP exceptions (404s)
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during bulk grocery purchase for user {current_user.id}")
        logger.debug(f"Database error occurred during bulk grocery purchase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the bulk purchase"
        )

    logger.info(
        f"Bulk grocery purchase: user_id={current_user.id}, "
        f"items_purchased={len(updated_items)}, "
        f"inventory_items_created={inventory_count}"
    )

    return updated_items, inventory_count
