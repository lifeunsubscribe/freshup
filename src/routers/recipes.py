"""
Recipe CRUD endpoints for FreshUp.

Provides endpoints for managing recipes with nested ingredients.
Recipes are globally visible (all users can read) but only the creator
can update/delete their own recipes. System recipes (created_by=NULL)
cannot be edited or deleted by any user.

Logging Policy:
    Recipe names are NOT logged as they may contain sensitive health
    information (dietary restrictions, allergens). Logs include operational
    metadata (user_id, recipe_id, timestamps) for debugging while protecting
    user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.schemas.recipe import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeListResponse,
)
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_data: RecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new recipe with nested ingredients.

    The created_by field is automatically set to the current user's ID,
    ensuring proper ownership tracking.

    Args:
        recipe_data: Recipe data including name, source_type, and ingredients
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Created recipe with nested ingredients

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If data integrity violation occurs
        HTTPException(422): If validation fails (invalid source_type, etc.)
    """
    # Create recipe with created_by set to current user
    recipe_dict = recipe_data.model_dump(exclude={'ingredients'})
    new_recipe = Recipe(
        **recipe_dict,
        created_by=current_user.id,
    )

    db.add(new_recipe)

    try:
        # Flush to get recipe ID for ingredients
        db.flush()

        # Create nested ingredients
        for ingredient_data in recipe_data.ingredients:
            ingredient = RecipeIngredient(
                recipe_id=new_recipe.id,
                **ingredient_data.model_dump()
            )
            db.add(ingredient)

        # Commit atomically
        db.commit()
        db.refresh(new_recipe)

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during recipe creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during recipe creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipe creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during recipe creation for user {current_user.id}")
        logger.debug(f"Database error occurred during recipe creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the recipe"
        )

    logger.info(
        f"Recipe created: user_id={current_user.id}, "
        f"recipe_id={new_recipe.id}, ingredient_count={len(recipe_data.ingredients)}"
    )

    return new_recipe


@router.get("", response_model=list[RecipeListResponse])
def list_recipes(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=100, description="Maximum number of recipes to return"),
    offset: int = Query(default=0, ge=0, description="Number of recipes to skip"),
):
    """
    List all recipes with pagination (global read access).

    Returns all recipes in the system, ordered by most recently created first.
    This endpoint does not require authentication - recipes are globally visible.

    Args:
        db: Database session
        limit: Maximum number of recipes to return (1-100, default 100)
        offset: Number of recipes to skip (default 0)

    Returns:
        list[RecipeListResponse]: List of recipes without ingredient details
    """
    recipes = (
        db.query(Recipe)
        .order_by(Recipe.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return recipes


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(
    recipe_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a single recipe by ID with nested ingredients (global read access).

    Retrieves a specific recipe with all ingredients. This endpoint does not
    require authentication - recipes are globally visible.

    Args:
        recipe_id: UUID of the recipe to retrieve
        db: Database session

    Returns:
        RecipeResponse: Requested recipe with nested ingredients

    Raises:
        HTTPException(404): If recipe doesn't exist
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    return recipe


@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: UUID,
    update_data: RecipeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a recipe with partial data (ownership required).

    Allows partial updates - only provided fields will be updated. Returns 404
    if the recipe doesn't exist, belongs to a different user, or is a system
    recipe (created_by=NULL). This prevents enumeration attacks and protects
    system recipes from modification.

    Note: This endpoint does NOT support updating ingredients. Ingredient
    updates will be handled by a separate endpoint in a future iteration.

    Args:
        recipe_id: UUID of the recipe to update
        update_data: Fields to update (all optional)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Updated recipe with ingredients

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist, belongs to another user, or is a system recipe
        HTTPException(422): If validation fails (invalid source_type, etc.)
    """
    # Query recipe with ownership check
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()

    # Return 404 if recipe doesn't exist (prevents enumeration)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Return 404 if recipe is a system recipe (created_by is NULL)
    if recipe.created_by is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Return 404 if recipe belongs to another user (prevents enumeration)
    if recipe.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Update only the fields that were provided
    update_dict = update_data.model_dump(exclude_unset=True)

    # Apply updates
    for field, value in update_dict.items():
        setattr(recipe, field, value)

    try:
        db.commit()
        db.refresh(recipe)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during recipe update for user {current_user.id}")
        logger.debug(f"Integrity error occurred during recipe update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipe update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during recipe update for user {current_user.id}")
        logger.debug(f"Database error occurred during recipe update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the recipe"
        )

    logger.info(
        f"Recipe updated: user_id={current_user.id}, "
        f"recipe_id={recipe_id}"
    )

    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(
    recipe_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a recipe (ownership required).

    Removes the specified recipe and all associated ingredients (cascading delete).
    Returns 404 if the recipe doesn't exist, belongs to a different user, or is a
    system recipe (created_by=NULL). This prevents enumeration attacks and protects
    system recipes from deletion.

    Args:
        recipe_id: UUID of the recipe to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist, belongs to another user, or is a system recipe
    """
    # Query recipe with ownership check
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()

    # Return 404 if recipe doesn't exist (prevents enumeration)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Return 404 if recipe is a system recipe (created_by is NULL)
    if recipe.created_by is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Return 404 if recipe belongs to another user (prevents enumeration)
    if recipe.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    try:
        # Manually delete ingredients first (cascade not configured in DB)
        db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()

        # Delete the recipe
        db.delete(recipe)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during recipe deletion for user {current_user.id}")
        logger.debug(f"Database error occurred during recipe deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the recipe"
        )

    logger.info(
        f"Recipe deleted: user_id={current_user.id}, "
        f"recipe_id={recipe_id}"
    )

    return None
