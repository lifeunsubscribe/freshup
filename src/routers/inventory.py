"""
InventoryItem CRUD endpoints for FreshUp.

Provides endpoints for users to manage their kitchen inventory items.
All endpoints are scoped to the authenticated user's inventory.
"""

import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.inventory_item import InventoryItem, Category, StorageLocation, Shareability
from src.db.models.store import Store
from src.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
    SetPreferredStoreRequest,
    AddAvailableStoreRequest,
    UpdateShareabilityRequest,
    LowStockAlertItem,
    ConsumptionRequest,
    ConsumptionResponse,
)
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    item_data: InventoryItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new inventory item for the authenticated user.

    The added_by field is automatically set to the current user's ID,
    ignoring any value provided in the request body.

    Args:
        item_data: Inventory item data (name, quantity, unit, category, etc.)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Created inventory item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If data integrity violation occurs
        HTTPException(422): If validation fails (invalid unit, category, etc.)
    """
    # Create new inventory item with added_by set to current user
    # Ignore any added_by value from request body for security
    item_dict = item_data.model_dump(exclude={'added_by'})
    new_item = InventoryItem(
        **item_dict,
        added_by=current_user.id,
    )

    db.add(new_item)

    try:
        db.commit()
        db.refresh(new_item)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during inventory item creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during inventory item creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inventory item creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during inventory item creation for user {current_user.id}")
        logger.debug(f"Database error occurred during inventory item creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the inventory item"
        )

    logger.info(
        f"Inventory item created: user_id={current_user.id}, "
        f"item_name={item_data.name}, "
        f"item_id={new_item.id}"
    )

    return new_item


@router.get("", response_model=list[InventoryItemListResponse])
def list_inventory_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    category: Optional[str] = Query(default=None, description="Filter by category (e.g., produce, dairy, protein)"),
    storage_location: Optional[str] = Query(default=None, description="Filter by storage location (pantry, fridge, freezer)"),
    shareability: Optional[str] = Query(default=None, description="Filter by shareability (shared, reserved, personal)"),
    is_staple: Optional[bool] = Query(default=None, description="Filter by staple status"),
    expiring_soon: Optional[bool] = Query(default=None, description="Filter items expiring within 7 days"),
    expiring_within_days: Optional[int] = Query(default=None, ge=1, description="Filter items expiring within N days"),
    search: Optional[str] = Query(default=None, min_length=2, max_length=255, description="Search items by name (case-insensitive partial match)"),
):
    """
    List inventory items for the authenticated user with filtering and pagination.

    Returns items owned by the current user, ordered by most recently added first.
    Supports pagination via limit and offset query parameters.
    Supports filtering by category, storage location, shareability, staple status,
    expiration status, and name search. Multiple filters combine with AND logic.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session
        limit: Maximum number of items to return (1-100, default 50)
        offset: Number of items to skip (default 0)
        category: Filter by category (must be valid Category enum value)
        storage_location: Filter by storage location (must be valid StorageLocation enum value)
        shareability: Filter by shareability (must be valid Shareability enum value)
        is_staple: Filter by staple status (true/false)
        expiring_soon: Filter items expiring within 7 days (true/false)
        expiring_within_days: Filter items expiring within N days (overrides expiring_soon if both provided)
        search: Search items by name (case-insensitive partial match)

    Returns:
        list[InventoryItemListResponse]: List of user's inventory items matching filters

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If invalid enum value provided for category, storage_location, or shareability
    """
    # Start with base query filtering by user
    query = db.query(InventoryItem).filter(InventoryItem.added_by == current_user.id)

    # Apply category filter
    if category is not None:
        # Validate category enum
        valid_categories = [cat.value for cat in Category]
        if category not in valid_categories:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        query = query.filter(InventoryItem.category == category)

    # Apply storage_location filter
    if storage_location is not None:
        # Validate storage_location enum
        valid_locations = [loc.value for loc in StorageLocation]
        if storage_location not in valid_locations:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid storage_location. Must be one of: {', '.join(valid_locations)}"
            )
        query = query.filter(InventoryItem.storage_location == storage_location)

    # Apply shareability filter
    if shareability is not None:
        # Validate shareability enum
        valid_shareability = [share.value for share in Shareability]
        if shareability not in valid_shareability:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid shareability. Must be one of: {', '.join(valid_shareability)}"
            )
        query = query.filter(InventoryItem.shareability == shareability)

    # Apply is_staple filter
    if is_staple is not None:
        query = query.filter(InventoryItem.is_staple == is_staple)

    # Apply expiration filters
    # expiring_within_days takes precedence over expiring_soon if both provided
    if expiring_within_days is not None:
        expiration_cutoff = datetime.now(timezone.utc) + timedelta(days=expiring_within_days)
        query = query.filter(
            InventoryItem.expiration_date.isnot(None),
            InventoryItem.expiration_date <= expiration_cutoff
        )
    elif expiring_soon is not None and expiring_soon:
        # expiring_soon means within 7 days
        expiration_cutoff = datetime.now(timezone.utc) + timedelta(days=7)
        query = query.filter(
            InventoryItem.expiration_date.isnot(None),
            InventoryItem.expiration_date <= expiration_cutoff
        )

    # Apply name search filter (case-insensitive partial match)
    if search is not None:
        # Escape LIKE wildcards to prevent DoS via expensive pattern matching
        escaped_search = search.replace('%', r'\%').replace('_', r'\_')
        query = query.filter(InventoryItem.name.ilike(f"%{escaped_search}%", escape='\\'))

    # Apply ordering and pagination
    items = (
        query
        .order_by(InventoryItem.date_added.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return items


@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_inventory_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single inventory item by ID.

    Retrieves a specific inventory item. Returns 404 if the item doesn't exist
    or belongs to a different user (preventing cross-user access).

    Args:
        item_id: UUID of the inventory item to retrieve
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Requested inventory item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
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


@router.put("/{item_id}", response_model=InventoryItemResponse)
def update_inventory_item(
    item_id: UUID,
    update_data: InventoryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an inventory item with partial data.

    Allows partial updates - only provided fields will be updated. Returns 404
    if the item doesn't exist or belongs to a different user.

    Args:
        item_id: UUID of the inventory item to update
        update_data: Fields to update (all optional)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
        HTTPException(422): If validation fails (invalid unit, category, etc.)
    """
    # Query item with user ownership check
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

    # Update only the fields that were provided
    update_dict = update_data.model_dump(exclude_unset=True)

    # Apply updates
    for field, value in update_dict.items():
        setattr(item, field, value)

    try:
        db.commit()
        db.refresh(item)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during inventory item update for user {current_user.id}")
        logger.debug(f"Integrity error occurred during inventory item update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inventory item update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during inventory item update for user {current_user.id}")
        logger.debug(f"Database error occurred during inventory item update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the inventory item"
        )

    logger.info(
        f"Inventory item updated: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete an inventory item.

    Removes the specified inventory item. Returns 404 if the item doesn't exist
    or belongs to a different user.

    Args:
        item_id: UUID of the inventory item to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    # Query item with user ownership check
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

    try:
        db.delete(item)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during inventory item deletion for user {current_user.id}")
        logger.debug(f"Database error occurred during inventory item deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the inventory item"
        )

    logger.info(
        f"Inventory item deleted: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return None


@router.put("/{item_id}/preferred-store", response_model=InventoryItemResponse)
def set_preferred_store(
    item_id: UUID,
    request_data: SetPreferredStoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set the preferred store for an inventory item.

    Updates the preferred_store field for the specified inventory item.
    Validates that the store exists before assignment.

    Args:
        item_id: UUID of the inventory item to update
        request_data: Store ID to set as preferred
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item with store data

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist, belongs to another user, or store_id is invalid
    """
    # Validate store exists
    store = db.query(Store).filter(Store.id == request_data.store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Query item with user ownership check
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

    # Update preferred store
    item.preferred_store = request_data.store_id

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during preferred store update for user {current_user.id}")
        logger.debug(f"Database error occurred during preferred store update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the preferred store"
        )

    logger.info(
        f"Preferred store updated: user_id={current_user.id}, "
        f"item_id={item_id}, store_id={request_data.store_id}"
    )

    return item


@router.delete("/{item_id}/preferred-store", response_model=InventoryItemResponse)
def clear_preferred_store(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Clear the preferred store for an inventory item.

    Sets the preferred_store field to NULL for the specified inventory item.

    Args:
        item_id: UUID of the inventory item to update
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    # Query item with user ownership check
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

    # Clear preferred store
    item.preferred_store = None

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during preferred store clear for user {current_user.id}")
        logger.debug(f"Database error occurred during preferred store clear: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while clearing the preferred store"
        )

    logger.info(
        f"Preferred store cleared: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return item


@router.post("/{item_id}/available-stores", response_model=InventoryItemResponse, status_code=status.HTTP_200_OK)
def add_available_store(
    item_id: UUID,
    request_data: AddAvailableStoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a store to the available_at_stores list for an inventory item.

    Appends a store to the many-to-many relationship. If the store is already
    in the list, this operation is idempotent (no duplicate added).

    Args:
        item_id: UUID of the inventory item to update
        request_data: Store ID to add to available stores
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item with store data

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist, belongs to another user, or store_id is invalid
    """
    # Validate store exists
    store = db.query(Store).filter(Store.id == request_data.store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Query item with user ownership check
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

    # Add store to available_at_stores if not already present
    if store not in item.available_at_stores:
        item.available_at_stores.append(store)

        try:
            db.commit()
            db.refresh(item)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during available store addition for user {current_user.id}")
            logger.debug(f"Database error occurred during available store addition: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while adding the available store"
            )

        logger.info(
            f"Available store added: user_id={current_user.id}, "
            f"item_id={item_id}, store_id={request_data.store_id}"
        )
    else:
        logger.debug(
            f"Available store already exists: user_id={current_user.id}, "
            f"item_id={item_id}, store_id={request_data.store_id}"
        )

    return item


@router.delete("/{item_id}/available-stores/{store_id}", response_model=InventoryItemResponse)
def remove_available_store(
    item_id: UUID,
    store_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a store from the available_at_stores list for an inventory item.

    Removes a store from the many-to-many relationship. If the store is not
    in the list, this operation is idempotent (no error raised).

    Args:
        item_id: UUID of the inventory item to update
        store_id: Store ID to remove from available stores
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item with store data

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist, belongs to another user, or store_id is invalid
    """
    # Validate store exists
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )

    # Query item with user ownership check
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

    # Remove store from available_at_stores if present
    if store in item.available_at_stores:
        item.available_at_stores.remove(store)

        try:
            db.commit()
            db.refresh(item)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during available store removal for user {current_user.id}")
            logger.debug(f"Database error occurred during available store removal: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while removing the available store"
            )

        logger.info(
            f"Available store removed: user_id={current_user.id}, "
            f"item_id={item_id}, store_id={store_id}"
        )
    else:
        logger.debug(
            f"Available store not in list: user_id={current_user.id}, "
            f"item_id={item_id}, store_id={store_id}"
        )

    return item


@router.get("/alerts/low-stock", response_model=list[LowStockAlertItem])
def get_low_stock_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get staple items that are below their minimum threshold.

    Returns items where:
    - is_staple is True
    - minimum_threshold is set (not NULL)
    - quantity <= minimum_threshold

    Items are ordered by deficit (most urgent first).

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        list[LowStockAlertItem]: List of low-stock staple items with deficit amounts

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    # Query staple items below threshold
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.added_by == current_user.id,
            InventoryItem.is_staple == True,
            InventoryItem.minimum_threshold.isnot(None),
            InventoryItem.quantity <= InventoryItem.minimum_threshold,
        )
        .all()
    )

    # Build response with deficit calculation
    alert_items = []
    for item in items:
        alert_items.append(
            LowStockAlertItem(
                id=item.id,
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                minimum_threshold=item.minimum_threshold,
                deficit=item.minimum_threshold - item.quantity,
            )
        )

    # Sort by deficit descending (most urgent first)
    alert_items.sort(key=lambda x: x.deficit, reverse=True)

    return alert_items


@router.put("/{item_id}/shareability", response_model=InventoryItemResponse)
def update_shareability(
    item_id: UUID,
    request_data: UpdateShareabilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update shareability status for an inventory item.

    Sets the shareability status (shared/reserved/personal) and optionally
    a reserved note. When setting to "shared", reserved_note and reserved_for
    are automatically cleared. For "personal" and "reserved", the reserved_note
    can be set if provided.

    Args:
        item_id: UUID of the inventory item to update
        request_data: Shareability and optional reserved note
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
        HTTPException(422): If shareability is invalid or reserved_note exceeds 500 chars
    """
    # Query item with user ownership check
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

    # Update shareability
    item.shareability = request_data.shareability

    # Clear reserved fields when setting to "shared"
    if request_data.shareability == Shareability.shared.value:
        item.reserved_note = None
        item.reserved_for = None
    elif request_data.shareability == Shareability.personal.value:
        # For "personal", set the note if provided (allows personal notes)
        item.reserved_note = request_data.reserved_note
        item.reserved_for = None
    else:
        # For "reserved", set the note if provided
        item.reserved_note = request_data.reserved_note

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during shareability update for user {current_user.id}")
        logger.debug(f"Database error occurred during shareability update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating shareability"
        )

    logger.info(
        f"Shareability updated: user_id={current_user.id}, "
        f"item_id={item_id}, shareability={request_data.shareability}"
    )

    return item


@router.post("/{item_id}/freeze", response_model=InventoryItemResponse)
def freeze_inventory_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Freeze an inventory item (quick action).

    Updates the item's storage location to "freezer" and sets frozen_date to now.
    This endpoint is idempotent - freezing an already-frozen item updates the
    frozen_date to the current time.

    Args:
        item_id: UUID of the inventory item to freeze
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item with freezer location and frozen_date

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    # Query item with user ownership check
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

    # Update storage location and frozen date
    item.storage_location = StorageLocation.freezer.value
    item.frozen_date = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during freeze action for user {current_user.id}")
        logger.debug(f"Database error occurred during freeze action: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while freezing the inventory item"
        )

    logger.info(
        f"Inventory item frozen: user_id={current_user.id}, "
        f"item_id={item_id}, item_name={item.name}"
    )

    return item


@router.post("/{item_id}/thaw", response_model=InventoryItemResponse)
def thaw_inventory_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Thaw an inventory item (quick action).

    Updates the item's storage location to "fridge" and clears the frozen_date.
    This endpoint is idempotent - thawing a non-frozen item does not raise an error.

    Args:
        item_id: UUID of the inventory item to thaw
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        InventoryItemResponse: Updated inventory item with fridge location and cleared frozen_date

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    # Query item with user ownership check
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

    # Update storage location and clear frozen date
    item.storage_location = StorageLocation.fridge.value
    item.frozen_date = None

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during thaw action for user {current_user.id}")
        logger.debug(f"Database error occurred during thaw action: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while thawing the inventory item"
        )

    logger.info(
        f"Inventory item thawed: user_id={current_user.id}, "
        f"item_id={item_id}, item_name={item.name}"
    )

    return item


@router.post("/{item_id}/consume", response_model=ConsumptionResponse)
def consume_inventory_item(
    item_id: UUID,
    consumption_data: ConsumptionRequest = ConsumptionRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Consume (decrement) inventory item quantity.

    Decrements the item's quantity by the specified amount. If quantity reaches
    zero and delete_when_empty is true (default), the item is deleted.

    Args:
        item_id: UUID of the inventory item to consume
        consumption_data: Amount to consume and deletion preference
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        ConsumptionResponse: Status message, deletion flag, and updated item (if not deleted)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
        HTTPException(400): If consumption amount exceeds available quantity
        HTTPException(422): If amount is negative or zero
    """
    # Query item with user ownership check
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

    # Validate consumption amount doesn't exceed available quantity
    if consumption_data.amount > item.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot consume {consumption_data.amount} {item.unit}. Only {item.quantity} {item.unit} available."
        )

    # Calculate new quantity
    new_quantity = item.quantity - consumption_data.amount

    # Check if item should be deleted (exact zero match, relying on float precision)
    if new_quantity == 0 and consumption_data.delete_when_empty:
        # Delete the item
        try:
            db.delete(item)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during item consumption deletion for user {current_user.id}")
            logger.debug(f"Database error occurred during item consumption deletion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while deleting the consumed item"
            )

        logger.info(
            f"Inventory item consumed and deleted: user_id={current_user.id}, "
            f"item_id={item_id}, item_name={item.name}, amount={consumption_data.amount}"
        )

        return ConsumptionResponse(
            message=f"Consumed {consumption_data.amount} {item.unit}. Item deleted (quantity reached 0).",
            deleted=True,
            item=None
        )
    else:
        # Update quantity
        item.quantity = new_quantity

        try:
            db.commit()
            db.refresh(item)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during item consumption for user {current_user.id}")
            logger.debug(f"Database error occurred during item consumption: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while consuming the item"
            )

        logger.info(
            f"Inventory item consumed: user_id={current_user.id}, "
            f"item_id={item_id}, item_name={item.name}, amount={consumption_data.amount}, "
            f"new_quantity={new_quantity}"
        )

        return ConsumptionResponse(
            message=f"Consumed {consumption_data.amount} {item.unit}. {new_quantity} {item.unit} remaining.",
            deleted=False,
            item=item
        )
