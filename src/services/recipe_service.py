"""
Recipe business logic service.

Provides core recipe operations that are used across multiple endpoints.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.models.recipe import Recipe

logger = logging.getLogger(__name__)


def trigger_persistence(recipe: Recipe, db: Session) -> bool:
    """
    Set a recipe's is_persisted flag to True if not already set.

    When a user bookmarks, likes, or adds a recipe to their meal plan,
    the recipe should become permanent (is_persisted=True). This function
    handles that transition idempotently.

    Background: Recipes start as non-persisted when imported via scrapers
    (browse flow). They only become permanent when a user explicitly
    interacts with them (bookmark, like, meal plan). This prevents
    the database from filling with unbrowsed recipes.

    Args:
        recipe: The Recipe object to persist
        db: Database session

    Returns:
        bool: True if the recipe was persisted (state changed), False if already persisted

    Raises:
        SQLAlchemyError: If database operation fails (caller should handle)
    """
    # No-op if already persisted (idempotent behavior)
    # This ensures safe repeated calls without side effects
    if recipe.is_persisted:
        logger.debug(f"Recipe {recipe.id} already persisted, skipping")
        return False

    # Set persistence flag (one-way operation - never reverses)
    recipe.is_persisted = True

    try:
        db.commit()
        db.refresh(recipe)
        logger.info(f"Recipe {recipe.id} persisted via user interaction")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to persist recipe {recipe.id}: {e}")
        raise
