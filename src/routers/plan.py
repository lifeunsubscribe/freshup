"""
Meal plan API endpoints.

Provides endpoints for auto-draft meal plan generation, weekly plan viewing,
entry confirmation, and manual single-entry creation.
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
    OptOutEntryResponse,
    SwapEntryResponse,
    MealPlanEntrySchema,
    CreateEntryRequest,
    RemixWeekRequest,
    RemixWeekResponse,
    RemoveEntryResponse,
    ShoppingLineNeed,
    ShoppingLineResponse,
    WeekShoppingResponse,
    WeekShoppingAddRequest,
    WeekShoppingAddResponse,
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
    Suggest a dinner for each day of the week (Sunday to Saturday) that has none.

    Creates draft MealPlanEntries for the free days of the week starting at
    week_start; with from_date, only for free days on or after it.
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
            from_date=request.from_date,
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


@router.post("/week/remix", response_model=RemixWeekResponse)
def remix_week(
    request: RemixWeekRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RemixWeekResponse:
    """
    Replace every suggested dinner of a week with a different suggestion.

    Accepted dinners stay. With from_date, suggestions on earlier days stay too.
    A suggestion with nothing else to offer is kept. Returns the week as it is
    afterwards and how many suggestions changed.

    **Auth:** Required
    """
    try:
        changed = meal_plan_service.remix_week(
            week_start=request.week_start,
            user_id=current_user.id,
            db=db,
            from_date=request.from_date,
        )
        confirmed, draft = meal_plan_service.get_week_plan(
            week_start=request.week_start,
            user_id=current_user.id,
            db=db,
        )
        return RemixWeekResponse(
            week_start=request.week_start,
            confirmed_entries=[MealPlanEntrySchema.model_validate(e) for e in confirmed],
            draft_entries=[MealPlanEntrySchema.model_validate(e) for e in draft],
            changed=changed,
        )
    except Exception as e:
        logger.error(f"Unexpected error during week remix: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remix the week",
        )


@router.get("/week/shopping", response_model=WeekShoppingResponse)
def get_week_shopping(
    week_start: Annotated[date, Query(description="First day of the week, a Sunday (YYYY-MM-DD)")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WeekShoppingResponse:
    """
    The ingredients the week's accepted dinners need, one line per ingredient,
    checked against the pantry and the grocery list, for the user to approve.

    **Auth:** Required
    """
    from src.services.plan_week import week_start_of
    from src.services.week_shopping import week_shopping_lines

    if week_start_of(week_start) != week_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="week_start must be a Sunday")
    lines, dinners = week_shopping_lines(db, week_start)
    return WeekShoppingResponse(
        week_start=week_start,
        dinners=dinners,
        lines=[
            ShoppingLineResponse(
                key=line.key,
                name=line.name,
                unit=line.unit,
                to_taste=line.to_taste,
                quantity=round(line.quantity, 3),
                add_quantity=line.add_quantity,
                suggested=line.suggested,
                pantry_quantity=line.pantry_quantity,
                pantry_unit=line.pantry_unit,
                pantry_counted=line.pantry_counted,
                listed_quantity=round(line.listed_quantity, 3),
                listed_otherwise=line.listed_otherwise,
                needs=[
                    ShoppingLineNeed(recipe_name=n.recipe_name, date=n.day, quantity=round(n.quantity, 3))
                    for n in line.needs
                ],
            )
            for line in lines
        ],
    )


@router.post("/week/shopping", response_model=WeekShoppingAddResponse)
def add_week_shopping(
    request: WeekShoppingAddRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WeekShoppingAddResponse:
    """
    Put the chosen lines of the week's shopping list on the grocery list.

    Each line becomes one item that records which dinners it is for, so
    removing a dinner later takes its share off again.

    **Auth:** Required
    """
    from src.services.week_shopping import add_lines_to_grocery_list

    result = add_lines_to_grocery_list(db, request.week_start, request.keys, current_user)
    return WeekShoppingAddResponse(added=result.added, skipped=result.skipped)


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


@router.put("/entries/{entry_id}/opt-out", response_model=OptOutEntryResponse)
def opt_out_entry(
    entry_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OptOutEntryResponse:
    """
    Remove the calling user from a meal plan entry's opt-in list.

    Idempotent: calling this endpoint twice in a row returns 200 both times
    and leaves one consistent state.  The entry is never deleted, even when
    the last participant opts out.  planned_servings is recomputed from the
    remaining opt-in count when that count is > 0; it is left unchanged when
    nobody remains opted in.

    **Auth:** Required
    **Scope:** Phase 2.5E - Per-meal opt-out
    """
    try:
        entry = meal_plan_service.opt_out_entry(
            entry_id=entry_id,
            current_user=current_user,
            db=db,
        )
        return OptOutEntryResponse(entry=MealPlanEntrySchema.model_validate(entry))
    except NotFoundError as e:
        logger.warning(f"Entry not found during opt-out: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        logger.warning(f"Validation error during opt-out: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during opt-out: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to opt out of meal plan entry",
        )


@router.delete("/entries/{entry_id}", response_model=RemoveEntryResponse)
def remove_entry(
    entry_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RemoveEntryResponse:
    """
    Take a dinner off the plan, suggested or accepted.

    Grocery items that were added for it and are not yet purchased come off the
    grocery list; purchased ones stay.

    **Auth:** Required
    """
    try:
        removed = meal_plan_service.remove_entry(entry_id, db)
        return RemoveEntryResponse(grocery_items_removed=removed)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/entries/{entry_id}/swap", response_model=SwapEntryResponse)
def swap_entry(
    entry_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SwapEntryResponse:
    """
    Replace a suggested dinner with the next best candidate for that day.

    Applies weeknight and allergy rules.  Tracks previously offered items so
    repeated swaps on the same slot never resurface something already shown.

    **Auth:** Required
    **Scope:** Phase 2.5J - Swap a suggested dinner
    """
    try:
        entry = meal_plan_service.swap_entry(
            entry_id=entry_id,
            user_id=current_user.id,
            db=db,
        )
        return SwapEntryResponse(entry=MealPlanEntrySchema.model_validate(entry))
    except NotFoundError as e:
        logger.warning(f"Entry not found during swap: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        logger.warning(f"Validation error during swap: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during swap: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to swap meal plan entry",
        )


@router.post("/entries", response_model=MealPlanEntrySchema, status_code=status.HTTP_201_CREATED)
def create_entry(
    request: CreateEntryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MealPlanEntrySchema:
    """
    Add a recipe, or a catalog card not yet imported, to the meal plan for a
    specific date and meal slot.

    Creates a draft entry that appears in GET /plan/week. The calling user is
    automatically opted in. Unaccepted suggestions in that slot are replaced;
    accepted meals there stay.

    **Auth:** Required
    **Scope:** Phase 2.5E - Add-to-plan quick action
    """
    try:
        entry = meal_plan_service.create_entry(
            request_date=request.date,
            meal_type=request.meal_type.value,
            recipe_id=request.recipe_id,
            catalog_card_id=request.catalog_card_id,
            planned_servings=request.planned_servings,
            notes=request.notes,
            current_user=current_user,
            db=db,
        )
        return MealPlanEntrySchema.model_validate(entry)
    except NotFoundError as e:
        logger.warning(f"Recipe or card not found during entry creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        logger.warning(f"Validation error during entry creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during entry creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create meal plan entry",
        )
