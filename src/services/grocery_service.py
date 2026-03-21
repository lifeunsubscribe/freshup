"""
Grocery list service for FreshUp.

Provides business logic for grocery list CRUD operations and
purchase actions, including single item and bulk purchase actions
with optional inventory item creation.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import HTTPException, status

from src.db.models.user import User
from src.db.models.grocery_list import GroceryListItem
from src.db.models.inventory_item import InventoryItem, UnitType

logger = logging.getLogger(__name__)

# Pre-computed set of valid inventory units for cross-domain validation
_VALID_INVENTORY_UNITS = {unit_type.value for unit_type in UnitType}


def _validate_unit_for_inventory(unit: str, item_name: str) -> None:
    """
    Validate that a unit value is compatible with the inventory domain's UnitType enum.

    This function provides cross-domain validation at the boundary between grocery
    and inventory domains, ensuring data integrity when converting grocery items
    to inventory items.

    Args:
        unit: The unit string to validate
        item_name: Name of the item (for error messages)

    Raises:
        HTTPException(422): If the unit is not a valid UnitType enum value
    """
    if unit not in _VALID_INVENTORY_UNITS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot create inventory item for '{item_name}': unit '{unit}' is not valid for inventory. Valid units: {', '.join(sorted(_VALID_INVENTORY_UNITS))}"
        )


def create_item(
    item_name: str,
    quantity: float,
    unit: str,
    source: str,
    current_user: User,
    db: Session,
    target_store: Optional[UUID] = None,
) -> GroceryListItem:
    """
    Create a new grocery list item.

    The added_by field is automatically set to the current user's ID,
    ignoring any value provided in the request body for security.

    Args:
        item_name: Name of the grocery item
        quantity: Quantity of the item (must be positive)
        unit: Unit of measurement
        source: Source of the grocery item (e.g., "manual")
        current_user: Authenticated user creating the item
        db: Database session
        target_store: Optional target store ID

    Returns:
        GroceryListItem: Created grocery item

    Raises:
        HTTPException(400): If data integrity violation occurs
        HTTPException(500): If database error occurs
    """
    new_item = GroceryListItem(
        item_name=item_name,
        quantity=quantity,
        unit=unit,
        source=source,
        added_by=current_user.id,
        target_store=target_store,
    )

    db.add(new_item)

    try:
        db.commit()
        db.refresh(new_item)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during grocery item creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during grocery item creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grocery item creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during grocery item creation for user {current_user.id}")
        logger.debug(f"Database error occurred during grocery item creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the grocery item"
        )

    logger.info(
        f"Grocery item created: user_id={current_user.id}, "
        f"item_id={new_item.id}"
    )

    return new_item


def list_items(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    purchased: Optional[bool] = None,
    search: Optional[str] = None,
) -> list[GroceryListItem]:
    """
    List grocery items with filtering and pagination.

    Returns ALL grocery items (shared/global reads), ordered by most recently
    added first. Supports pagination via limit and offset. Supports filtering
    by purchased status and name search.

    Args:
        db: Database session
        limit: Maximum number of items to return (1-100)
        offset: Number of items to skip
        purchased: Filter by purchased status (None returns unpurchased only by default)
        search: Search items by name (case-insensitive partial match)

    Returns:
        list[GroceryListItem]: List of grocery items matching filters
    """
    # Start with base query - NO user filter (shared/global reads)
    query = db.query(GroceryListItem)

    # Apply purchased filter (default: unpurchased only)
    # This default behavior makes the grocery list focused on "what to buy"
    # rather than a historical log of all grocery items
    if purchased is None:
        # Default behavior: show only unpurchased items
        query = query.filter(GroceryListItem.purchased.is_(False))
    else:
        # Explicit filter: show items matching the purchased status
        # Use purchased=true to see completed items, purchased=false for active items
        query = query.filter(GroceryListItem.purchased == purchased)

    # Apply name search filter (case-insensitive partial match)
    if search is not None:
        # Escape LIKE wildcards to prevent DoS via expensive pattern matching
        escaped_search = search.replace('%', r'\%').replace('_', r'\_')
        query = query.filter(GroceryListItem.item_name.ilike(f"%{escaped_search}%", escape='\\'))

    # Apply ordering and pagination
    items = (
        query
        .order_by(GroceryListItem.id.desc())  # Most recently added first
        .limit(limit)
        .offset(offset)
        .all()
    )

    return items


def get_item_by_id(
    item_id: UUID,
    db: Session,
) -> GroceryListItem:
    """
    Get a single grocery item by ID.

    Retrieves a specific grocery item. Returns 404 if the item doesn't exist.
    Any authenticated user can read any item (shared/global reads).

    Args:
        item_id: UUID of the grocery item to retrieve
        db: Database session

    Returns:
        GroceryListItem: Requested grocery item

    Raises:
        HTTPException(404): If item doesn't exist
    """
    item = db.query(GroceryListItem).filter(GroceryListItem.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found"
        )

    return item


def update_item(
    item_id: UUID,
    current_user: User,
    db: Session,
    **update_fields,
) -> GroceryListItem:
    """
    Update a grocery item with partial data.

    Allows partial updates - only provided fields will be updated. Returns 404
    if the item doesn't exist or is not owned by the current user (owner-restricted writes).

    Supports explicitly clearing optional fields by setting them to None.

    Args:
        item_id: UUID of the grocery item to update
        current_user: Authenticated user performing the update
        db: Database session
        **update_fields: Fields to update (item_name, quantity, unit, target_store)

    Returns:
        GroceryListItem: Updated grocery item

    Raises:
        HTTPException(404): If item doesn't exist or is not owned by current user
        HTTPException(422): If validation fails
        HTTPException(500): If database error occurs
    """
    item = db.query(GroceryListItem).filter(GroceryListItem.id == item_id).first()

    # Return 404 if item doesn't exist OR is not owned by current user
    if not item or item.added_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found"
        )

    # Update only the fields that were provided
    # Using 'in' operator allows distinguishing between "not provided" and "explicitly set to None"
    if 'item_name' in update_fields:
        item.item_name = update_fields['item_name']
    if 'quantity' in update_fields:
        item.quantity = update_fields['quantity']
    if 'unit' in update_fields:
        item.unit = update_fields['unit']
    if 'target_store' in update_fields:
        item.target_store = update_fields['target_store']

    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during grocery item update for user {current_user.id}")
        logger.debug(f"Integrity error occurred during grocery item update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grocery item update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during grocery item update for user {current_user.id}")
        logger.debug(f"Database error occurred during grocery item update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the grocery item"
        )

    logger.info(
        f"Grocery item updated: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return item


def delete_item(
    item_id: UUID,
    current_user: User,
    db: Session,
) -> None:
    """
    Delete a grocery item.

    Removes the specified grocery item. Returns 404 if the item doesn't exist
    or is not owned by the current user (owner-restricted writes).

    Args:
        item_id: UUID of the grocery item to delete
        current_user: Authenticated user performing the deletion
        db: Database session

    Raises:
        HTTPException(404): If item doesn't exist or is not owned by current user
        HTTPException(500): If database error occurs
    """
    item = db.query(GroceryListItem).filter(GroceryListItem.id == item_id).first()

    # Return 404 if item doesn't exist OR is not owned by current user
    if not item or item.added_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found"
        )

    try:
        db.delete(item)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during grocery item deletion for user {current_user.id}")
        logger.debug(f"Database error occurred during grocery item deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the grocery item"
        )

    logger.info(
        f"Grocery item deleted: user_id={current_user.id}, "
        f"item_id={item_id}"
    )


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

        # Pre-validate all units before making any modifications (ensures atomic all-or-nothing)
        if create_inventory_item:
            for item in items:
                # Only validate items that will actually create inventory (not already purchased)
                if not item.purchased:
                    _validate_unit_for_inventory(item.unit, item.item_name)

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
                # (unit already validated in pre-validation phase above)
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


def get_items_by_store(
    db: Session,
    include_purchased: bool = False,
) -> dict:
    """
    Get grocery items grouped by target store.

    Returns items organized by their target store, with items lacking a
    target_store in a separate "unassigned" list. By default, only returns
    unpurchased items (include_purchased=False).

    Uses eager loading (selectinload) to avoid N+1 queries when accessing
    store relationships. Items are ordered by ID descending (most recent first)
    within each store group.

    Args:
        db: Database session
        include_purchased: If True, return all items; if False, only unpurchased (default: False)

    Returns:
        dict: {
            "stores": [
                {"store_id": UUID, "store_name": str, "items": [GroceryListItem, ...]},
                ...
            ],
            "unassigned": [GroceryListItem, ...]
        }
    """
    # Build query with eager loading to prevent N+1 queries
    query = db.query(GroceryListItem).options(selectinload(GroceryListItem.target_store_rel))

    # Apply purchased filter
    if not include_purchased:
        query = query.filter(GroceryListItem.purchased.is_(False))

    # Order by most recent first
    items = query.order_by(GroceryListItem.id.desc()).all()

    # Group items by store
    # Use dict to track stores: {store_id: {"store_id": UUID, "store_name": str, "items": [...]}}
    stores_dict = {}
    unassigned = []

    for item in items:
        if item.target_store is None:
            # Item has no target store
            unassigned.append(item)
        else:
            # Item has a target store
            store_id = item.target_store
            # Check if store relationship exists (handles dangling foreign key if store was deleted)
            if item.target_store_rel is None:
                # Store was deleted - treat as unassigned
                unassigned.append(item)
                continue

            if store_id not in stores_dict:
                # First time seeing this store - initialize group
                # Access the relationship to get store details (already eager-loaded)
                store = item.target_store_rel
                stores_dict[store_id] = {
                    "store_id": store_id,
                    "store_name": store.name,
                    "items": []
                }
            stores_dict[store_id]["items"].append(item)

    # Convert stores dict to list
    stores = list(stores_dict.values())

    return {
        "stores": stores,
        "unassigned": unassigned
    }
