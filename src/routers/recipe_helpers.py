"""
Helper functions for recipe ownership verification.

Centralizes ownership validation logic to reduce code duplication across
recipe CRUD endpoints and maintain consistent error handling.
"""

from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models.user import User
from src.db.models.recipe import Recipe


def verify_recipe_ownership(
    recipe_id: UUID,
    current_user: User,
    db: Session,
) -> Recipe:
    """
    Verify that a recipe exists and belongs to the current user.

    Used by update and delete endpoints that enforce ownership at the
    database query level for efficiency.

    Args:
        recipe_id: UUID of the recipe to verify
        current_user: Authenticated user making the request
        db: Database session

    Returns:
        Recipe: The recipe if it exists and belongs to current user

    Raises:
        HTTPException(404): If recipe doesn't exist or belongs to another user
    """
    recipe = (
        db.query(Recipe)
        .filter(
            Recipe.id == recipe_id,
            Recipe.created_by == current_user.id,
        )
        .first()
    )

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    return recipe


def verify_recipe_ownership_with_system_check(
    recipe_id: UUID,
    current_user: User,
    db: Session,
) -> Recipe:
    """
    Verify recipe ownership with explicit system recipe protection.

    Used by ingredient endpoints that need to distinguish between:
    - System recipes (created_by is NULL) → 403 Forbidden
    - Other users' recipes → 404 Not Found
    - Missing recipes → 404 Not Found

    This three-way distinction is important for security: we don't want to
    leak the existence of recipes by returning different status codes for
    "recipe exists but you can't modify it" vs "recipe doesn't exist".

    Args:
        recipe_id: UUID of the recipe to verify
        current_user: Authenticated user making the request
        db: Database session

    Returns:
        Recipe: The recipe if it exists, is not a system recipe, and belongs to current user

    Raises:
        HTTPException(404): If recipe doesn't exist or belongs to another user
        HTTPException(403): If recipe is a system recipe (created_by is NULL)
    """
    # Fetch recipe without ownership filter to distinguish error cases
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id)
        .first()
    )

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Check if recipe is a system recipe (cannot be modified)
    if recipe.created_by is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system recipes"
        )

    # Check if recipe belongs to current user
    if recipe.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    return recipe
