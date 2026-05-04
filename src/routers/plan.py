"""
Meal plan API endpoints.

Provides endpoints for auto-draft meal plan generation, weekly plan viewing,
and entry confirmation.
"""

import logging
from uuid import UUID
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.services import meal_plan_service
from src.middleware.auth import get_current_user
from src.schemas.plan import (
    DraftGenerateRequest,
    DraftGenerateResponse,
    WeekViewResponse,
    ConfirmEntryResponse,
    MealPlanEntrySchema,
)
from src.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan", tags=["meal_plan"])


@router.post("/draft/generate", response_model=DraftGenerateResponse)
def generate_draft(
    request: DraftGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DraftGenerateResponse:
    """
    Generate a draft meal plan for 7 dinner slots.

    Creates draft MealPlanEntries for 7 consecutive days starting from week_start.
    Uses feed query patterns for recipe selection:
    - Expiring inventory first (make_now_recipes)
    - Familiar recipes next (on_repeat_recipes)
    - Popular recipes as fallback

    **Auth:** Required
    **Scope:** Phase 2.5E - Auto-draft meal plan generation
    """
    try:
        entries = meal_plan_service.generate_draft_meal_plan(
            week_start=request.week_start,
            user_id=current_user.id,
            db=db,
        )

        return DraftGenerateResponse(
            entries_created=len(entries),
            week_start=request.week_start,
            entries=[MealPlanEntrySchema.model_validate(e) for e in entries],
        )
    except ValidationError as e:
        logger.warning(f"Validation error during draft generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during draft generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate draft meal plan",
        )


@router.get("/week", response_model=WeekViewResponse)
def get_week(
    week_start: Annotated[date, Query(description="Start date of the week (YYYY-MM-DD)")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WeekViewResponse:
    """
    Get meal plan for a specific week.

    Returns all meal plan entries for the week, separated by status:
    - confirmed_entries: Entries with status=approved
    - draft_entries: Entries with status=draft

    Each entry includes user opt-in information.

    **Auth:** Required
    **Scope:** Phase 2.5E - Weekly plan viewing
    """
    try:
        confirmed, draft = meal_plan_service.get_week_plan(
            week_start=week_start,
            user_id=current_user.id,
            db=db,
        )

        return WeekViewResponse(
            week_start=week_start,
            confirmed_entries=[MealPlanEntrySchema.model_validate(e) for e in confirmed],
            draft_entries=[MealPlanEntrySchema.model_validate(e) for e in draft],
        )
    except Exception as e:
        logger.error(f"Unexpected error during week plan retrieval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve week plan",
        )


@router.put("/entries/{entry_id}/confirm", response_model=ConfirmEntryResponse)
def confirm_entry(
    entry_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConfirmEntryResponse:
    """
    Confirm a draft meal plan entry.

    Transitions entry from draft → approved status and propagates recipe
    ingredients to the grocery list.

    **Auth:** Required
    **Scope:** Phase 2.5E - Entry confirmation with grocery list propagation
    """
    try:
        entry, items_added = meal_plan_service.confirm_entry(
            entry_id=entry_id,
            current_user=current_user,
            db=db,
        )

        return ConfirmEntryResponse(
            entry=MealPlanEntrySchema.model_validate(entry),
            grocery_items_added=items_added,
        )
    except NotFoundError as e:
        logger.warning(f"Entry not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        logger.warning(f"Validation error during entry confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during entry confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm meal plan entry",
        )
