"""
Browse cache cleanup service.

Prunes non-persisted recipes older than the configured TTL and their
associated UserRecipeRating records. This keeps the browse cache from
growing indefinitely while preserving user-persisted recipes.

Per ADR Section 2.5B: Browse-Then-Persist Flow
- Only non-persisted recipes are pruned (is_persisted=False)
- TTL is configurable via BROWSE_CACHE_TTL_DAYS env var (default 7 days)
- Orphaned UserRecipeRating records are cascade deleted
- Cleanup runs on application startup (MVP - no real-time scheduling)
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models.recipe import Recipe
from src.db.models.user_recipe import UserRecipeRating

logger = logging.getLogger(__name__)


def prune_unpersisted_recipes(db: Session) -> int:
    """
    Delete non-persisted recipes older than TTL and their orphaned UserRecipeRating records.

    Queries for recipes where:
    - is_persisted = False
    - created_at < now() - BROWSE_CACHE_TTL_DAYS

    First deletes associated UserRecipeRating records to avoid FK constraint violations,
    then deletes the recipes themselves. All operations are performed in a single
    transaction.

    Args:
        db: Database session for queries and deletes

    Returns:
        Number of recipes pruned

    Example:
        >>> with SessionFactory() as db:
        >>>     pruned_count = prune_unpersisted_recipes(db)
        >>>     logger.info(f"Pruned {pruned_count} recipes")
    """
    # Get settings inside function to allow test monkeypatching
    settings = get_settings()

    # Calculate cutoff date based on TTL
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.browse_cache_ttl_days)

    # Query for recipes to prune
    stmt = (
        select(Recipe.id)
        .where(
            Recipe.is_persisted == False,  # noqa: E712 - SQLAlchemy requires == for bool comparison
            Recipe.created_at < cutoff_date
        )
    )
    result = db.execute(stmt)
    recipe_ids_to_prune = [row[0] for row in result.fetchall()]

    if not recipe_ids_to_prune:
        logger.debug(
            "No non-persisted recipes to prune",
            extra={"ttl_days": settings.browse_cache_ttl_days}
        )
        return 0

    logger.info(
        f"Pruning {len(recipe_ids_to_prune)} non-persisted recipe(s) older than {settings.browse_cache_ttl_days} days",
        extra={
            "recipe_count": len(recipe_ids_to_prune),
            "ttl_days": settings.browse_cache_ttl_days,
            "cutoff_date": cutoff_date.isoformat()
        }
    )

    # Delete associated UserRecipeRating records first (avoid FK constraint violations)
    rating_delete_stmt = (
        delete(UserRecipeRating)
        .where(UserRecipeRating.recipe_id.in_(recipe_ids_to_prune))
    )
    rating_result = db.execute(rating_delete_stmt)
    deleted_ratings = rating_result.rowcount

    logger.debug(
        f"Deleted {deleted_ratings} orphaned UserRecipeRating record(s)",
        extra={"deleted_count": deleted_ratings}
    )

    # Delete the recipes
    recipe_delete_stmt = (
        delete(Recipe)
        .where(Recipe.id.in_(recipe_ids_to_prune))
    )
    recipe_result = db.execute(recipe_delete_stmt)
    deleted_recipes = recipe_result.rowcount

    # Commit the transaction
    db.commit()

    logger.info(
        f"Pruned {deleted_recipes} recipe(s) and {deleted_ratings} rating(s)",
        extra={
            "pruned_recipes": deleted_recipes,
            "pruned_ratings": deleted_ratings
        }
    )

    return deleted_recipes
