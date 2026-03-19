"""
Recipe CRUD endpoints for FreshUp.

Provides endpoints for users to manage their recipes.
All endpoints are scoped to the authenticated user's recipes.

Logging Policy:
    User-provided recipe names are NOT logged as they may contain sensitive
    information (e.g., dietary preferences, cultural indicators).
    Logs include operational metadata (user_id, recipe_id) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func, or_, String

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.recipe import Recipe, SourceType
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
    Create a new recipe for the authenticated user.

    The created_by field is automatically set to the current user's ID,
    ignoring any value provided in the request body.

    Args:
        recipe_data: Recipe data (name, source_type, steps, etc.)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Created recipe

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If data integrity violation occurs
        HTTPException(422): If validation fails (invalid source_type, etc.)
    """
    # Create new recipe with created_by set to current user
    # Ignore any created_by value from request body for security
    recipe_dict = recipe_data.model_dump(exclude={'created_by'})
    new_recipe = Recipe(
        **recipe_dict,
        created_by=current_user.id,
    )

    db.add(new_recipe)

    try:
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
        f"recipe_id={new_recipe.id}"
    )

    return new_recipe


@router.get("", response_model=list[RecipeListResponse])
def list_recipes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of recipes to return"),
    offset: int = Query(default=0, ge=0, description="Number of recipes to skip"),
    source_type: Optional[str] = Query(default=None, description="Filter by source type (manual, hellofresh_card, etc.)"),
    tag: Optional[str] = Query(default=None, description="Filter by tag (case-insensitive match in tags array)"),
    max_cook_time: Optional[int] = Query(default=None, ge=0, description="Filter by maximum cook time in minutes"),
    max_prep_time: Optional[int] = Query(default=None, ge=0, description="Filter by maximum prep time in minutes"),
    search: Optional[str] = Query(default=None, min_length=2, max_length=255, description="Search recipes by name (case-insensitive partial match)"),
    has_variation: Optional[bool] = Query(default=None, description="Filter by variation groups presence (true/false)"),
):
    """
    List recipes for the authenticated user with filtering and pagination.

    Returns recipes created by the current user, ordered by most recently added first.
    Supports pagination via limit and offset query parameters.
    Supports filtering by source_type, tag, cook time, prep time, name search, and
    variation presence. Multiple filters combine with AND logic.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session
        limit: Maximum number of recipes to return (1-100, default 50)
        offset: Number of recipes to skip (default 0)
        source_type: Filter by source type (must be valid SourceType enum value)
        tag: Filter by tag (case-insensitive match in tags JSON array)
        max_cook_time: Filter by maximum cook time (recipes with cook_time_minutes <= max_cook_time)
        max_prep_time: Filter by maximum prep time (recipes with prep_time_minutes <= max_prep_time)
        search: Search recipes by name (case-insensitive partial match, LIKE wildcards escaped)
        has_variation: Filter by variation groups presence (true for recipes with variations, false for none)

    Returns:
        list[RecipeListResponse]: List of user's recipes matching filters

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If invalid enum value provided for source_type
    """
    # Start with base query filtering by user
    query = db.query(Recipe).filter(Recipe.created_by == current_user.id)

    # Apply source_type filter
    if source_type is not None:
        # Validate source_type enum
        valid_source_types = [st.value for st in SourceType]
        if source_type not in valid_source_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid source_type. Must be one of: {', '.join(valid_source_types)}"
            )
        query = query.filter(Recipe.source_type == source_type)

    # Apply tag filter (case-insensitive exact match in JSON array)
    # Match exact tag values only, not substrings within tags
    if tag is not None:
        # SQLite/PostgreSQL compatible: use LIKE with proper JSON delimiters
        # to ensure exact tag match (e.g., searching "an" won't match "italian")
        # Pattern matches: ["tag"] or ["tag", ...] or [..., "tag"] or [..., "tag", ...]
        # Note: JSON arrays may have spaces after commas: ["a", "b"]
        tag_lower = tag.lower()
        query = query.filter(
            or_(
                # Match at start: ["tag" or ["tag",
                func.lower(func.cast(Recipe.tags, String)).like(f'["{tag_lower}"%'),
                # Match in middle or end: , "tag", or , "tag"] (note space after comma)
                func.lower(func.cast(Recipe.tags, String)).like(f'%, "{tag_lower}"%')
            )
        )

    # Apply max_cook_time filter
    if max_cook_time is not None:
        query = query.filter(
            Recipe.cook_time_minutes.isnot(None),
            Recipe.cook_time_minutes <= max_cook_time
        )

    # Apply max_prep_time filter
    if max_prep_time is not None:
        query = query.filter(
            Recipe.prep_time_minutes.isnot(None),
            Recipe.prep_time_minutes <= max_prep_time
        )

    # Apply name search filter (case-insensitive partial match)
    if search is not None:
        # Escape LIKE wildcards to prevent DoS via expensive pattern matching
        escaped_search = search.replace('\\', r'\\').replace('%', r'\%').replace('_', r'\_')
        query = query.filter(Recipe.name.ilike(f"%{escaped_search}%", escape='\\'))

    # Apply has_variation filter
    if has_variation is not None:
        if has_variation:
            # Filter for recipes WITH variations (variation_groups is not null and not empty dict)
            # Check that the JSON is not null and has content (not just {})
            query = query.filter(
                Recipe.variation_groups.isnot(None),
                func.cast(Recipe.variation_groups, String) != '{}'
            )
        else:
            # Filter for recipes WITHOUT variations (variation_groups is null or empty dict)
            query = query.filter(
                or_(
                    Recipe.variation_groups.is_(None),
                    func.cast(Recipe.variation_groups, String) == '{}'
                )
            )

    # Apply ordering and pagination
    # Note: Recipe model doesn't have date_added, so we order by id (chronological proxy)
    recipes = (
        query
        .order_by(Recipe.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return recipes


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(
    recipe_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single recipe by ID.

    Retrieves a specific recipe. Returns 404 if the recipe doesn't exist
    or belongs to a different user (preventing cross-user access).

    Args:
        recipe_id: UUID of the recipe to retrieve
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Requested recipe

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
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


@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: UUID,
    update_data: RecipeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a recipe with partial data.

    Allows partial updates - only provided fields will be updated. Returns 404
    if the recipe doesn't exist or belongs to a different user.

    Args:
        recipe_id: UUID of the recipe to update
        update_data: Fields to update (all optional)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Updated recipe

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist or belongs to another user
        HTTPException(422): If validation fails (invalid source_type, etc.)
    """
    # Query recipe with user ownership check
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
    Delete a recipe.

    Removes the specified recipe. Returns 404 if the recipe doesn't exist
    or belongs to a different user.

    Args:
        recipe_id: UUID of the recipe to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist or belongs to another user
    """
    # Query recipe with user ownership check
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

    try:
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
