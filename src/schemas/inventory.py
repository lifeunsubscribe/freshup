"""
Pydantic schemas for inventory endpoints.

Defines request/response models for inventory CRUD operations.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.inventory_item import Category, UnitType, StorageLocation, Shareability


class StoreResponse(BaseModel):
    """Response schema for store data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    has_digital_receipts: bool


class SetPreferredStoreRequest(BaseModel):
    """Request schema for setting preferred store."""

    store_id: UUID = Field(..., description="Store ID to set as preferred")


class AddAvailableStoreRequest(BaseModel):
    """Request schema for adding a store to available_at_stores."""

    store_id: UUID = Field(..., description="Store ID to add to available stores")


class UpdateShareabilityRequest(BaseModel):
    """Request schema for updating item shareability."""

    shareability: str = Field(..., description="Shareability status (shared, reserved, personal)")
    reserved_note: Optional[str] = Field(default=None, max_length=500, description="Note for reserved items")

    @field_validator('shareability')
    @classmethod
    def validate_shareability(cls, v: str) -> str:
        """Ensure shareability is a valid Shareability enum value."""
        valid_shareability = [share.value for share in Shareability]
        if v not in valid_shareability:
            raise ValueError(f'Shareability must be one of: {", ".join(valid_shareability)}')
        return v


