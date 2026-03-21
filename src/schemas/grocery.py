"""
Pydantic schemas for grocery list endpoints.

Defines request/response models for grocery item CRUD operations and
store-grouped responses for the by-store endpoint.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.grocery_list import GrocerySource
from src.db.models.inventory_item import Category, UnitType, StorageLocation
from src.schemas.validators import (
    validate_name_not_empty,
    validate_enum_value,
)


class GroceryItemCreate(BaseModel):
    """Request schema for creating a new grocery list item."""

    item_name: str = Field(..., min_length=1, max_length=255, description="Item name")
    quantity: float = Field(..., gt=0, description="Quantity of the item (must be positive)")
    unit: str = Field(..., description="Unit of measurement")
    target_store: Optional[UUID] = Field(default=None, description="Target store ID")
    notes: Optional[str] = Field(default=None, max_length=500, description="Optional notes")
    source: str = Field(default="manual", description="Source of the grocery item (Phase 1: only 'manual' allowed)")

    @field_validator('quantity')
    @classmethod
    def validate_quantity_field(cls, v: float) -> float:
        """Ensure quantity is positive (already enforced by gt=0 in Field)."""
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @field_validator('unit')
    @classmethod
    def validate_unit_field(cls, v: str) -> str:
        """Ensure unit is a valid UnitType enum value."""
        result = validate_enum_value('Unit', v, UnitType, allow_none=False)
        # validate_enum_value handles Optional, but this field is required so won't be None
        return result  # type: ignore

    @field_validator('item_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure item_name is not empty or whitespace only."""
        result = validate_name_not_empty(v)
        # validate_name_not_empty handles None, but name is required so this won't be None
        return result  # type: ignore

    @field_validator('source')
    @classmethod
    def validate_source_field(cls, v: str) -> str:
        """Ensure source is a valid GrocerySource enum value."""
        result = validate_enum_value('Source', v, GrocerySource, allow_none=False)
        # validate_enum_value handles Optional, but this field has a default so won't be None
        return result  # type: ignore


class GroceryItemUpdate(BaseModel):
    """Request schema for updating a grocery item (partial updates)."""

    # Silently ignore unknown fields for forward compatibility
    model_config = ConfigDict(extra="ignore")

    item_name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Item name")
    quantity: Optional[float] = Field(default=None, gt=0, description="Quantity of the item (must be positive)")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    target_store: Optional[UUID] = Field(default=None, description="Target store ID")
    notes: Optional[str] = Field(default=None, max_length=500, description="Optional notes")
    # source is excluded - it's system-managed

    @field_validator('quantity')
    @classmethod
    def validate_quantity_field(cls, v: Optional[float]) -> Optional[float]:
        """Ensure quantity is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @field_validator('unit')
    @classmethod
    def validate_unit_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure unit is a valid UnitType enum value if provided."""
        return validate_enum_value('Unit', v, UnitType, allow_none=True)

    @field_validator('item_name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure item_name is not empty or whitespace only if provided."""
        return validate_name_not_empty(v)


class GroceryItemResponse(BaseModel):
    """Response schema for grocery item data (includes all fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_name: str
    quantity: float
    unit: str
    source: str
    target_store: Optional[UUID]
    purchased: bool
    purchased_by: Optional[UUID]
    purchased_date: Optional[datetime]
    added_by: UUID


class StoreGroupedItems(BaseModel):
    """Schema for a store with its associated grocery items."""

    store_id: UUID
    store_name: str
    items: list[GroceryItemResponse]


class StoreGroupedGroceryResponse(BaseModel):
    """Response schema for grocery items grouped by store."""

    stores: list[StoreGroupedItems] = Field(..., description="Items grouped by target store")
    unassigned: list[GroceryItemResponse] = Field(..., description="Items without a target store")


class BulkPurchaseRequest(BaseModel):
    """Request schema for bulk purchasing grocery items."""

    item_ids: list[UUID] = Field(..., min_length=1, description="List of grocery item IDs to mark as purchased")
    create_inventory_item: bool = Field(default=False, description="Whether to create inventory items from purchased groceries")
    storage_location: Optional[str] = Field(default=None, description="Storage location for created inventory items")
    category: Optional[str] = Field(default=None, description="Category for created inventory items")

    @field_validator('storage_location')
    @classmethod
    def validate_storage_location_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure storage_location is a valid StorageLocation enum value if provided."""
        return validate_enum_value('Storage location', v, StorageLocation, allow_none=True)

    @field_validator('category')
    @classmethod
    def validate_category_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure category is a valid Category enum value if provided."""
        return validate_enum_value('Category', v, Category, allow_none=True)
