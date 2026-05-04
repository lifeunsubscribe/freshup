"""
Menu CRUD endpoints for FreshUp.

Provides endpoints for users to manage their menus (manual and auto-generated).
All endpoints are scoped to the authenticated user's menus.

Logging Policy:
    User-provided menu names are NOT logged as they may contain sensitive
    information (e.g., dietary preferences, cultural indicators).
    Logs include operational metadata (user_id, menu_id) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.recipe import Recipe
from src.middleware.auth import get_current_user
from src.schemas.menu import (
    MenuCreate,
    MenuUpdate,
    MenuResponse,
    MenuListResponse,
    MenuRecipeCreate,
    MenuRecipeResponse,
    MenuRecipesResponse,
    MenuGenerateRequest,
    MenuGenerateResponse,
)
from src.schemas.recipe import RecipeResponse, RecipeListResponse
from src.services import menu_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get("", response_model=MenuListResponse)
def get_menus(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all menus for the authenticated user, ordered by sort_order.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        MenuListResponse: List of user's menus

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    try:
        menus = menu_service.get_user_menus(current_user.id, db)
        return MenuListResponse(menus=menus, total=len(menus))
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving menus for user {current_user.id}")
        logger.debug(f"Database error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menus"
        )


@router.post("", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
def create_menu(
    menu_data: MenuCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new manual menu for the authenticated user.

    Args:
        menu_data: Menu data (name, description, filter_rules, etc.)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        MenuResponse: Created menu

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If data integrity violation occurs
    """
    try:
        # Convert filter_rules to dict if provided
        filter_rules_dict = None
        if menu_data.filter_rules:
            filter_rules_dict = menu_data.filter_rules.model_dump()

        menu = menu_service.create_menu(
            user_id=current_user.id,
            name=menu_data.name,
            description=menu_data.description,
            filter_rules=filter_rules_dict,
            is_auto_generated=menu_data.is_auto_generated,
            cover_image=menu_data.cover_image,
            sort_order=menu_data.sort_order,
            db=db,
        )
        return menu
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during menu creation for user {current_user.id}")
        logger.debug(f"Integrity error occurred during menu creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Menu creation failed due to data integrity violation"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during menu creation for user {current_user.id}")
        logger.debug(f"Database error occurred during menu creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create menu"
        )


@router.put("/{menu_id}", response_model=MenuResponse)
def update_menu(
    menu_id: UUID,
    menu_data: MenuUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing menu.

    Only the menu owner can update it. Returns 404 if menu doesn't exist or user doesn't own it.

    Args:
        menu_id: Menu ID to update
        menu_data: Updated menu data
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        MenuResponse: Updated menu

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If menu not found or user doesn't own it
    """
    menu = menu_service.get_menu_by_id(menu_id, current_user.id, db)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    try:
        # Convert filter_rules to dict if provided
        filter_rules_dict = None
        if menu_data.filter_rules is not None:
            filter_rules_dict = menu_data.filter_rules.model_dump()

        updated_menu = menu_service.update_menu(
            menu=menu,
            name=menu_data.name,
            description=menu_data.description,
            filter_rules=filter_rules_dict,
            sort_order=menu_data.sort_order,
            db=db,
        )
        return updated_menu
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during menu update for menu {menu_id}")
        logger.debug(f"Database error occurred during menu update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update menu"
        )


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu(
    menu_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a menu and all its MenuRecipe entries (cascade).

    Only the menu owner can delete it. Returns 404 if menu doesn't exist or user doesn't own it.

    Args:
        menu_id: Menu ID to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If menu not found or user doesn't own it
    """
    menu = menu_service.get_menu_by_id(menu_id, current_user.id, db)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    try:
        menu_service.delete_menu(menu, db)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during menu deletion for menu {menu_id}")
        logger.debug(f"Database error occurred during menu deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete menu"
        )


@router.get("/{menu_id}/recipes", response_model=MenuRecipesResponse)
def get_menu_recipes(
    menu_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get recipes in a menu with pagination.

    Only the menu owner can view its recipes. Returns 404 if menu doesn't exist or user doesn't own it.

    Args:
        menu_id: Menu ID to get recipes for
        offset: Pagination offset (default 0)
        limit: Pagination limit (default 50, max 100)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        MenuRecipesResponse: Paginated list of recipes in the menu

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If menu not found or user doesn't own it
    """
    menu = menu_service.get_menu_by_id(menu_id, current_user.id, db)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    try:
        recipes, total = menu_service.get_menu_recipes(menu_id, db, offset=offset, limit=limit)
        # Convert Recipe objects to RecipeListResponse
        recipe_list = [RecipeListResponse.model_validate(r) for r in recipes]
        return MenuRecipesResponse(recipes=recipe_list, total=total)
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving recipes for menu {menu_id}")
        logger.debug(f"Database error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve menu recipes"
        )


@router.post("/{menu_id}/recipes", response_model=MenuRecipeResponse, status_code=status.HTTP_201_CREATED)
def add_recipe_to_menu(
    menu_id: UUID,
    recipe_data: MenuRecipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a recipe to a menu.

    Sets manually_added=true if the recipe doesn't match the menu's filter rules.
    Only the menu owner can add recipes. Returns 404 if menu doesn't exist or user doesn't own it.

    Args:
        menu_id: Menu ID to add recipe to
        recipe_data: Recipe data (recipe_id, sort_order)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        MenuRecipeResponse: Created MenuRecipe entry

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If menu or recipe not found, or user doesn't own menu
        HTTPException(400): If recipe already in menu (duplicate)
    """
    menu = menu_service.get_menu_by_id(menu_id, current_user.id, db)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    try:
        menu_recipe = menu_service.add_recipe_to_menu(
            menu=menu,
            recipe_id=recipe_data.recipe_id,
            sort_order=recipe_data.sort_order,
            db=db,
        )
        return menu_recipe
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error adding recipe to menu {menu_id}")
        logger.debug(f"Integrity error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipe already in menu"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error adding recipe to menu {menu_id}")
        logger.debug(f"Database error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add recipe to menu"
        )


@router.delete("/{menu_id}/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_recipe_from_menu(
    menu_id: UUID,
    recipe_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a recipe from a menu.

    Sets manually_removed=true if the recipe matches the menu's filter rules (instead of deleting).
    Otherwise, deletes the MenuRecipe entry.
    Only the menu owner can remove recipes. Returns 404 if menu doesn't exist or user doesn't own it.

    Args:
        menu_id: Menu ID to remove recipe from
        recipe_id: Recipe ID to remove
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If menu or recipe not found, or user doesn't own menu
    """
    menu = menu_service.get_menu_by_id(menu_id, current_user.id, db)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    try:
        menu_service.remove_recipe_from_menu(menu, recipe_id, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error removing recipe from menu {menu_id}")
        logger.debug(f"Database error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove recipe from menu"
        )


@router.post("/generate", response_model=MenuGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_menus(
    request: MenuGenerateRequest = MenuGenerateRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Auto-generate menus from user's behavioral patterns.

    Detects tag patterns from saved recipes (>= min_saves) and creates menus with filter rules.
    Populates menus with user's bookmarked+liked recipes matching the filter rules.

    Args:
        request: Generation parameters (min_saves, max_menus)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        MenuGenerateResponse: Generated menus

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    try:
        generated_menus = menu_service.generate_menus_from_patterns(
            user_id=current_user.id,
            db=db,
            min_saves=request.min_saves,
            max_menus=request.max_menus,
        )
        return MenuGenerateResponse(
            generated_menus=generated_menus,
            total_generated=len(generated_menus)
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error generating menus for user {current_user.id}")
        logger.debug(f"Database error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate menus"
        )
