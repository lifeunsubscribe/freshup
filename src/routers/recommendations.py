"""
Recommendations router.

GET /recommendations returns a ranked mix of catalog cards and imported
recipes scored by the user's taste blended with popularity.
"""

import logging
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.db.models.user_recipe import UserRecipeRelation
from src.middleware.auth import get_current_user
from src.schemas.catalog import CardResponse
from src.schemas.recipe import RecipeListResponse
from src.schemas.recommendation import RecommendedItem
from src.services.card_tags import overlap_tags, tags_from_text
from src.services.recommendation_service import dinner_first, rank_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendedItem])
def get_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    meal: Optional[Literal["dinner"]] = Query(
        default=None,
        description="dinner = list what suits a dinner first (when choosing for a dinner slot)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendedItem]:
    """
    Return ranked recipe and card recommendations for the authenticated user.

    With no taste history the list is ordered by catalog popularity.
    Every fifth item is an exploration pick: the most popular item whose
    keys have no affinity yet, chosen to surface new ingredients or cuisines.
    """
    ranked = rank_candidates(current_user, db, limit)

    # Build card overlap and recipe bookmark lookups in one pass each
    card_ids = [item.card.id for item in ranked if item.kind == "card"]
    card_overlap = overlap_tags(db, card_ids) if card_ids else {}

    if meal == "dinner":
        ranked = dinner_first(ranked, card_overlap)

    recipe_ids = [item.recipe.id for item in ranked if item.kind == "recipe"]
    bookmarked: set[UUID] = set()
    if recipe_ids:
        bookmarked = {
            rel.recipe_id
            for rel in db.query(UserRecipeRelation)
            .filter(
                UserRecipeRelation.user_id == current_user.id,
                UserRecipeRelation.recipe_id.in_(recipe_ids),
                UserRecipeRelation.is_bookmarked.is_(True),
            )
            .all()
        }

    items: list[RecommendedItem] = []
    for ranked_item in ranked:
        if ranked_item.kind == "card":
            card = ranked_item.card
            c_overlap = card_overlap.get(card.id, set())
            text_tags = tags_from_text(card.name, card.headline)
            stored_keys = card.ingredient_keys
            if stored_keys is not None:
                text_tags = {t for t in text_tags if not t.startswith("ingredient:")}
                c_overlap = {t for t in c_overlap if not t.startswith("ingredient:")}
                tags = text_tags | c_overlap | {f"ingredient:{k}" for k in stored_keys}
            else:
                tags = text_tags | c_overlap
            card_resp = CardResponse(
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
                tags=sorted(tags),
            )
            items.append(RecommendedItem(
                kind="card",
                card=card_resp,
                score=ranked_item.score,
                reason=ranked_item.reason,
            ))
        else:
            recipe = ranked_item.recipe
            recipe_resp = RecipeListResponse(
                id=recipe.id,
                name=recipe.name,
                source_type=recipe.source_type,
                source_url=recipe.source_url,
                source_image=recipe.source_image,
                prep_time_minutes=recipe.prep_time_minutes,
                cook_time_minutes=recipe.cook_time_minutes,
                base_servings=recipe.base_servings,
                tags=recipe.tags or [],
                times_cooked=recipe.times_cooked,
                created_by=recipe.created_by,
                is_bookmarked=recipe.id in bookmarked,
            )
            items.append(RecommendedItem(
                kind="recipe",
                recipe=recipe_resp,
                score=ranked_item.score,
                reason=ranked_item.reason,
            ))

    return items
