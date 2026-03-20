"""
Pydantic schemas for recipe endpoints.

Defines request/response models for recipe CRUD operations.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.recipe import SourceType
from src.schemas.validators import validate_enum_value, validate_non_negative, validate_ingredient_name


class RecipeIngredientCreate(BaseModel):
    """Request schema for creating a recipe ingredient (nested in recipe creation)."""

    ingredient_name: str = Field(..., min_length=1, max_length=255, description="Ingredient name")
    quantity: float = Field(..., description="Quantity of ingredient")
    unit: str = Field(..., max_length=50, description="Unit of measurement")
    variation_group: Optional[str] = Field(default=None, max_length=100, description="Variation group identifier")
    variation_diet: Optional[str] = Field(default=None, max_length=50, description="Dietary variation identifier")
    is_optional: Optional[bool] = Field(default=False, description="Whether ingredient is optional")

    @field_validator('ingredient_name')
    @classmethod
    def validate_ingredient_name_field(cls, v: str) -> str:
        """Validate ingredient name for Unicode safety and allowed characters."""
        return validate_ingredient_name('Ingredient name', v)

    @field_validator('quantity')
    @classmethod
    def validate_quantity_field(cls, v: float) -> float:
        """Ensure quantity is positive (zero not allowed for ingredients)."""
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v


class RecipeIngredientResponse(BaseModel):
    """Response schema for recipe ingredient."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingredient_name: str
    quantity: float
    unit: str
    variation_group: Optional[str]
    variation_diet: Optional[str]
    is_optional: bool


class RecipeCreate(BaseModel):
    """Request schema for creating a new recipe."""

    name: str = Field(..., min_length=1, max_length=255, description="Recipe name")
    source_type: str = Field(..., description="Source type (e.g., manual, hellofresh_card)")
    source_url: Optional[str] = Field(default=None, max_length=2048, description="Source URL")
    source_image: Optional[str] = Field(default=None, max_length=2048, description="Image URL")
    variation_groups: Optional[dict] = Field(default=None, description="Variation groups metadata")
    steps: Optional[list] = Field(default_factory=list, description="Recipe steps")
    prep_time_minutes: Optional[int] = Field(default=None, description="Preparation time in minutes")
    cook_time_minutes: Optional[int] = Field(default=None, description="Cooking time in minutes")
    base_servings: Optional[int] = Field(default=4, description="Base number of servings")
    tags: Optional[list] = Field(default_factory=list, description="Recipe tags")
    nutritional_info: Optional[dict] = Field(default=None, description="Nutritional information")
    notes: Optional[str] = Field(default=None, description="Personal notes about the recipe")
    ingredients: list[RecipeIngredientCreate] = Field(default_factory=list, description="Recipe ingredients")

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v: str) -> str:
        """Validate recipe name for Unicode safety and allowed characters."""
        return validate_ingredient_name('Recipe name', v)

    @field_validator('source_type')
    @classmethod
    def validate_source_type_field(cls, v: str) -> str:
        """Ensure source_type is a valid SourceType enum value."""
        result = validate_enum_value('Source type', v, SourceType, allow_none=False)
        return result  # type: ignore

    @field_validator('prep_time_minutes')
    @classmethod
    def validate_prep_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure prep time is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Prep time cannot be negative")
        return v

    @field_validator('cook_time_minutes')
    @classmethod
    def validate_cook_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure cook time is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Cook time cannot be negative")
        return v

    @field_validator('base_servings')
    @classmethod
    def validate_base_servings_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure base servings is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Base servings must be greater than 0")
        return v


class RecipeUpdate(BaseModel):
    """Request schema for updating a recipe (partial updates)."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Recipe name")
    source_type: Optional[str] = Field(default=None, description="Source type")
    source_url: Optional[str] = Field(default=None, max_length=2048, description="Source URL")
    source_image: Optional[str] = Field(default=None, max_length=2048, description="Image URL")
    variation_groups: Optional[dict] = Field(default=None, description="Variation groups metadata")
    steps: Optional[list] = Field(default=None, description="Recipe steps")
    prep_time_minutes: Optional[int] = Field(default=None, description="Preparation time in minutes")
    cook_time_minutes: Optional[int] = Field(default=None, description="Cooking time in minutes")
    base_servings: Optional[int] = Field(default=None, description="Base number of servings")
    tags: Optional[list] = Field(default=None, description="Recipe tags")
    nutritional_info: Optional[dict] = Field(default=None, description="Nutritional information")
    notes: Optional[str] = Field(default=None, description="Personal notes about the recipe")

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate recipe name for Unicode safety and allowed characters if provided."""
        if v is not None:
            return validate_ingredient_name('Recipe name', v)
        return v

    @field_validator('source_type')
    @classmethod
    def validate_source_type_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure source_type is a valid SourceType enum value if provided."""
        return validate_enum_value('Source type', v, SourceType, allow_none=True)

    @field_validator('prep_time_minutes')
    @classmethod
    def validate_prep_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure prep time is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Prep time cannot be negative")
        return v

    @field_validator('cook_time_minutes')
    @classmethod
    def validate_cook_time_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure cook time is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Cook time cannot be negative")
        return v

    @field_validator('base_servings')
    @classmethod
    def validate_base_servings_field(cls, v: Optional[int]) -> Optional[int]:
        """Ensure base servings is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Base servings must be greater than 0")
        return v


class RecipeResponse(BaseModel):
    """Response schema for single recipe with full details and ingredients."""

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
    ingredients: list[RecipeIngredientResponse]


class RecipeListResponse(BaseModel):
    """Response schema for recipe list (lighter weight without ingredients)."""

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
