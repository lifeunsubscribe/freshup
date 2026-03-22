"""
Business logic for prepared food operations.

Separates business logic from router layer to improve testability
and maintain separation of concerns.
"""

import logging
import math
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import or_
from fastapi import HTTPException, status

from src.constants import FLOAT_COMPARISON_TOLERANCE
from src.db.models.prepared_food import PreparedFood
from src.db.models.user import User
from src.db.models.inventory_item import StorageLocation, Shareability
from src.schemas.prepared_food import PreparedFoodCreate
from src.schemas.inventory import ConsumptionRequest

logger = logging.getLogger(__name__)


def create_prepared_food(
    item_data: PreparedFoodCreate,
    current_user: User,
    db: Session,
) -> PreparedFood:
    """
    Create a new prepared food item for the authenticated user.

    The prepared_by field is automatically set to the current user's ID,
    ensuring proper ownership tracking.

    Args:
        item_data: Prepared food data (name, type, servings, etc.)
        current_user: Authenticated user creating the item
        db: Database session

    Returns:
        PreparedFood: Created prepared food item

    Raises:
        HTTPException(400): If data integrity violation occurs
        HTTPException(500): If database error occurs
    """
    # Create new prepared food item with prepared_by set to current user
    item_dict = item_data.model_dump()
    new_item = PreparedFood(
        **item_dict,
        prepared_by=current_user.id,
    )

    db.add(new_item)

    try:
        db.commit()
        db.refresh(new_item)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during prepared food creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during prepared food creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prepared food creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during prepared food creation for user {current_user.id}")
        logger.debug(f"Database error occurred during prepared food creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the prepared food item"
        )

    logger.info(
        f"Prepared food created: user_id={current_user.id}, "
        f"item_id={new_item.id}"
    )

    return new_item


def consume_prepared_food(
    item_id: UUID,
    consumption_data: ConsumptionRequest,
    current_user: User,
    db: Session,
) -> tuple[str, bool, PreparedFood | None]:
    """
    Consume (decrement) prepared food servings with shareability-aware permissions.

    Implements shareability-aware access control:
    - Shared items can be consumed by any authenticated user
    - Personal/reserved items can only be consumed by their owner

    Decrements servings_remaining by the specified amount. If servings reach
    zero and delete_when_empty is true (default), the item is deleted.

    Args:
        item_id: UUID of the prepared food item to consume
        consumption_data: Amount to consume and deletion preference
        current_user: Authenticated user consuming the item
        db: Database session

    Returns:
        tuple[str, bool, PreparedFood | None]: (message, deleted, item)
            - message: Status message describing the action
            - deleted: True if item was deleted, False otherwise
            - item: Updated PreparedFood item, or None if deleted

    Raises:
        HTTPException(404): If item doesn't exist or is not accessible to current user
        HTTPException(400): If consumption amount exceeds available servings
    """
    # Shareability-aware fetch: shared items accessible to all, personal/reserved only to owner
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

    # Validate consumption amount doesn't exceed available servings
    # Use tolerance to handle floating-point precision issues
    if consumption_data.amount > item.servings_remaining + FLOAT_COMPARISON_TOLERANCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot consume {consumption_data.amount} servings. Only {item.servings_remaining} servings available."
        )

    # Calculate new servings count
    new_servings = item.servings_remaining - consumption_data.amount

    # Check if item should be deleted (using math.isclose for proper float comparison)
    # Handles both "effectively zero" and negative edge cases from floating-point rounding
    if (math.isclose(new_servings, 0.0, abs_tol=FLOAT_COMPARISON_TOLERANCE) or new_servings < 0) and consumption_data.delete_when_empty:
        # Delete the item
        try:
            db.delete(item)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during prepared food consumption deletion for user {current_user.id}")
            logger.debug(f"Database error occurred during prepared food consumption deletion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while deleting the consumed item"
            )

        logger.info(
            f"Prepared food consumed and deleted: user_id={current_user.id}, "
            f"item_id={item_id}, amount={consumption_data.amount}"
        )

        return (
            f"Consumed {consumption_data.amount} servings. Item deleted (servings reached 0).",
            True,
            None
        )
    else:
        # Update servings - clamp to 0.0 if negative due to floating-point precision
        item.servings_remaining = max(0.0, new_servings)

        try:
            db.commit()
            db.refresh(item)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during prepared food consumption for user {current_user.id}")
            logger.debug(f"Database error occurred during prepared food consumption: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while consuming the item"
            )

        logger.info(
            f"Prepared food consumed: user_id={current_user.id}, "
            f"item_id={item_id}, amount={consumption_data.amount}, "
            f"new_servings={new_servings}"
        )

        return (
            f"Consumed {consumption_data.amount} servings. {item.servings_remaining} servings remaining.",
            False,
            item
        )


