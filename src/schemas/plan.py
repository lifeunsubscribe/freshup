"""
Pydantic schemas for meal plan endpoints.

Defines request/response models for weekly meal plan draft generation,
viewing, confirmation, and single-entry creation.
"""

from __future__ import annotations

from uuid import UUID
from datetime import date as date_type
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from src.db.models.meal_plan import MealType


class DisplayInfo(BaseModel):
    """Display-ready summary built from either the linked recipe or catalog card."""

    name: str
    image_url: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    source_type: str


class MealPlanEntrySchema(BaseModel):
    """Meal plan entry data returned in responses."""

    id: UUID = Field(..., description="Entry ID")
    date: date_type = Field(..., description="Meal date")
    meal_type: str = Field(..., description="Meal type (breakfast, lunch, dinner, snack)")
    recipe_id: Optional[UUID] = Field(None, description="Recipe ID if using a recipe")
    catalog_card_id: Optional[UUID] = Field(None, description="Catalog card ID for unconfirmed card entries")
    prepared_food_id: Optional[UUID] = Field(None, description="Prepared food ID if using leftovers")
    planned_servings: int = Field(..., description="Number of servings planned")
    status: str = Field(..., description="Entry status (draft, approved, etc.)")
    notes: Optional[str] = Field(None, description="Optional notes")
    display: Optional[DisplayInfo] = Field(None, description="Display info from the linked recipe or card")

    model_config = {"from_attributes": True}

    @model_validator(mode='before')
    @classmethod
    def _populate_display(cls, obj):
        """Build display from ORM relationships; pass dicts through unchanged."""
        if isinstance(obj, dict):
            return obj

        recipe_rel = getattr(obj, 'recipe_rel', None)
        card_rel = getattr(obj, 'catalog_card_rel', None)

        if recipe_rel is not None:
            # A recipe keeps its picture in source_image. An entry accepted from
            # a catalog card still points at the card, so the card's picture
            # stands in when the imported recipe came without one.
            image_url = getattr(recipe_rel, 'source_image', None) or getattr(card_rel, 'image_url', None)
            display = {
                'name': recipe_rel.name,
                'image_url': image_url,
                'prep_time_minutes': getattr(recipe_rel, 'prep_time_minutes', None),
                'source_type': getattr(recipe_rel, 'source_type', 'manual') or 'manual',
            }
        elif card_rel is not None:
            display = {
                'name': card_rel.name,
                'image_url': card_rel.image_url,
                'prep_time_minutes': card_rel.prep_time_minutes,
                'source_type': card_rel.source_type,
            }
        else:
            display = None

        return {
            'id': obj.id,
            'date': obj.date,
            'meal_type': obj.meal_type,
            'recipe_id': obj.recipe_id,
            'catalog_card_id': getattr(obj, 'catalog_card_id', None),
            'prepared_food_id': getattr(obj, 'prepared_food_id', None),
            'planned_servings': obj.planned_servings,
            'status': obj.status,
            'notes': getattr(obj, 'notes', None),
            'display': display,
        }


class DraftGenerateRequest(BaseModel):
    """Request schema for generating a draft meal plan."""

    week_start: date_type = Field(..., description="Start date of the week (YYYY-MM-DD)")

    @field_validator('week_start')
    @classmethod
    def validate_week_start_is_monday(cls, v: date_type) -> date_type:
        """Ensure week_start is a Monday."""
        if v.weekday() != 0:  # Monday is 0
            raise ValueError('week_start must be a Monday')
        return v


class DraftGenerateResponse(BaseModel):
    """Response schema for draft generation."""

    entries_created: int = Field(..., description="Number of entries created")
    week_start: date_type = Field(..., description="Start date of the week")
    entries: list[MealPlanEntrySchema] = Field(..., description="Created meal plan entries")


class WeekViewResponse(BaseModel):
    """Response schema for GET /plan/week endpoint."""

    week_start: date_type = Field(..., description="Start date of the week")
    confirmed_entries: list[MealPlanEntrySchema] = Field(
        default_factory=list,
        description="Entries with status=approved"
    )
    draft_entries: list[MealPlanEntrySchema] = Field(
        default_factory=list,
        description="Entries with status=draft"
    )


class ConfirmEntryResponse(BaseModel):
    """Response schema for confirming a draft entry."""

    entry: MealPlanEntrySchema = Field(..., description="Updated meal plan entry")
    grocery_items_added: int = Field(..., description="Number of items added to grocery list")


class OptOutEntryResponse(BaseModel):
    """Response schema for PUT /plan/entries/{id}/opt-out."""

    entry: MealPlanEntrySchema = Field(..., description="Updated meal plan entry after opt-out")


class SwapEntryResponse(BaseModel):
    """Response schema for POST /plan/entries/{id}/swap."""

    entry: MealPlanEntrySchema = Field(..., description="Updated meal plan entry after swap")


class CreateEntryRequest(BaseModel):
    """Request schema for POST /plan/entries — place a recipe into a meal slot."""

    date: date_type = Field(..., description="Date of the meal (YYYY-MM-DD)")
    meal_type: MealType = Field(..., description="Meal slot (breakfast, lunch, dinner, snack)")
    recipe_id: UUID = Field(..., description="Recipe to add to the meal plan")
    planned_servings: Optional[int] = Field(
        None,
        ge=1,
        description="Number of servings (defaults to recipe's base_servings when omitted)",
    )
    notes: Optional[str] = Field(None, description="Optional free-text notes for this entry")
