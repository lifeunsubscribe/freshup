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
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.user_recipe import UserRecipeRating
from src.db.models.inventory_item import InventoryItem
from src.schemas.recipe import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeListResponse,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeIngredientResponse,
    UserRecipeRatingCreate,
    UserRecipeRatingResponse,
    RecipeAggregateRatingsResponse,
    AdHocRecipeCreate,
)
from src.middleware.auth import get_current_user
from src.routers.recipe_helpers import (
    verify_recipe_ownership,
    verify_recipe_ownership_with_system_check,
    validate_step_index,
)
from src.services.recipe_service import trigger_persistence

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


@router.post("/ad-hoc", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_ad_hoc_recipe(
    recipe_data: AdHocRecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create an ad-hoc recipe from selected inventory items.

    Users can create recipes directly from what they just cooked by selecting
    ingredients from current inventory. Recipe ingredients are populated from
    inventory item names (canonical names, not inventory IDs). Optionally
    decrements inventory when the recipe is saved.

    The entire operation is atomic — if any validation fails, no recipe is
    created and no inventory is decremented. Validation occurs before any
    mutations to ensure data consistency.

    Args:
        recipe_data: Ad-hoc recipe data (name, steps, notes, tags, inventory_items, decrement_inventory)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Created recipe with source_type="ad_hoc"

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If any inventory_item_id not found or not owned by current user
        HTTPException(400): If units mismatch between recipe and inventory, or if decrement would result in negative quantity
        HTTPException(422): If validation fails (empty inventory_items list, etc.)
    """
    # Phase 1: Validate inventory item ownership and existence
    # Fetch all inventory items in a single query for efficiency
    inventory_item_ids = [item.inventory_item_id for item in recipe_data.inventory_items]
    inventory_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id.in_(inventory_item_ids),
            InventoryItem.added_by == current_user.id,
        )
        .all()
    )

    # Create a lookup map for quick access
    inventory_map = {item.id: item for item in inventory_items}

    # Validate all items exist and belong to current user
    for item_usage in recipe_data.inventory_items:
        if item_usage.inventory_item_id not in inventory_map:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory item {item_usage.inventory_item_id} not found or not owned by user"
            )

    # Phase 2: Validate unit consistency and quantity sufficiency
    # Validate units match between recipe and inventory (prevents data corruption)
    for item_usage in recipe_data.inventory_items:
        inventory_item = inventory_map[item_usage.inventory_item_id]

        # Check unit mismatch (case-insensitive comparison for better UX)
        # Handle None values to prevent AttributeError on .lower()
        # Note: This is defensive programming - the database has a NOT NULL constraint
        # on inventory_items.unit and Pydantic schema requires non-empty strings,
        # so None units cannot occur in practice. However, this defensive check ensures
        # safe handling if constraints change in the future. If both units are None,
        # they match (None == None evaluates to True), allowing unitless items.
        # See tests: test_create_ad_hoc_recipe_none_unit_behavior_documentation
        recipe_unit = item_usage.unit.lower() if item_usage.unit is not None else None
        inventory_unit = inventory_item.unit.lower() if inventory_item.unit is not None else None

        if recipe_unit != inventory_unit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unit mismatch for {inventory_item.name}: recipe uses \"{item_usage.unit}\" but inventory has \"{inventory_item.unit}\""
            )

    # Validate quantity sufficiency (if decrement is requested)
    # This happens BEFORE any mutations to ensure atomicity
    if recipe_data.decrement_inventory:
        for item_usage in recipe_data.inventory_items:
            inventory_item = inventory_map[item_usage.inventory_item_id]
            new_quantity = inventory_item.quantity - item_usage.quantity_used

            # Check if decrement would result in negative quantity
            if new_quantity < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot use {item_usage.quantity_used} {item_usage.unit} of {inventory_item.name}. Only {inventory_item.quantity} {inventory_item.unit} available."
                )

    # Phase 3: Create recipe and optionally decrement inventory
    # All validations passed — now perform mutations atomically
    try:
        # Create recipe with source_type="ad_hoc"
        new_recipe = Recipe(
            name=recipe_data.name,
            source_type=SourceType.ad_hoc.value,
            steps=recipe_data.steps,
            notes=recipe_data.notes,
            tags=recipe_data.tags,
            created_by=current_user.id,
        )
        db.add(new_recipe)
        db.flush()  # Generate recipe.id without committing

        # Create recipe ingredients from inventory item names
        for item_usage in recipe_data.inventory_items:
            inventory_item = inventory_map[item_usage.inventory_item_id]

            # Validate step_index bounds if provided
            validate_step_index(item_usage.step_index, len(recipe_data.steps))

            recipe_ingredient = RecipeIngredient(
                recipe_id=new_recipe.id,
                ingredient_name=inventory_item.name,  # Use canonical name from inventory
                quantity=item_usage.quantity_used,
                unit=item_usage.unit,
                step_index=item_usage.step_index,  # Pass through step_index from inventory usage
            )
            db.add(recipe_ingredient)

        # Decrement inventory if requested
        if recipe_data.decrement_inventory:
            for item_usage in recipe_data.inventory_items:
                inventory_item = inventory_map[item_usage.inventory_item_id]
                inventory_item.quantity -= item_usage.quantity_used

        # Commit all changes atomically
        db.commit()
        db.refresh(new_recipe)

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during ad-hoc recipe creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during ad-hoc recipe creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ad-hoc recipe creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during ad-hoc recipe creation for user {current_user.id}")
        logger.debug(f"Database error occurred during ad-hoc recipe creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the ad-hoc recipe"
        )

    logger.info(
        f"Ad-hoc recipe created: user_id={current_user.id}, "
        f"recipe_id={new_recipe.id}, decrement_inventory={recipe_data.decrement_inventory}"
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
    List all recipes with filtering and pagination.

    Returns all recipes in the system (global read), ordered by most recently added first.
    Supports pagination via limit and offset query parameters.
    Supports filtering by source_type, tag, cook time, prep time, name search, and
    variation presence. Multiple filters combine with AND logic.

    This endpoint provides global read access - all users can see all recipes.
    Only recipe creators can modify/delete their own recipes via PUT/DELETE endpoints.

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
        list[RecipeListResponse]: List of all recipes matching filters

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(422): If invalid enum value provided for source_type
    """
    # Start with base query (global read - no user filter)
    query = db.query(Recipe)

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
        # Escape LIKE wildcards to prevent DoS via expensive pattern matching
        escaped_tag = tag.replace('\\', r'\\').replace('%', r'\%').replace('_', r'\_')
        tag_lower = escaped_tag.lower()
        query = query.filter(
            or_(
                # Match at start: ["tag" or ["tag",
                func.lower(func.cast(Recipe.tags, String)).like(f'["{tag_lower}"%', escape='\\'),
                # Match in middle or end: , "tag", or , "tag"] (note space after comma)
                func.lower(func.cast(Recipe.tags, String)).like(f'%, "{tag_lower}"%', escape='\\')
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
    # Order by created_at to show most recently added recipes first
    recipes = (
        query
        .order_by(Recipe.created_at.desc())
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

    Retrieves a specific recipe. Returns 404 if the recipe doesn't exist.
    This endpoint provides global read access - any authenticated user can
    view any recipe. Only the recipe creator can modify/delete via PUT/DELETE.

    Args:
        recipe_id: UUID of the recipe to retrieve
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeResponse: Requested recipe

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist
    """
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
    # Verify recipe exists and belongs to current user
    recipe = verify_recipe_ownership(recipe_id, current_user, db)

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
    # Verify recipe exists and belongs to current user
    recipe = verify_recipe_ownership(recipe_id, current_user, db)

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


@router.post("/{recipe_id}/ingredients", response_model=RecipeIngredientResponse, status_code=status.HTTP_201_CREATED)
def add_recipe_ingredient(
    recipe_id: UUID,
    ingredient_data: RecipeIngredientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a new ingredient to a recipe.

    Creates a new RecipeIngredient entry for the specified recipe.
    Only the recipe owner can add ingredients. System recipes (created_by is NULL)
    cannot be modified.

    Args:
        recipe_id: UUID of the recipe to add ingredient to
        ingredient_data: Ingredient data (name, quantity, unit, etc.)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeIngredientResponse: Created ingredient

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If recipe is a system recipe (created_by is NULL)
        HTTPException(404): If recipe doesn't exist or belongs to another user
        HTTPException(400): If data integrity violation occurs
    """
    # Verify recipe exists, is not a system recipe, and belongs to current user
    recipe = verify_recipe_ownership_with_system_check(recipe_id, current_user, db)

    # Validate step_index bounds if provided
    validate_step_index(ingredient_data.step_index, len(recipe.steps))

    # Create new ingredient
    ingredient_dict = ingredient_data.model_dump()
    new_ingredient = RecipeIngredient(
        **ingredient_dict,
        recipe_id=recipe_id,
    )

    db.add(new_ingredient)

    try:
        db.commit()
        db.refresh(new_ingredient)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during ingredient creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during ingredient creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingredient creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during ingredient creation for user {current_user.id}")
        logger.debug(f"Database error occurred during ingredient creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the ingredient"
        )

    logger.info(
        f"Recipe ingredient created: user_id={current_user.id}, "
        f"recipe_id={recipe_id}, ingredient_id={new_ingredient.id}"
    )

    return new_ingredient


@router.put("/{recipe_id}/ingredients/{ingredient_id}", response_model=RecipeIngredientResponse)
def update_recipe_ingredient(
    recipe_id: UUID,
    ingredient_id: UUID,
    update_data: RecipeIngredientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a recipe ingredient with partial data.

    Allows partial updates - only provided fields will be updated.
    Only the recipe owner can update ingredients. System recipes (created_by is NULL)
    cannot be modified.

    Args:
        recipe_id: UUID of the recipe containing the ingredient
        ingredient_id: UUID of the ingredient to update
        update_data: Fields to update (all optional)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeIngredientResponse: Updated ingredient

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If recipe is a system recipe (created_by is NULL)
        HTTPException(404): If recipe doesn't exist, belongs to another user, or ingredient not found
        HTTPException(400): If data integrity violation occurs
    """
    # Verify recipe exists, is not a system recipe, and belongs to current user
    recipe = verify_recipe_ownership_with_system_check(recipe_id, current_user, db)

    # Query ingredient and verify it belongs to the recipe
    ingredient = (
        db.query(RecipeIngredient)
        .filter(
            RecipeIngredient.id == ingredient_id,
            RecipeIngredient.recipe_id == recipe_id,
        )
        .first()
    )

    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )

    # Validate step_index bounds if provided
    validate_step_index(update_data.step_index, len(recipe.steps))

    # Update only the fields that were provided
    update_dict = update_data.model_dump(exclude_unset=True)

    # Apply updates
    for field, value in update_dict.items():
        setattr(ingredient, field, value)

    try:
        db.commit()
        db.refresh(ingredient)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during ingredient update for user {current_user.id}")
        logger.debug(f"Integrity error occurred during ingredient update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingredient update failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during ingredient update for user {current_user.id}")
        logger.debug(f"Database error occurred during ingredient update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the ingredient"
        )

    logger.info(
        f"Recipe ingredient updated: user_id={current_user.id}, "
        f"recipe_id={recipe_id}, ingredient_id={ingredient_id}"
    )

    return ingredient


@router.delete("/{recipe_id}/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_ingredient(
    recipe_id: UUID,
    ingredient_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a recipe ingredient.

    Removes the specified ingredient from a recipe.
    Only the recipe owner can delete ingredients. System recipes (created_by is NULL)
    cannot be modified.

    Args:
        recipe_id: UUID of the recipe containing the ingredient
        ingredient_id: UUID of the ingredient to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If recipe is a system recipe (created_by is NULL)
        HTTPException(404): If recipe doesn't exist, belongs to another user, or ingredient not found
    """
    # Verify recipe exists, is not a system recipe, and belongs to current user
    recipe = verify_recipe_ownership_with_system_check(recipe_id, current_user, db)

    # Query ingredient and verify it belongs to the recipe
    ingredient = (
        db.query(RecipeIngredient)
        .filter(
            RecipeIngredient.id == ingredient_id,
            RecipeIngredient.recipe_id == recipe_id,
        )
        .first()
    )

    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found"
        )

    try:
        db.delete(ingredient)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during ingredient deletion for user {current_user.id}")
        logger.debug(f"Database error occurred during ingredient deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the ingredient"
        )

    logger.info(
        f"Recipe ingredient deleted: user_id={current_user.id}, "
        f"recipe_id={recipe_id}, ingredient_id={ingredient_id}"
    )

    return None


@router.post("/{recipe_id}/rate", response_model=UserRecipeRatingResponse, status_code=status.HTTP_200_OK)
def rate_recipe(
    recipe_id: UUID,
    rating_data: UserRecipeRatingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update a rating for a recipe (upsert behavior).

    Each user can have only one rating per recipe. If a rating already exists,
    this endpoint will update it. Otherwise, it creates a new rating.

    Args:
        recipe_id: UUID of the recipe to rate
        rating_data: Rating data (rating value, is_favorite, notes)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        UserRecipeRatingResponse: Created or updated rating

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist
        HTTPException(422): If rating value is out of range (0.0-5.0)
    """
    # Verify recipe exists (no ownership check - any user can rate any recipe)
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Check if user already has a rating for this recipe
    existing_rating = (
        db.query(UserRecipeRating)
        .filter(
            UserRecipeRating.user_id == current_user.id,
            UserRecipeRating.recipe_id == recipe_id,
        )
        .first()
    )

    if existing_rating:
        # Update existing rating
        update_dict = rating_data.model_dump()
        for field, value in update_dict.items():
            setattr(existing_rating, field, value)

        try:
            db.commit()
            db.refresh(existing_rating)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during rating update for user {current_user.id}")
            logger.debug(f"Database error occurred during rating update: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating the rating"
            )

        logger.info(
            f"Recipe rating updated: user_id={current_user.id}, "
            f"recipe_id={recipe_id}, rating_id={existing_rating.id}"
        )

        rating_result = existing_rating
    else:
        # Create new rating
        new_rating = UserRecipeRating(
            user_id=current_user.id,
            recipe_id=recipe_id,
            **rating_data.model_dump()
        )
        db.add(new_rating)

        try:
            db.commit()
            db.refresh(new_rating)
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error during rating creation for user {current_user.id}")
            logger.debug(f"Integrity error occurred during rating creation: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating creation failed due to data integrity violation"
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during rating creation for user {current_user.id}")
            logger.debug(f"Database error occurred during rating creation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while creating the rating"
            )

        logger.info(
            f"Recipe rating created: user_id={current_user.id}, "
            f"recipe_id={recipe_id}, rating_id={new_rating.id}"
        )

        rating_result = new_rating

    # Trigger persistence if user bookmarked/liked the recipe
    # Phase 2.5B: bookmarking/liking makes recipes permanent
    # This prevents cleanup of recipes users have shown interest in
    if rating_data.is_favorite:
        try:
            trigger_persistence(recipe, db)
        except SQLAlchemyError as e:
            logger.error(f"Failed to trigger persistence for recipe {recipe_id}", exc_info=e)
            # Don't fail the rating operation if persistence fails
            # The rating was already saved successfully

    return rating_result


@router.get("/{recipe_id}/my-rating", response_model=UserRecipeRatingResponse)
def get_my_rating(
    recipe_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current user's rating for a recipe.

    Returns the authenticated user's rating for the specified recipe.
    Returns 404 if the user hasn't rated this recipe yet.

    Args:
        recipe_id: UUID of the recipe
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        UserRecipeRatingResponse: User's rating for this recipe

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist or user hasn't rated it
    """
    # Verify recipe exists
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Get user's rating
    rating = (
        db.query(UserRecipeRating)
        .filter(
            UserRecipeRating.user_id == current_user.id,
            UserRecipeRating.recipe_id == recipe_id,
        )
        .first()
    )

    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rating not found"
        )

    return rating


@router.delete("/{recipe_id}/my-rating", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_rating(
    recipe_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete the current user's rating for a recipe.

    Removes the authenticated user's rating for the specified recipe.
    Returns 204 even if no rating exists (idempotent behavior).

    Args:
        recipe_id: UUID of the recipe
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist
    """
    # Verify recipe exists
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Get user's rating (if exists)
    rating = (
        db.query(UserRecipeRating)
        .filter(
            UserRecipeRating.user_id == current_user.id,
            UserRecipeRating.recipe_id == recipe_id,
        )
        .first()
    )

    if rating:
        try:
            db.delete(rating)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during rating deletion for user {current_user.id}")
            logger.debug(f"Database error occurred during rating deletion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while deleting the rating"
            )

        logger.info(
            f"Recipe rating deleted: user_id={current_user.id}, "
            f"recipe_id={recipe_id}"
        )

    return None


@router.get("/{recipe_id}/ratings", response_model=RecipeAggregateRatingsResponse)
def get_recipe_ratings(
    recipe_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get aggregate rating statistics for a recipe.

    Returns the average rating, total rating count, and favorite count
    across all users who have rated this recipe. This is a shared read
    endpoint - all users can see aggregate stats for any recipe.

    Args:
        recipe_id: UUID of the recipe
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        RecipeAggregateRatingsResponse: Aggregate rating statistics

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If recipe doesn't exist
    """
    # Verify recipe exists
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

    # Calculate aggregate statistics across all users
    # - average_rating: Average of all non-null rating values (func.avg automatically excludes nulls)
    # - rating_count: Count of rows where rating is not None (users who provided numeric ratings)
    # - favorite_count: Count of rows where is_favorite is True (users who favorited)
    # Note: Users can favorite without rating (rating=None), so favorite_count may exceed rating_count
    stats = (
        db.query(
            func.avg(UserRecipeRating.rating).label('average_rating'),
            func.count(UserRecipeRating.id).filter(UserRecipeRating.rating.isnot(None)).label('rating_count'),
            func.count(UserRecipeRating.id).filter(UserRecipeRating.is_favorite.is_(True)).label('favorite_count'),
        )
        .filter(UserRecipeRating.recipe_id == recipe_id)
        .first()
    )

    # Extract values (handle None for average when no ratings)
    # Note: count() always returns an integer (0 if no matches), never None
    average_rating = stats.average_rating if stats.average_rating is not None else None
    rating_count = stats.rating_count
    favorite_count = stats.favorite_count

    return RecipeAggregateRatingsResponse(
        average_rating=average_rating,
        rating_count=rating_count,
        favorite_count=favorite_count,
    )
