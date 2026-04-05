"""
PreparedFood CRUD endpoints for FreshUp.

Provides endpoints for users to manage prepared foods (leftovers, batch prep,
component ingredients). Implements shareability-aware permissions where shared
items are visible to all users, but personal/reserved items are only visible
to their owner.

Logging Policy:
    User-provided item names are NOT logged as they may contain sensitive
    health information (e.g., dietary restrictions, medical meal prep).
    Logs include operational metadata (user_id, item_id, timestamps) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import or_

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.prepared_food import PreparedFood, PreparedFoodType
from src.db.models.inventory_item import StorageLocation, Shareability
from src.schemas.prepared_food import (
    PreparedFoodCreate,
    PreparedFoodUpdate,
    PreparedFoodResponse,
    PreparedFoodListResponse,
    PreparedFoodConsumptionResponse,
    TransferRequest,
)
from src.schemas.inventory import ConsumptionRequest
from src.schemas.validators import validate_enum_value
from src.middleware.auth import get_current_user
from src.routers.prepared_foods_helpers import (
    verify_prepared_food_ownership,
    raise_query_param_validation_error,
)
from src.services.prepared_foods_service import (
    create_prepared_food,
    consume_prepared_food,
    transfer_prepared_food,
    freeze_prepared_food,
    thaw_prepared_food,
)
from src.exceptions import DomainException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prepared-foods", tags=["prepared-foods"])


def get_accessible_prepared_food(
    item_id: UUID,
    current_user: User,
    db: Session,
) -> PreparedFood:
    """
    Retrieve a prepared food item with shareability-aware access control.

    Implements the authorization pattern where:
    - Shared items are accessible to all authenticated users
    - Personal/reserved items are only accessible to their owner

    This helper consolidates the authorization logic used across multiple
    action endpoints (consume, transfer, freeze, thaw).

    Args:
        item_id: UUID of the prepared food item to retrieve
        current_user: Authenticated user attempting to access the item
        db: Database session

    Returns:
        PreparedFood: The requested item if accessible

    Raises:
        HTTPException(404): If item doesn't exist or is not accessible to current user
    """
    item = (
        db.query(PreparedFood)
        .filter(
            PreparedFood.id == item_id,
            or_(
                PreparedFood.shareability == Shareability.shared.value,
                PreparedFood.prepared_by == current_user.id
            )
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prepared food item not found"
        )

    return item


@router.post("", response_model=PreparedFoodResponse, status_code=status.HTTP_201_CREATED)
def create_prepared_food_endpoint(
    item_data: PreparedFoodCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new prepared food item for the authenticated user.

    The prepared_by field is automatically set to the current user's ID,
    ignoring any value provided in the request body.

    Args:
        item_data: Prepared food data (name, type, servings, storage, etc.)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodResponse: Created prepared food item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If data integrity violation occurs
        HTTPException(422): If validation fails (invalid type, storage_location, etc.)
    """
    try:
        return create_prepared_food(item_data, current_user, db)
    except DomainException as e:
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        logger.error(f"Runtime error in create_prepared_food_endpoint: user_id={current_user.id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=list[PreparedFoodListResponse])
def list_prepared_foods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    type: Optional[str] = Query(default=None, description="Filter by type (complete_meal, batch_portion, component_ingredient)"),
    storage_location: Optional[str] = Query(default=None, description="Filter by storage location (pantry, fridge, freezer)"),
    shareability: Optional[str] = Query(default=None, description="Filter by shareability (shared, reserved, personal)"),
    expiring_soon: Optional[bool] = Query(default=None, description="Filter items expiring within 7 days"),
    expiring_within_days: Optional[int] = Query(default=None, ge=1, description="Filter items expiring within N days"),
    search: Optional[str] = Query(default=None, min_length=2, max_length=255, description="Search items by name (case-insensitive partial match)"),
):
    """
    List prepared food items with shareability-aware filtering and pagination.

    Returns shared items from ALL users, plus personal/reserved items only from
    the current user. This implements multi-user visibility for shared prepared
    foods while maintaining privacy for personal items.

    Supports pagination via limit and offset query parameters.
    Supports filtering by type, storage location, shareability, expiration status,
    and name search. Multiple filters combine with AND logic.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session
        limit: Maximum number of items to return (1-100, default 50)
        offset: Number of items to skip (default 0)
        type: Filter by type (must be valid PreparedFoodType enum value)
        storage_location: Filter by storage location (must be valid StorageLocation enum value)
        shareability: Filter by shareability (must be valid Shareability enum value)
        expiring_soon: Filter items expiring within 7 days (true/false)
        expiring_within_days: Filter items expiring within N days (overrides expiring_soon if both provided)
        search: Search items by name (case-insensitive partial match)

    Returns:
        list[PreparedFoodListResponse]: List of prepared food items matching filters

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If invalid enum value provided for type, storage_location, or shareability
    """
    # Shareability-aware base query:
    # - Include all items where shareability = 'shared' (from any user)
    # - Include items where prepared_by = current_user (personal/reserved items)
    query = db.query(PreparedFood).filter(
        or_(
            PreparedFood.shareability == Shareability.shared.value,
            PreparedFood.prepared_by == current_user.id
        )
    )

    # Apply type filter
    if type is not None:
        try:
            validate_enum_value("type", type, PreparedFoodType)
        except ValueError as e:
            raise_query_param_validation_error("type", str(e))
        query = query.filter(PreparedFood.type == type)

    # Apply storage_location filter
    if storage_location is not None:
        try:
            validate_enum_value("storage_location", storage_location, StorageLocation)
        except ValueError as e:
            raise_query_param_validation_error("storage_location", str(e))
        query = query.filter(PreparedFood.storage_location == storage_location)

    # Apply shareability filter
    if shareability is not None:
        try:
            validate_enum_value("shareability", shareability, Shareability)
        except ValueError as e:
            raise_query_param_validation_error("shareability", str(e))
        # When filtering by shareability, still respect base visibility rules
        # Example: If filtering for "personal", only show current user's personal items
        if shareability == Shareability.personal.value or shareability == Shareability.reserved.value:
            query = query.filter(
                PreparedFood.shareability == shareability,
                PreparedFood.prepared_by == current_user.id
            )
        else:
            # For "shared", show all shared items (already covered by base query)
            query = query.filter(PreparedFood.shareability == shareability)

    # Apply expiration filters
    # expiring_within_days takes precedence over expiring_soon if both provided
    if expiring_within_days is not None:
        expiration_cutoff = datetime.now(timezone.utc) + timedelta(days=expiring_within_days)
        query = query.filter(
            PreparedFood.estimated_expiration.isnot(None),
            PreparedFood.estimated_expiration <= expiration_cutoff
        )
    elif expiring_soon is not None and expiring_soon:
        # expiring_soon means within 7 days
        expiration_cutoff = datetime.now(timezone.utc) + timedelta(days=7)
        query = query.filter(
            PreparedFood.estimated_expiration.isnot(None),
            PreparedFood.estimated_expiration <= expiration_cutoff
        )

    # Apply name search filter (case-insensitive partial match)
    if search is not None:
        # Escape LIKE wildcards to prevent DoS via expensive pattern matching
        escaped_search = search.replace('%', r'\%').replace('_', r'\_')
        query = query.filter(PreparedFood.name.ilike(f"%{escaped_search}%", escape='\\'))

    # Apply ordering and pagination
    items = (
        query
        .order_by(PreparedFood.date_prepared.desc(), PreparedFood.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return items


@router.get("/{item_id}", response_model=PreparedFoodResponse)
def get_prepared_food(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single prepared food item by ID.

    Retrieves a specific prepared food item. Returns 404 if the item doesn't exist,
    or if the item is personal/reserved and belongs to a different user.

    Implements shareability-aware access:
    - Shared items are accessible to all users
    - Personal/reserved items are only accessible to their owner

    Args:
        item_id: UUID of the prepared food item to retrieve
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodResponse: Requested prepared food item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not accessible to current user
    """
    # Query item with shareability-aware access control
    item = (
        db.query(PreparedFood)
        .filter(
            PreparedFood.id == item_id,
            or_(
                PreparedFood.shareability == Shareability.shared.value,
                PreparedFood.prepared_by == current_user.id
            )
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prepared food item not found"
        )

    return item


@router.put("/{item_id}", response_model=PreparedFoodResponse)
def update_prepared_food(
    item_id: UUID,
    update_data: PreparedFoodUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a prepared food item with partial data.

    Allows partial updates - only provided fields will be updated. Returns 404
    if the item doesn't exist or belongs to a different user.

    Only the owner (prepared_by user) can update items, regardless of shareability.

    Args:
        item_id: UUID of the prepared food item to update
        update_data: Fields to update (all optional)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodResponse: Updated prepared food item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
        HTTPException(422): If validation fails (invalid type, storage_location, etc.)
    """
    # Verify item exists and belongs to current user
    item = verify_prepared_food_ownership(item_id, current_user, db)

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
        logger.error(f"Integrity error during prepared food update for user {current_user.id}")
        logger.debug(f"Integrity error occurred during prepared food update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prepared food update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during prepared food update for user {current_user.id}")
        logger.debug(f"Database error occurred during prepared food update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the prepared food item"
        )

    logger.info(
        f"Prepared food updated: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prepared_food(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a prepared food item.

    Removes the specified prepared food item. Returns 404 if the item doesn't exist
    or belongs to a different user.

    Only the owner (prepared_by user) can delete items, regardless of shareability.

    Args:
        item_id: UUID of the prepared food item to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    # Verify item exists and belongs to current user
    item = verify_prepared_food_ownership(item_id, current_user, db)

    try:
        db.delete(item)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during prepared food deletion for user {current_user.id}")
        logger.debug(f"Database error occurred during prepared food deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the prepared food item"
        )

    logger.info(
        f"Prepared food deleted: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return None


@router.post("/{item_id}/consume", response_model=PreparedFoodConsumptionResponse)
def consume_prepared_food_endpoint(
    item_id: UUID,
    consumption_data: ConsumptionRequest = ConsumptionRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Consume (decrement) prepared food servings with shareability-aware permissions.

    Decrements the item's servings_remaining by the specified amount. If servings reach
    zero and delete_when_empty is true (default), the item is deleted.

    Implements shareability-aware access control:
    - Shared items can be consumed by any authenticated user
    - Personal/reserved items can only be consumed by their owner (404 for non-owner)

    Args:
        item_id: UUID of the prepared food item to consume
        consumption_data: Amount to consume and deletion preference
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodConsumptionResponse: Status message, deletion flag, and updated item (if not deleted)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not accessible to current user
        HTTPException(400): If consumption amount exceeds available servings
        HTTPException(422): If amount is negative or zero
    """
    try:
        message, deleted, item = consume_prepared_food(item_id, consumption_data, current_user, db)

        return PreparedFoodConsumptionResponse(
            message=message,
            deleted=deleted,
            item=item
        )
    except DomainException as e:
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        logger.error(f"Runtime error in consume_prepared_food_endpoint: user_id={current_user.id}, item_id={item_id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{item_id}/transfer", response_model=PreparedFoodResponse)
def transfer_prepared_food_endpoint(
    item_id: UUID,
    transfer_data: TransferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Transfer prepared food to a different storage location with shareability-aware permissions.

    Updates the item's storage_location field to the specified location.

    Implements shareability-aware access control:
    - Shared items can be transferred by any authenticated user
    - Personal/reserved items can only be transferred by their owner (404 for non-owner)

    Args:
        item_id: UUID of the prepared food item to transfer
        transfer_data: Target storage location
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodResponse: Updated prepared food item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not accessible to current user
        HTTPException(422): If storage_location is invalid
    """
    try:
        # Use helper function for shareability-aware access control
        item = get_accessible_prepared_food(item_id, current_user, db)

        return transfer_prepared_food(item, transfer_data.storage_location, current_user, db)
    except DomainException as e:
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        logger.error(f"Runtime error in transfer_prepared_food_endpoint: user_id={current_user.id}, item_id={item_id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{item_id}/freeze", response_model=PreparedFoodResponse)
def freeze_prepared_food_endpoint(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Freeze a prepared food item (quick action) with shareability-aware permissions.

    Updates the item's storage location to "freezer". This endpoint is idempotent -
    freezing an already-frozen item simply ensures it's in the freezer.

    Implements shareability-aware access control:
    - Shared items can be frozen by any authenticated user
    - Personal/reserved items can only be frozen by their owner (404 for non-owner)

    Args:
        item_id: UUID of the prepared food item to freeze
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodResponse: Updated prepared food item with freezer location

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not accessible to current user
    """
    try:
        # Use helper function for shareability-aware access control
        item = get_accessible_prepared_food(item_id, current_user, db)

        return freeze_prepared_food(item, current_user, db)
    except DomainException as e:
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        logger.error(f"Runtime error in freeze_prepared_food_endpoint: user_id={current_user.id}, item_id={item_id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{item_id}/thaw", response_model=PreparedFoodResponse)
def thaw_prepared_food_endpoint(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Thaw a prepared food item (quick action) with shareability-aware permissions.

    Updates the item's storage location to "fridge". This endpoint is idempotent -
    thawing a non-frozen item simply ensures it's in the fridge.

    Implements shareability-aware access control:
    - Shared items can be thawed by any authenticated user
    - Personal/reserved items can only be thawed by their owner (404 for non-owner)

    Args:
        item_id: UUID of the prepared food item to thaw
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        PreparedFoodResponse: Updated prepared food item with fridge location

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not accessible to current user
    """
    try:
        # Use helper function for shareability-aware access control
        item = get_accessible_prepared_food(item_id, current_user, db)

        return thaw_prepared_food(item, current_user, db)
    except DomainException as e:
        raise HTTPException(status_code=e.http_status_code, detail=e.message)
    except RuntimeError as e:
        logger.error(f"Runtime error in thaw_prepared_food_endpoint: user_id={current_user.id}, item_id={item_id}")
        logger.debug(f"RuntimeError details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
