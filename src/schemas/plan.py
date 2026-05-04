"""
Pydantic schemas for meal plan endpoints.

Defines request/response models for weekly meal plan draft generation,
viewing, and confirmation.
"""

from __future__ import annotations

from uuid import UUID
from datetime import date as date_type
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class MealPlanEntrySchema(BaseModel):
    """Meal plan entry data returned in responses."""

    id: UUID = Field(..., description="Entry ID")
    date: date_type = Field(..., description="Meal date")
    meal_type: str = Field(..., description="Meal type (breakfast, lunch, dinner, snack)")
    recipe_id: Optional[UUID] = Field(None, description="Recipe ID if using a recipe")
    prepared_food_id: Optional[UUID] = Field(None, description="Prepared food ID if using leftovers")
    planned_servings: int = Field(..., description="Number of servings planned")
    status: str = Field(..., description="Entry status (draft, approved, etc.)")
    notes: Optional[str] = Field(None, description="Optional notes")

    model_config = {"from_attributes": True}


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