def transfer_prepared_food(
    item: PreparedFood,
    storage_location: str,
    current_user: User,
    db: Session,
) -> PreparedFood:
    """
    Transfer prepared food to a different storage location.

    Updates the storage_location field for the specified item.
    Implements shareability-aware access: shared items can be transferred by any user,
    personal/reserved items only by owner (access control verified by caller).

    Args:
        item: PreparedFood item to transfer (access control already verified)
        storage_location: Target storage location (pantry, fridge, freezer)
        current_user: Authenticated user performing the transfer
        db: Database session

    Returns:
        PreparedFood: Updated prepared food item

    Raises:
        HTTPException(500): If database error occurs
    """
    # Update storage location
    item.storage_location = storage_location

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during prepared food transfer for user {current_user.id}")
        logger.debug(f"Database error occurred during prepared food transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while transferring the prepared food item"
        )

    logger.info(
        f"Prepared food transferred: user_id={current_user.id}, "
        f"item_id={item.id}, storage_location={storage_location}"
    )

    return item


def freeze_prepared_food(
    item: PreparedFood,
    current_user: User,
    db: Session,
) -> PreparedFood:
    """
    Freeze a prepared food item (quick action).

    Updates the item's storage location to "freezer".
    Implements shareability-aware access: shared items can be frozen by any user,
    personal/reserved items only by owner (access control verified by caller).

    Args:
        item: PreparedFood item to freeze (access control already verified)
        current_user: Authenticated user performing the freeze
        db: Database session

    Returns:
        PreparedFood: Updated prepared food item with freezer location

    Raises:
        HTTPException(500): If database error occurs
    """
    # Update storage location to freezer
    item.storage_location = StorageLocation.freezer.value

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during prepared food freeze for user {current_user.id}")
        logger.debug(f"Database error occurred during prepared food freeze: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while freezing the prepared food item"
        )

    logger.info(
        f"Prepared food frozen: user_id={current_user.id}, "
        f"item_id={item.id}"
    )

    return item


def thaw_prepared_food(
    item: PreparedFood,
    current_user: User,
    db: Session,
) -> PreparedFood:
    """
    Thaw a prepared food item (quick action).

    Updates the item's storage location to "fridge".
    Implements shareability-aware access: shared items can be thawed by any user,
    personal/reserved items only by owner (access control verified by caller).

    Args:
        item: PreparedFood item to thaw (access control already verified)
        current_user: Authenticated user performing the thaw
        db: Database session

    Returns:
        PreparedFood: Updated prepared food item with fridge location

    Raises:
        HTTPException(500): If database error occurs
    """
    # Update storage location to fridge
    item.storage_location = StorageLocation.fridge.value

    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during prepared food thaw for user {current_user.id}")
        logger.debug(f"Database error occurred during prepared food thaw: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while thawing the prepared food item"
        )

    logger.info(
        f"Prepared food thawed: user_id={current_user.id}, "
        f"item_id={item.id}"
    )

    return item
