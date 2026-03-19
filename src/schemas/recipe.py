"""
Pydantic schemas for recipe endpoints.

Defines request/response models for recipe CRUD operations.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.recipe import SourceType
from src.schemas.validators import validate_enum_value, validate_non_negative


class RecipeCreate(BaseModel):
    """Request schema for creating a new recipe."""

    name: str = Field(..., min_length=1, max_length=255, description="Recipe name")
    source_type: str = Field(..., description="Source type (manual, hellofresh_card, etc.)")

    # Optional fields
    source_url: Optional[str] = Field(default=None, max_length=2048, description="Source URL")
    source_image: Optional[str] = Field(default=None, max_length=2048, description="Source image URL")
    variation_groups: Optional[dict] = Field(default=None, description="Variation groups (JSON)")
    steps: Optional[list] = Field(default_factory=list, description="Cooking steps (JSON)")
    prep_time_minutes: Optional[int] = Field(default=None, description="Preparation time in minutes")
    cook_time_minutes: Optional[int] = Field(default=None, description="Cooking time in minutes")
    base_servings: Optional[int] = Field(default=4, description="Base number of servings")
    tags: Optional[list] = Field(default_factory=list, description="Recipe tags (JSON array)")
    nutritional_info: Optional[dict] = Field(default=None, description="Nutritional information (JSON)")
    notes: Optional[str] = Field(default=None, description="Recipe notes")
    created_by: Optional[UUID] = Field(default=None, description="User ID who created the recipe")

    @field_validator('source_type')
    @classmethod
    def validate_source_type_field(cls, v: str) -> str:
        """Ensure source_type is a valid SourceType enum value."""
        result = validate_enum_value('source_type', v, SourceType, allow_none=False)
        return result  # type: ignore

    @field_validator('prep_time_minutes')
    @classmethod
    def validate_prep_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure prep_time_minutes is non-negative if provided."""
        return validate_non_negative('prep_time_minutes', v, allow_none=True)

    @field_validator('cook_time_minutes')
    @classmethod
    def validate_cook_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure cook_time_minutes is non-negative if provided."""
        return validate_non_negative('cook_time_minutes', v, allow_none=True)

    @field_validator('base_servings')
    @classmethod
    def validate_base_servings_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure base_servings is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("base_servings must be positive")
        return v


class RecipeUpdate(BaseModel):
    """Request schema for updating a recipe (partial updates allowed)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Recipe name")
    source_type: Optional[str] = Field(default=None, description="Source type")
    source_url: Optional[str] = Field(default=None, max_length=2048, description="Source URL")
    source_image: Optional[str] = Field(default=None, max_length=2048, description="Source image URL")
    variation_groups: Optional[dict] = Field(default=None, description="Variation groups (JSON)")
    steps: Optional[list] = Field(default=None, description="Cooking steps (JSON)")
    prep_time_minutes: Optional[int] = Field(default=None, description="Preparation time in minutes")
    cook_time_minutes: Optional[int] = Field(default=None, description="Cooking time in minutes")
    base_servings: Optional[int] = Field(default=None, description="Base number of servings")
    tags: Optional[list] = Field(default=None, description="Recipe tags (JSON array)")
    nutritional_info: Optional[dict] = Field(default=None, description="Nutritional information (JSON)")
    notes: Optional[str] = Field(default=None, description="Recipe notes")

    @field_validator('source_type')
    @classmethod
    def validate_source_type_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure source_type is a valid SourceType enum value if provided."""
        return validate_enum_value('source_type', v, SourceType, allow_none=True)

    @field_validator('prep_time_minutes')
    @classmethod
    def validate_prep_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure prep_time_minutes is non-negative if provided."""
        return validate_non_negative('prep_time_minutes', v, allow_none=True)

    @field_validator('cook_time_minutes')
    @classmethod
    def validate_cook_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure cook_time_minutes is non-negative if provided."""
        return validate_non_negative('cook_time_minutes', v, allow_none=True)

    @field_validator('base_servings')
    @classmethod
    def validate_base_servings_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure base_servings is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("base_servings must be positive")
        return v


class RecipeResponse(BaseModel):
    """Response schema for recipe data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    source_url: Optional[str]
    source_image: Optional[str]
    variation_groups: Optional[dict]
    steps: list
    prep_time_minutes: Optional[int]
    cook_time_minutes: Optional[int]
    base_servings: int
    tags: list
    nutritional_info: Optional[dict]
    times_cooked: int
    created_by: Optional[UUID]
    notes: Optional[str]


class RecipeListResponse(BaseModel):
    """Response schema for recipe list items (lightweight)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    source_image: Optional[str]
    prep_time_minutes: Optional[int]
    cook_time_minutes: Optional[int]
    base_servings: int
    tags: list
    times_cooked: int
    created_by: Optional[UUID]
