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
from src.schemas.feed import (
    HomeFeedResponseSchema,
    FeedSectionSchema,
    RecipeCardSchema,
    FeedRowSchema,
    BrowseFeedResponseSchema
)

router = APIRouter(prefix="/feed", tags=["feed"])
logger = logging.getLogger(__name__)


@router.get("/home", response_model=HomeFeedResponseSchema)
def get_home_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized home feed with recipe recommendations.

    Returns multiple sections:
    - Make This Right Now: Recipes user can cook based on current inventory (top 10)
    - On Repeat: Recipes user repeatedly engages with (top 15)
    - Personalized rows: Tag-based rows from user patterns (3-4 rows max)
    - Source rows: Source-specific rows from user patterns (2 rows max, >=5 saves)
    - Fallback rows: Popular/Quick/New recipes for cold start or variety

    Cold start behavior: When personalized/source rows are empty, fallback rows provide content.

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

    # Build personalized rows (tag-based patterns)
    personalized_rows_data = feed_service.build_personalized_rows(
        user_id=current_user.id,
        db=db,
        max_rows=4
    )

    # Build source rows (source-based patterns)
    source_rows_data = feed_service.build_source_rows(
        user_id=current_user.id,
        db=db,
        max_rows=2
    )

    # Build fallback rows (cold start or variety)
    fallback_rows_data = feed_service.build_fallback_rows(db=db)

    # Convert row data to schemas
    personalized_rows = [
        FeedRowSchema(
            title=row["title"],
            recipes=[RecipeCardSchema.model_validate(r) for r in row["recipes"]],
            browse_url=row.get("browse_url")
        )
        for row in personalized_rows_data
    ]

    source_rows = [
        FeedRowSchema(
            title=row["title"],
            recipes=[RecipeCardSchema.model_validate(r) for r in row["recipes"]],
            browse_url=row.get("browse_url")
        )
        for row in source_rows_data
    ]

    fallback_rows = [
        FeedRowSchema(
            title=row["title"],
            recipes=[RecipeCardSchema.model_validate(r) for r in row["recipes"]],
            browse_url=row.get("browse_url")
        )
        for row in fallback_rows_data
    ]

    # Build response
    response = HomeFeedResponseSchema(
        make_now=FeedSectionSchema(
            title="Make This Right Now",
            recipes=[RecipeCardSchema.model_validate(r) for r in make_now_recipes]
        ),
        on_repeat=FeedSectionSchema(
            title="On Repeat",
            recipes=[RecipeCardSchema.model_validate(r) for r in on_repeat_recipes]
        ),
        personalized_rows=personalized_rows,
        source_rows=source_rows,
        fallback_rows=fallback_rows
    )

    logger.info(
        f"Home feed for user {current_user.id}: "
        f"{len(make_now_recipes)} make-now, {len(on_repeat_recipes)} on-repeat, "
        f"{len(personalized_rows)} personalized rows, {len(source_rows)} source rows, "
        f"{len(fallback_rows)} fallback rows"
    )

    return response


@router.get("/browse", response_model=BrowseFeedResponseSchema)
def get_browse_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get browse feed with all carousel sections for recipe discovery.

    Returns all available feed sections:
    - Personalized rows (tag-based patterns)
    - Source rows (source-based patterns)
    - Fallback rows (Popular/Quick/New)

    This endpoint provides the full recipe browse experience with all
    available carousels. Future enhancement: add filter param to narrow
    by tag/source/etc.

    Requires authentication.
    """
    # Build all row types
    personalized_rows_data = feed_service.build_personalized_rows(
        user_id=current_user.id,
        db=db,
        max_rows=4
    )

    source_rows_data = feed_service.build_source_rows(
        user_id=current_user.id,
        db=db,
        max_rows=2
    )

    fallback_rows_data = feed_service.build_fallback_rows(db=db)

    # Combine all sections
    all_sections_data = personalized_rows_data + source_rows_data + fallback_rows_data

    # Convert to schemas
    sections = [
        FeedRowSchema(
            title=row["title"],
            recipes=[RecipeCardSchema.model_validate(r) for r in row["recipes"]],
            browse_url=row.get("browse_url")
        )
        for row in all_sections_data
    ]

    logger.info(
        f"Browse feed for user {current_user.id}: {len(sections)} total sections "
        f"({len(personalized_rows_data)} personalized, {len(source_rows_data)} source, "
        f"{len(fallback_rows_data)} fallback)"
    )

    return BrowseFeedResponseSchema(sections=sections)