class InventoryItemCreate(BaseModel):
    """Request schema for creating a new inventory item."""

    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    quantity: float = Field(..., description="Quantity of the item")
    unit: str = Field(..., description="Unit of measurement")
    category: str = Field(..., description="Item category")
    storage_location: str = Field(..., description="Storage location (pantry, fridge, freezer)")
    added_by: UUID = Field(..., description="User ID who added the item")

    # Optional fields
    expiration_date: Optional[datetime] = Field(default=None, description="Expiration date")
    frozen_date: Optional[datetime] = Field(default=None, description="Date when item was frozen")
    is_staple: Optional[bool] = Field(default=False, description="Whether item is a staple")
    minimum_threshold: Optional[float] = Field(default=None, description="Minimum quantity threshold for alerts")
    shareability: Optional[str] = Field(default=Shareability.shared.value, description="Shareability status (shared, reserved, personal)")
    reserved_note: Optional[str] = Field(default=None, max_length=500, description="Note for reserved items")
    price: Optional[float] = Field(default=None, description="Price of the item")
    brand: Optional[str] = Field(default=None, max_length=255, description="Brand name")
    preferred_store: Optional[UUID] = Field(default=None, description="Preferred store ID")
    vegan_friendly: Optional[bool] = Field(default=False, description="Whether item is vegan-friendly")

    @field_validator('quantity')
    @classmethod
    def validate_quantity_non_negative(cls, v: float) -> float:
        """Ensure quantity is non-negative."""
        if v < 0:
            raise ValueError('Quantity cannot be negative')
        return v

    @field_validator('minimum_threshold')
    @classmethod
    def validate_threshold_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure minimum threshold is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Minimum threshold cannot be negative')
        return v

    @field_validator('price')
    @classmethod
    def validate_price_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure price is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Price cannot be negative')
        return v

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: str) -> str:
        """Ensure unit is a valid UnitType enum value."""
        valid_units = [unit.value for unit in UnitType]
        if v not in valid_units:
            raise ValueError(f'Unit must be one of: {", ".join(valid_units)}')
        return v

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Ensure category is a valid Category enum value."""
        valid_categories = [cat.value for cat in Category]
        if v not in valid_categories:
            raise ValueError(f'Category must be one of: {", ".join(valid_categories)}')
        return v

    @field_validator('storage_location')
    @classmethod
    def validate_storage_location(cls, v: str) -> str:
        """Ensure storage_location is a valid StorageLocation enum value."""
        valid_locations = [loc.value for loc in StorageLocation]
        if v not in valid_locations:
            raise ValueError(f'Storage location must be one of: {", ".join(valid_locations)}')
        return v

    @field_validator('shareability')
    @classmethod
    def validate_shareability(cls, v: Optional[str]) -> Optional[str]:
        """Ensure shareability is a valid Shareability enum value."""
        if v is not None:
            valid_shareability = [share.value for share in Shareability]
            if v not in valid_shareability:
                raise ValueError(f'Shareability must be one of: {", ".join(valid_shareability)}')
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure name is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()


class InventoryItemUpdate(BaseModel):
    """Request schema for updating an inventory item (partial updates)."""

    # Silently ignore unknown fields for forward compatibility
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Item name")
    quantity: Optional[float] = Field(default=None, description="Quantity of the item")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    category: Optional[str] = Field(default=None, description="Item category")
    storage_location: Optional[str] = Field(default=None, description="Storage location (pantry, fridge, freezer)")
    expiration_date: Optional[datetime] = Field(default=None, description="Expiration date")
    frozen_date: Optional[datetime] = Field(default=None, description="Date when item was frozen")
    is_staple: Optional[bool] = Field(default=None, description="Whether item is a staple")
    minimum_threshold: Optional[float] = Field(default=None, description="Minimum quantity threshold for alerts")
    shareability: Optional[str] = Field(default=None, description="Shareability status (shared, reserved, personal)")
    reserved_note: Optional[str] = Field(default=None, max_length=500, description="Note for reserved items")
    price: Optional[float] = Field(default=None, description="Price of the item")
    brand: Optional[str] = Field(default=None, max_length=255, description="Brand name")
    preferred_store: Optional[UUID] = Field(default=None, description="Preferred store ID")
    vegan_friendly: Optional[bool] = Field(default=None, description="Whether item is vegan-friendly")

    @field_validator('quantity')
    @classmethod
    def validate_quantity_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure quantity is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Quantity cannot be negative')
        return v

    @field_validator('minimum_threshold')
    @classmethod
    def validate_threshold_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure minimum threshold is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Minimum threshold cannot be negative')
        return v

    @field_validator('price')
    @classmethod
    def validate_price_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure price is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Price cannot be negative')
        return v

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: Optional[str]) -> Optional[str]:
        """Ensure unit is a valid UnitType enum value if provided."""
        if v is not None:
            valid_units = [unit.value for unit in UnitType]
            if v not in valid_units:
                raise ValueError(f'Unit must be one of: {", ".join(valid_units)}')
        return v

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        """Ensure category is a valid Category enum value if provided."""
        if v is not None:
            valid_categories = [cat.value for cat in Category]
            if v not in valid_categories:
                raise ValueError(f'Category must be one of: {", ".join(valid_categories)}')
        return v

    @field_validator('storage_location')
    @classmethod
    def validate_storage_location(cls, v: Optional[str]) -> Optional[str]:
        """Ensure storage_location is a valid StorageLocation enum value if provided."""
        if v is not None:
            valid_locations = [loc.value for loc in StorageLocation]
            if v not in valid_locations:
                raise ValueError(f'Storage location must be one of: {", ".join(valid_locations)}')
        return v

    @field_validator('shareability')
    @classmethod
    def validate_shareability(cls, v: Optional[str]) -> Optional[str]:
        """Ensure shareability is a valid Shareability enum value if provided."""
        if v is not None:
            valid_shareability = [share.value for share in Shareability]
            if v not in valid_shareability:
                raise ValueError(f'Shareability must be one of: {", ".join(valid_shareability)}')
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty or whitespace only if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Name cannot be empty')
        return v.strip() if v else None


class InventoryItemResponse(BaseModel):
    """Response schema for inventory item data (includes all fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    quantity: float
    unit: str
    category: str
    vegan_friendly: bool
    storage_location: str
    date_added: datetime
    expiration_date: Optional[datetime]
    frozen_date: Optional[datetime]
    is_staple: bool
    minimum_threshold: Optional[float]
    shareability: str
    reserved_for: Optional[UUID]
    reserved_note: Optional[str]
    added_by: UUID
    price: Optional[float]
    brand: Optional[str]
    preferred_store: Optional[UUID]
    preferred_store_rel: Optional[StoreResponse] = None
    available_at_stores: list[StoreResponse] = []


class InventoryItemListResponse(BaseModel):
    """Response schema for inventory item lists (summary fields only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    quantity: float
    unit: str
    category: str
    storage_location: str
    shareability: str
    is_staple: bool
    expiration_date: Optional[datetime]


class LowStockAlertItem(BaseModel):
    """Response schema for low-stock alert items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    quantity: float
    unit: str
    minimum_threshold: float
    deficit: float = Field(..., description="How many units below threshold (threshold - quantity)")


class ConsumptionRequest(BaseModel):
    """Request schema for consuming inventory items."""

    amount: float = Field(default=1.0, gt=0, description="Amount to consume (must be positive)")
    delete_when_empty: bool = Field(default=True, description="Auto-delete item when quantity reaches 0")


class ConsumptionResponse(BaseModel):
    """Response schema for consumption endpoint."""

    message: str = Field(..., description="Status message")
    deleted: bool = Field(..., description="Whether the item was deleted")
    item: Optional[InventoryItemResponse] = Field(default=None, description="Updated item (null if deleted)")


class BulkInventoryItemCreate(BaseModel):
    """Request schema for bulk creating inventory items."""

    items: list[InventoryItemCreate] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of items to create (1-50 items)"
    )


class BulkInventoryItemResponse(BaseModel):
    """Response schema for bulk create endpoint."""

    items: list[InventoryItemResponse] = Field(..., description="List of created items with IDs")
