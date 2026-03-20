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


class RecipeIngredientCreate(BaseModel):
    """Request schema for creating a new recipe ingredient."""

    ingredient_name: str = Field(..., min_length=1, max_length=255, description="Ingredient name")
    quantity: float = Field(..., gt=0, description="Ingredient quantity (must be positive)")
    unit: str = Field(..., min_length=1, max_length=50, description="Unit of measurement")
    variation_group: Optional[str] = Field(default=None, max_length=100, description="Variation group identifier")
    variation_diet: Optional[str] = Field(default=None, max_length=50, description="Dietary variation identifier")
    is_optional: bool = Field(default=False, description="Whether ingredient is optional")

    @field_validator('ingredient_name', 'unit')
    @classmethod
    def strip_required_strings(cls, v: str) -> str:
        """Strip whitespace from required string fields."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or only whitespace")
        return stripped

    @field_validator('variation_group', 'variation_diet')
    @classmethod
    def strip_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from optional string fields."""
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class RecipeIngredientUpdate(BaseModel):
    """Request schema for updating a recipe ingredient (partial updates allowed)."""

    ingredient_name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Ingredient name")
    quantity: Optional[float] = Field(default=None, gt=0, description="Ingredient quantity (must be positive)")
    unit: Optional[str] = Field(default=None, min_length=1, max_length=50, description="Unit of measurement")
    variation_group: Optional[str] = Field(default=None, max_length=100, description="Variation group identifier")
    variation_diet: Optional[str] = Field(default=None, max_length=50, description="Dietary variation identifier")
    is_optional: Optional[bool] = Field(default=None, description="Whether ingredient is optional")

    @field_validator('ingredient_name', 'unit')
    @classmethod
    def strip_required_strings(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from string fields."""
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or only whitespace")
        return stripped

    @field_validator('variation_group', 'variation_diet')
    @classmethod
    def strip_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from optional string fields."""
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class RecipeIngredientResponse(BaseModel):
    """Response schema for recipe ingredient data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipe_id: UUID
    ingredient_name: str
    quantity: float
    unit: str
    variation_group: Optional[str]
    variation_diet: Optional[str]
    is_optional: bool


class UserRecipeRatingCreate(BaseModel):
    """Request schema for creating or updating a recipe rating."""

    rating: Optional[float] = Field(default=None, description="Rating value (0.0-5.0)")
    is_favorite: bool = Field(default=False, description="Whether recipe is favorited")
    notes: Optional[str] = Field(default=None, max_length=1000, description="Personal notes about the recipe")

    @field_validator('rating')
    @classmethod
    def validate_rating_range(cls, v: Optional[float]) -> Optional[float]:
        """Ensure rating is between 0.0 and 5.0 if provided."""
        if v is not None:
            if v < 0.0 or v > 5.0:
                raise ValueError("Rating must be between 0.0 and 5.0")
        return v


class UserRecipeRatingResponse(BaseModel):
    """Response schema for user recipe rating data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    recipe_id: UUID
    rating: Optional[float]
    is_favorite: bool
    notes: Optional[str]


class RecipeAggregateRatingsResponse(BaseModel):
    """Response schema for aggregate recipe ratings."""

    average_rating: Optional[float] = Field(default=None, description="Average rating across all users (null if no ratings)")
    rating_count: int = Field(..., description="Number of users who have rated this recipe")
    favorite_count: int = Field(..., description="Number of users who favorited this recipe")


class InventoryItemUsage(BaseModel):
    """Schema for inventory item usage in ad-hoc recipe creation."""

    inventory_item_id: UUID = Field(..., description="ID of the inventory item to use")
    quantity_used: float = Field(..., gt=0, description="Quantity to use from inventory (must be positive)")
    unit: str = Field(..., min_length=1, max_length=50, description="Unit of measurement")

    @field_validator('unit')
    @classmethod
    def strip_unit(cls, v: str) -> str:
        """Strip whitespace from unit field."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Unit cannot be empty or only whitespace")
        return stripped


class AdHocRecipeCreate(BaseModel):
    """Request schema for creating an ad-hoc recipe from inventory items."""

    name: str = Field(..., min_length=1, max_length=255, description="Recipe name")
    steps: Optional[list[str]] = Field(default_factory=list, description="Cooking steps (JSON array)")
    notes: Optional[str] = Field(default=None, description="Recipe notes")
    tags: Optional[list[str]] = Field(default_factory=list, description="Recipe tags (JSON array)")
    inventory_items: list[InventoryItemUsage] = Field(..., min_length=1, description="List of inventory items used in this recipe")
    decrement_inventory: bool = Field(default=False, description="Whether to decrement inventory quantities")

    @field_validator('name')
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip whitespace from name field."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or only whitespace")
        return stripped
