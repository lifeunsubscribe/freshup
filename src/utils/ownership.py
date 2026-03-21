"""
Generic ownership verification utilities.

Provides reusable functions for verifying that database entities belong to
the authenticated user. Centralizes ownership check logic to reduce code
duplication across routers and maintain consistent error handling.
"""

from typing import Any, Type
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models.user import User


def verify_ownership(
    entity_class: Type,
    entity_id: UUID,
    ownership_field: str,
    current_user: User,
    db: Session,
    entity_name: str = "Resource"
) -> Any:
    """
    Verify that a database entity exists and belongs to the current user.

    Generic helper function that enforces ownership at the database query level
    for efficiency. Used by update and delete endpoints across different routers.

    Args:
        entity_class: SQLAlchemy model class to query (e.g., InventoryItem, Recipe)
        entity_id: UUID of the entity to verify
        ownership_field: Name of the field that contains the owner's user ID
                        (e.g., 'added_by', 'created_by', 'user_id')
        current_user: Authenticated user making the request
        db: Database session
        entity_name: Human-readable name for error messages (e.g., "Inventory item", "Recipe")

    Returns:
        The entity if it exists and belongs to current user

    Raises:
        HTTPException(404): If entity doesn't exist or belongs to another user

    Example:
        >>> item = verify_ownership(
        ...     InventoryItem,
        ...     item_id,
        ...     'added_by',
        ...     current_user,
        ...     db,
        ...     "Inventory item"
        ... )
    """
    # Build filter dynamically based on ownership field
    ownership_filter = {ownership_field: current_user.id}

    entity = (
        db.query(entity_class)
        .filter_by(id=entity_id, **ownership_filter)
        .first()
    )

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} not found"
        )

    return entity
