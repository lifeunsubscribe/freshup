"""
InventoryItem CRUD endpoints for FreshUp.

Provides endpoints for users to manage their kitchen inventory items.
All endpoints are scoped to the authenticated user's inventory.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.inventory_item import InventoryItem
from src.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
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
        logger.debug(f"Integrity error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inventory item creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during inventory item creation for user {current_user.id}")
        logger.debug(f"Database error details: {str(e)}")
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
):
    """
    List inventory items for the authenticated user with pagination.

    Returns items owned by the current user, ordered by most recently added first.
    Supports pagination via limit and offset query parameters.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session
        limit: Maximum number of items to return (1-100, default 50)
        offset: Number of items to skip (default 0)

    Returns:
        list[InventoryItemListResponse]: List of user's inventory items

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.added_by == current_user.id)
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
        logger.debug(f"Integrity error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inventory item update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during inventory item update for user {current_user.id}")
        logger.debug(f"Database error details: {str(e)}")
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
        logger.debug(f"Database error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the inventory item"
        )

    logger.info(
        f"Inventory item deleted: user_id={current_user.id}, "
        f"item_id={item_id}"
    )

    return None
