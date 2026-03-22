"""
Business logic for prepared food operations.

Separates business logic from router layer to improve testability
and maintain separation of concerns.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import HTTPException, status

from src.db.models.prepared_food import PreparedFood
from src.db.models.user import User
from src.schemas.prepared_food import PreparedFoodCreate

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
