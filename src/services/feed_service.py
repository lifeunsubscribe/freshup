"""
Feed service - Personalized recipe recommendations.

Provides "Make This Right Now" (inventory-aware) and "On Repeat" (behavioral signals)
query logic for the home feed.
"""

import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.inventory_item import InventoryItem
from src.db.models.user_recipe import UserRecipeRating

logger = logging.getLogger(__name__)


def get_make_now_recipes(user_id: UUID, db: Session, limit: int = 10) -> list[Recipe]:
    """
    Get recipes the user can make right now based on inventory availability.

    Returns persisted recipes where the user has 100% of required (non-optional)
    ingredients available. Results are sorted by freshness priority (ingredients
    expiring soonest) then by times_cooked descending.

    Args:
        user_id: User ID to check inventory for
        db: Database session
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects with 100% ingredient availability

    Note:
        - Only checks required ingredients (is_optional=False)
        - Uses case-insensitive ingredient name matching
        - Freshness priority based on earliest expiration_date in recipe's ingredients
        - TODO: Add fuzzy matching for ingredient names
        - TODO: Add unit conversion between recipe and inventory units
    """
    # Subquery: For each recipe, count total required ingredients
    total_ingredients_subq = (
        db.query(
            RecipeIngredient.recipe_id,
            func.count(distinct(RecipeIngredient.id)).label("total_required")
        )
        .filter(RecipeIngredient.is_optional == False)  # noqa: E712
        .group_by(RecipeIngredient.recipe_id)
        .subquery()
    )

    # Subquery: For each recipe, count matched ingredients in user's inventory
    # Match by case-insensitive ingredient name
    matched_ingredients_subq = (
        db.query(
            RecipeIngredient.recipe_id,
            func.count(distinct(RecipeIngredient.id)).label("matched_count")
        )
        .join(
            InventoryItem,
            func.lower(RecipeIngredient.ingredient_name) == func.lower(InventoryItem.name)
        )
        .filter(RecipeIngredient.is_optional == False)  # noqa: E712
        .filter(InventoryItem.added_by == user_id)
        .filter(InventoryItem.quantity > 0)  # Only count items with available quantity
        .group_by(RecipeIngredient.recipe_id)
        .subquery()
    )

    # Subquery: For each recipe, get earliest expiration date of its ingredients
    # This drives freshness priority sorting
    freshness_subq = (
        db.query(
            RecipeIngredient.recipe_id,
            func.min(InventoryItem.expiration_date).label("earliest_expiration")
        )
        .join(
            InventoryItem,
            func.lower(RecipeIngredient.ingredient_name) == func.lower(InventoryItem.name)
        )
        .filter(InventoryItem.added_by == user_id)
        .filter(InventoryItem.expiration_date.isnot(None))
        .group_by(RecipeIngredient.recipe_id)
        .subquery()
    )

    # Main query: Get recipes with 100% ingredient availability
    query = (
        db.query(Recipe)
        .join(total_ingredients_subq, Recipe.id == total_ingredients_subq.c.recipe_id)
        .outerjoin(matched_ingredients_subq, Recipe.id == matched_ingredients_subq.c.recipe_id)
        .outerjoin(freshness_subq, Recipe.id == freshness_subq.c.recipe_id)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .filter(
            # Only recipes with 100% ingredient availability
            # Handle case where matched_count is NULL (0 matches)
            func.coalesce(matched_ingredients_subq.c.matched_count, 0)
            == total_ingredients_subq.c.total_required
        )
        .order_by(
            # Sort by freshness (earliest expiration first), NULL last
            case(
                (freshness_subq.c.earliest_expiration.is_(None), None),
                else_=freshness_subq.c.earliest_expiration
            ).asc().nullslast(),
            # Then by popularity (times cooked)
            Recipe.times_cooked.desc()
        )
        .limit(limit)
    )

    recipes = query.all()
    logger.info(f"Found {len(recipes)} make-now recipes for user {user_id}")
    return recipes


def get_on_repeat_recipes(user_id: UUID, db: Session, limit: int = 15) -> list[Recipe]:
    """
    Get recipes the user repeatedly engages with based on behavioral signals.

    Weighted scoring from:
    - Viewed-not-cooked (0.25) - TODO: requires UserRecipeView model from #5
    - High-frequency-cooked (0.30) - TODO: requires UserCookEvent model from #4
    - Recently-rated (0.25) - IMPLEMENTED: uses UserRecipeRating.updated_at
    - Genre-affinity (0.20) - TODO: requires cook history analysis

    Args:
        user_id: User ID to get recommendations for
        db: Database session
        limit: Maximum number of recipes to return (default 15)

    Returns:
        List of Recipe objects sorted by engagement score

    Note:
        Current implementation only uses recently-rated signal (0.25 weight).
        Full weighted scoring will be available after dependencies #4 and #5 complete.
        Returns empty list if no rating data exists (cold start case).
    """
    # TODO (#4): Add viewed-not-cooked signal (0.25)
    # Requires UserRecipeView model to track views and correlate with cook events

    # TODO (#4): Add high-frequency-cooked signal (0.30)
    # Requires UserCookEvent model to calculate cook frequency

    # TODO (#4, #5): Add genre-affinity signal (0.20)
    # Requires cook history to analyze preferred tags/genres

    # Current implementation: Recently-rated signal only
    # Uses updated_at from UserRecipeRating as recency indicator
    # Orders by most recent rating first
    query = (
        db.query(Recipe)
        .join(UserRecipeRating, Recipe.id == UserRecipeRating.recipe_id)
        .filter(UserRecipeRating.user_id == user_id)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .order_by(UserRecipeRating.updated_at.desc())
        .limit(limit)
    )

    recipes = query.all()
    logger.info(
        f"Found {len(recipes)} on-repeat recipes for user {user_id} "
        f"(recently-rated signal only, awaiting #4 and #5 for full scoring)"
    )
    return recipes
