"""
Pydantic schemas for prepared food endpoints.

Defines request/response models for PreparedFood CRUD operations including
logging leftovers, batch prep items, and component ingredients.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.prepared_food import PreparedFoodType
from src.db.models.inventory_item import StorageLocation, Shareability
from src.schemas.validators import (
    validate_name_not_empty,
    validate_enum_value,
    validate_non_negative
)
from src.schemas.inventory import ConsumptionRequest


class PreparedFoodCreate(BaseModel):
    """Request schema for creating a new prepared food item."""

    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    source_recipe: Optional[UUID] = Field(default=None, description="Source recipe ID if from a recipe")
    type: str = Field(..., description="Type of prepared food (complete_meal, batch_portion, component_ingredient)")
    servings_remaining: float = Field(..., description="Number of servings remaining")
    storage_location: str = Field(..., description="Storage location (pantry, fridge, freezer)")
    estimated_expiration: Optional[datetime] = Field(default=None, description="Estimated expiration date")
    shareability: str = Field(default=Shareability.shared.value, description="Shareability status (shared, reserved, personal)")
    notes: Optional[str] = Field(default=None, description="Additional notes")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is not empty or whitespace only."""
        result = validate_name_not_empty(v)
        # validate_name_not_empty handles None, but name is required so won't be None
        return result  # type: ignore

    @field_validator('type')
    @classmethod
    def validate_type_field(cls, v: str) -> str:
        """Ensure type is a valid PreparedFoodType enum value."""
        result = validate_enum_value('Type', v, PreparedFoodType, allow_none=False)
        # validate_enum_value handles Optional, but this field is required so won't be None
        return result  # type: ignore

    @field_validator('storage_location')
    @classmethod
    def validate_storage_location_field(cls, v: str) -> str:
        """Ensure storage_location is a valid StorageLocation enum value."""
        result = validate_enum_value('Storage location', v, StorageLocation, allow_none=False)
        # validate_enum_value handles Optional, but this field is required so won't be None
        return result  # type: ignore

    @field_validator('shareability')
    @classmethod
    def validate_shareability_field(cls, v: str) -> str:
        """Ensure shareability is a valid Shareability enum value."""
        result = validate_enum_value('Shareability', v, Shareability, allow_none=False)
        # validate_enum_value handles Optional, but this field has a default so won't be None
        return result  # type: ignore

    @field_validator('servings_remaining')
    @classmethod
    def validate_servings_remaining_field(cls, v: float) -> float:
        """Ensure servings_remaining is non-negative."""
        result = validate_non_negative('Servings remaining', v, allow_none=False)
        # validate_non_negative handles Optional, but this field is required so won't be None
        return result  # type: ignore


class PreparedFoodUpdate(BaseModel):
    """Request schema for updating a prepared food item (partial updates)."""

    # Silently ignore unknown fields for forward compatibility
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Item name")
    source_recipe: Optional[UUID] = Field(default=None, description="Source recipe ID if from a recipe")
    type: Optional[str] = Field(default=None, description="Type of prepared food (complete_meal, batch_portion, component_ingredient)")
    servings_remaining: Optional[float] = Field(default=None, description="Number of servings remaining")
    storage_location: Optional[str] = Field(default=None, description="Storage location (pantry, fridge, freezer)")
    estimated_expiration: Optional[datetime] = Field(default=None, description="Estimated expiration date")
    shareability: Optional[str] = Field(default=None, description="Shareability status (shared, reserved, personal)")
    notes: Optional[str] = Field(default=None, description="Additional notes")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty or whitespace only if provided."""
        return validate_name_not_empty(v)

    @field_validator('type')
    @classmethod
    def validate_type_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure type is a valid PreparedFoodType enum value if provided."""
        return validate_enum_value('Type', v, PreparedFoodType, allow_none=True)

    @field_validator('storage_location')
    @classmethod
    def validate_storage_location_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure storage_location is a valid StorageLocation enum value if provided."""
        return validate_enum_value('Storage location', v, StorageLocation, allow_none=True)

    @field_validator('shareability')
    @classmethod
    def validate_shareability_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure shareability is a valid Shareability enum value if provided."""
        return validate_enum_value('Shareability', v, Shareability, allow_none=True)

    @field_validator('servings_remaining')
    @classmethod
    def validate_servings_remaining_field(cls, v: Optional[float]) -> Optional[float]:
        """Ensure servings_remaining is non-negative if provided."""
        return validate_non_negative('Servings remaining', v, allow_none=True)


class PreparedFoodResponse(BaseModel):
    """Response schema for prepared food item data (includes all fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_recipe: Optional[UUID]
    type: str
    servings_remaining: float
    storage_location: str
    date_prepared: datetime
    estimated_expiration: Optional[datetime]
    shareability: str
    prepared_by: UUID
    notes: Optional[str]


class PreparedFoodListResponse(BaseModel):
    """Response schema for prepared food item lists (summary fields only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: str
    servings_remaining: float
    storage_location: str
    estimated_expiration: Optional[datetime]
    shareability: str


class PreparedFoodConsumptionResponse(BaseModel):
    """Response schema for consumption endpoint."""

    message: str = Field(..., description="Status message")
    deleted: bool = Field(..., description="Whether the item was deleted")
    item: Optional[PreparedFoodResponse] = Field(default=None, description="Updated item (null if deleted)")


class PaginatedPreparedFoodResponse(BaseModel):
    """Response schema for paginated prepared food lists."""

    items: list[PreparedFoodListResponse] = Field(..., description="List of prepared food items")
    total: int = Field(..., description="Total count of items matching filters (before pagination)")


__all__ = [
    "PreparedFoodCreate",
    "PreparedFoodUpdate",
    "PreparedFoodResponse",
    "PreparedFoodListResponse",
    "PreparedFoodConsumptionResponse",
    "PaginatedPreparedFoodResponse",
    "ConsumptionRequest",
]
