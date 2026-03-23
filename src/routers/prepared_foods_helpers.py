"""
Helper functions for prepared food ownership verification and error handling.

Centralizes ownership validation logic and error response formatting to reduce
code duplication across prepared food CRUD endpoints and maintain consistent
error handling.
"""

from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.db.models.user import User
from src.db.models.prepared_food import PreparedFood
from src.utils.ownership import verify_ownership


def verify_prepared_food_ownership(
    item_id: UUID,
    current_user: User,
    db: Session,
) -> PreparedFood:
    """
    Verify that a prepared food item exists and belongs to the current user.

    Used by update and delete endpoints that enforce ownership at the
    database query level for efficiency.

    Args:
        item_id: UUID of the prepared food item to verify
        current_user: Authenticated user making the request
        db: Database session

    Returns:
        PreparedFood: The item if it exists and belongs to current user

    Raises:
        HTTPException(404): If item doesn't exist or belongs to another user
    """
    return verify_ownership(
        entity_class=PreparedFood,
        entity_id=item_id,
        ownership_field='prepared_by',
        current_user=current_user,
        db=db,
        entity_name="Prepared food item"
    )


def raise_query_param_validation_error(field_name: str, error_message: str) -> None:
    """
    Raise a standardized 422 validation error for query parameter validation failures.

    This helper eliminates code duplication by providing a consistent error format
    for enum validation failures in query parameters. The error format matches
    FastAPI's validation error structure with a list of error details.

    Args:
        field_name: Name of the query parameter that failed validation
        error_message: Error message describing the validation failure

    Raises:
        HTTPException: Always raises 422 Unprocessable Entity with standardized detail format
    """
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[
            {
                "loc": ["query", field_name],
                "msg": error_message,
                "type": "value_error"
            }
        ]
    )
