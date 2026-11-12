"""
Recipe business logic service.

Provides core recipe operations that are used across multiple endpoints.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.models.recipe import Recipe
from src.db.models.user import User
from src.db.models.user_recipe import UserRecipeRelation
from src.db.models.user_cook_event import UserCookEvent
from src.schemas.recipe import RecipeOutcomeResponse

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


def get_recipe_outcomes(recipe_id: UUID, db: Session) -> list[RecipeOutcomeResponse]:
    """
    Return one RecipeOutcomeResponse per household member who has cooked or rated the recipe.

    Uses exactly two queries:
      1. UserRecipeRelation JOIN User — members with rating/comment/photos
      2. UserCookEvent JOIN User — all cook events for the recipe

    Members appear if they have a qualifying relation (rating, rating_comment, or
    rating_photos set) OR at least one cook event. Bookmark/like alone does not
    create a row. Results are merged in Python and ordered by last_cooked_at desc
    then user_name asc.
    """
    # Query 1: relations that carry rating data
    relations = (
        db.query(UserRecipeRelation, User)
        .join(User, User.id == UserRecipeRelation.user_id)
        .filter(
            UserRecipeRelation.recipe_id == recipe_id,
            (
                UserRecipeRelation.rating.isnot(None)
                | UserRecipeRelation.rating_comment.isnot(None)
                | UserRecipeRelation.rating_photos.isnot(None)
            ),
        )
        .all()
    )

    # Query 2: all cook events for this recipe, newest first
    cook_events = (
        db.query(UserCookEvent, User)
        .join(User, User.id == UserCookEvent.user_id)
        .filter(UserCookEvent.recipe_id == recipe_id)
        .order_by(UserCookEvent.cooked_at.desc())
        .all()
    )

    # Build a map of user_id -> outcome dict, seeded from relations
    outcomes: dict[UUID, dict] = {}
    for rel, user in relations:
        outcomes[user.id] = {
            "user_id": user.id,
            "user_name": user.name,
            "rating": rel.rating,
            "rating_comment": rel.rating_comment,
            "rating_photos": rel.rating_photos or [],
            "times_cooked": 0,
            "last_cooked_at": None,
            "latest_cook_notes": None,
        }

    # Merge cook events (grouped by user in Python; events are already newest-first)
    for event, user in cook_events:
        if user.id not in outcomes:
            outcomes[user.id] = {
                "user_id": user.id,
                "user_name": user.name,
                "rating": None,
                "rating_comment": None,
                "rating_photos": [],
                "times_cooked": 0,
                "last_cooked_at": None,
                "latest_cook_notes": None,
            }
        entry = outcomes[user.id]
        entry["times_cooked"] += 1
        # First event seen is the latest (events ordered desc)
        if entry["last_cooked_at"] is None:
            entry["last_cooked_at"] = event.cooked_at
            entry["latest_cook_notes"] = event.notes

    # Sort: last_cooked_at desc (None last), then user_name asc
    rows = list(outcomes.values())
    rows.sort(key=lambda r: (r["last_cooked_at"] is None, -(r["last_cooked_at"].timestamp() if r["last_cooked_at"] else 0), r["user_name"]))

    return [RecipeOutcomeResponse(**r) for r in rows]
