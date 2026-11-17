"""
Recommendations router.

GET /recommendations returns a ranked mix of catalog cards and unlinked
imported recipes, scored by the user's taste blended with popularity.
Blocked items and anything cooked in the last 14 days are excluded.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.middleware.auth import get_current_user
from src.schemas.catalog import CardResponse
from src.schemas.recipe import RecipeListResponse
from src.schemas.recommendation import RecommendedItem
from src.services.card_tags import overlap_tags, tags_from_text
from src.services.recommendation_service import RankedItem, rank_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def _build_card_response(item: RankedItem, db: Session) -> CardResponse:
    """Convert a card-kind RankedItem to a CardResponse."""
    card = item.card
    assert card is not None

    # Build tags: same logic as catalog router but per-card for the response field.
    overlap = overlap_tags(db, [card.id])
    text_tags = tags_from_text(card.name, getattr(card, "headline", None))
    overlap_set = overlap.get(card.id, set())
    stored_keys = card.ingredient_keys
    if stored_keys is not None:
        text_tags = {t for t in text_tags if not t.startswith("ingredient:")}
        overlap_set = {t for t in overlap_set if not t.startswith("ingredient:")}
        tags_set = text_tags | overlap_set | {f"ingredient:{k}" for k in stored_keys}
    else:
        tags_set = text_tags | overlap_set
    tags_set = {t for t in tags_set if not t.startswith("side:")}

    return CardResponse(
        id=card.id,
        name=card.name,
        source_type=card.source_type,
        headline=card.headline,
        image_url=card.image_url,
        prep_time_minutes=card.prep_time_minutes,
        rating=card.rating,
        rating_count=card.rating_count,
        recipe_url=card.recipe_url,
        recipe_id=card.recipe_id,
        is_persisted=bool(card.recipe_rel and card.recipe_rel.is_persisted),
        ingredient_keys=card.ingredient_keys,
        tags=sorted(tags_set),
    )


def _build_recipe_response(item: RankedItem) -> RecipeListResponse:
    """Convert a recipe-kind RankedItem to a RecipeListResponse."""
    recipe = item.recipe
    assert recipe is not None
    return RecipeListResponse(
        id=recipe.id,
        name=recipe.name,
        source_type=recipe.source_type,
        source_url=getattr(recipe, "source_url", None),
        source_image=getattr(recipe, "source_image", None),
        prep_time_minutes=getattr(recipe, "prep_time_minutes", None),
        cook_time_minutes=getattr(recipe, "cook_time_minutes", None),
        base_servings=getattr(recipe, "base_servings", 4),
        tags=list(getattr(recipe, "tags", []) or []),
        times_cooked=getattr(recipe, "times_cooked", 0),
        created_by=getattr(recipe, "created_by", None),
        is_bookmarked=False,
    )


@router.get("", response_model=list[RecommendedItem])
def get_recommendations(
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendedItem]:
    """
    Return a ranked list of recommended recipe cards and imported recipes.

    Items are scored by the user's taste preferences blended with catalog
    popularity.  Blocked items and anything cooked in the last 14 days are
    excluded.  Every fifth slot may be an exploration pick — a popular item
    whose keys the user has not yet signalled an affinity for.
    """
    ranked = rank_candidates(current_user, db, limit)

    response: list[RecommendedItem] = []
    for item in ranked:
        if item.kind == "card":
            response.append(RecommendedItem(
                kind="card",
                card=_build_card_response(item, db),
                recipe=None,
                score=item.score,
                reason=item.reason,
            ))
        else:
            response.append(RecommendedItem(
                kind="recipe",
                card=None,
                recipe=_build_recipe_response(item),
                score=item.score,
                reason=item.reason,
            ))

    return response
