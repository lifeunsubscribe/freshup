"""
Feed router - Personalized recipe recommendations.

Provides endpoints for the home feed with inventory-aware and behavior-based
recipe recommendations.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.routers.auth import get_current_user
from src.services import feed_service
from src.schemas.feed import HomeFeedResponseSchema, FeedSectionSchema, RecipeCardSchema

router = APIRouter(prefix="/feed", tags=["feed"])
logger = logging.getLogger(__name__)


@router.get("/home", response_model=HomeFeedResponseSchema)
def get_home_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized home feed with recipe recommendations.

    Returns two sections:
    - Make This Right Now: Recipes user can cook based on current inventory (top 10)
    - On Repeat: Recipes user repeatedly engages with (top 15)

    Cold start behavior: Returns empty arrays if no matching recipes found.

    Requires authentication.
    """
    # Get Make This Right Now recipes (inventory-aware)
    make_now_recipes = feed_service.get_make_now_recipes(
        user_id=current_user.id,
        db=db,
        limit=10
    )

    # Get On Repeat recipes (behavioral signals)
    on_repeat_recipes = feed_service.get_on_repeat_recipes(
        user_id=current_user.id,
        db=db,
        limit=15
    )

    # Build response
    response = HomeFeedResponseSchema(
        make_now=FeedSectionSchema(
            title="Make This Right Now",
            recipes=[RecipeCardSchema.model_validate(r) for r in make_now_recipes]
        ),
        on_repeat=FeedSectionSchema(
            title="On Repeat",
            recipes=[RecipeCardSchema.model_validate(r) for r in on_repeat_recipes]
        )
    )

    logger.info(
        f"Home feed for user {current_user.id}: "
        f"{len(make_now_recipes)} make-now, {len(on_repeat_recipes)} on-repeat"
    )

    return response
