"""
Pydantic schemas for receipt parsing.

Defines the structured output format for LLM-based receipt text parsing.
Used by OllamaClient to validate receipt parsing results from raw OCR text.

Per ADR Phase 4B: Receipt parsing handles messy OCR output from grocery receipts,
extracting store name, date, and line items with quantities and prices.
"""

from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from src.db.models.inventory_item import Category, UnitType, StorageLocation
from src.schemas.validators import validate_name_not_empty, validate_enum_value, validate_non_negative
from src.schemas.inventory import InventoryItemResponse


class ReceiptLineItem(BaseModel):
    """
    A single line item from a parsed grocery receipt.

    Represents one product purchased, with optional quantity and price data.
    Fields are optional to handle incomplete or illegible receipt data.
    """

    item_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the purchased item"
    )
    quantity: float | None = Field(
        default=None,
        gt=0,
        description="Quantity purchased (if specified on receipt)"
    )
    unit_price: float | None = Field(
        default=None,
        ge=0,
        description="Price per unit (if specified on receipt)"
    )
    total_price: float | None = Field(
        default=None,
        ge=0,
        description="Total line item price"
    )
    category_guess: str | None = Field(
        default=None,
        max_length=100,
        description="LLM's best guess at grocery category (e.g., produce, protein, dairy)"
    )

    @field_validator('item_name')
    @classmethod
    def validate_item_name_not_empty(cls, v: str) -> str:
        """Ensure item_name is not empty or whitespace only."""
        result = validate_name_not_empty(v)
        return result  # type: ignore

    @field_validator('quantity')
    @classmethod
    def validate_quantity_positive(cls, v: Optional[float]) -> Optional[float]:
        """Ensure quantity is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @field_validator('unit_price')
    @classmethod
    def validate_unit_price_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure unit_price is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Unit price cannot be negative')
        return v

    @field_validator('total_price')
    @classmethod
    def validate_total_price_non_negative(cls, v: Optional[float]) -> Optional[float]:
        """Ensure total_price is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError('Total price cannot be negative')
        return v

    @field_validator('category_guess')
    @classmethod
    def validate_category_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure category_guess is not empty or whitespace if provided."""
        if v is not None:
            result = validate_name_not_empty(v)
            return result
        return None


class ReceiptParseResult(BaseModel):
    """
    Structured output from receipt parsing.

    Represents the complete parsed receipt with store metadata and line items.
    Used as the response_schema for OllamaClient.complete() during receipt parsing.
    """

    store_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the store from the receipt"
    )
    receipt_date: date | None = Field(
        default=None,
        description="Date of purchase (may be None if illegible or missing)"
    )
    line_items: list[ReceiptLineItem] = Field(
        ...,
        min_length=1,
        description="List of purchased items from the receipt"
    )

    @field_validator('store_name')
    @classmethod
    def validate_store_name_not_empty(cls, v: str) -> str:
        """Ensure store_name is not empty or whitespace only."""
        result = validate_name_not_empty(v)
        return result  # type: ignore

    @field_validator('line_items')
    @classmethod
    def validate_line_items_not_empty(cls, v: list[ReceiptLineItem]) -> list[ReceiptLineItem]:
        """Ensure at least one line item is present."""
        if not v:
            raise ValueError('Receipt must have at least one line item')
        return v


class ReceiptInventoryCandidate(BaseModel):
    """
    A receipt line item ready for inventory confirmation.

    Represents a parsed receipt item that users can review, edit, and confirm
    to add to their inventory. Users can override any field before confirmation.

    This schema bridges the gap between LLM-parsed receipt data (ReceiptLineItem)
    and confirmed inventory items (InventoryItem).
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Item name (user can override parsed value)"
    )
    quantity: float = Field(
        ...,
        gt=0,
        description="Quantity to add to inventory"
    )
    unit: str = Field(
        ...,
        description="Unit of measurement (must be valid UnitType enum value)"
    )
    category: str = Field(
        ...,
        description="Item category (must be valid Category enum value)"
    )
    storage_location: str = Field(
        ...,
        description="Storage location: pantry, fridge, or freezer"
    )
    price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Price of the item (nullable, deferred)"
    )

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v: str) -> str:
        """Ensure name is not empty or whitespace only."""
        result = validate_name_not_empty(v)
        return result  # type: ignore

    @field_validator('quantity')
    @classmethod
    def validate_quantity_field(cls, v: float) -> float:
        """Ensure quantity is positive."""
        result = validate_non_negative('Quantity', v, allow_none=False)
        if result is not None and result <= 0:
            raise ValueError('Quantity must be positive')
        return result  # type: ignore

    @field_validator('price')
    @classmethod
    def validate_price_field(cls, v: Optional[float]) -> Optional[float]:
        """Ensure price is non-negative if provided."""
        return validate_non_negative('Price', v, allow_none=True)

    @field_validator('unit')
    @classmethod
    def validate_unit_field(cls, v: str) -> str:
        """Ensure unit is a valid UnitType enum value."""
        result = validate_enum_value('Unit', v, UnitType, allow_none=False)
        return result  # type: ignore

    @field_validator('category')
    @classmethod
    def validate_category_field(cls, v: str) -> str:
        """Ensure category is a valid Category enum value."""
        result = validate_enum_value('Category', v, Category, allow_none=False)
        return result  # type: ignore

    @field_validator('storage_location')
    @classmethod
    def validate_storage_location_field(cls, v: str) -> str:
        """Ensure storage_location is a valid StorageLocation enum value."""
        result = validate_enum_value('Storage location', v, StorageLocation, allow_none=False)
        return result  # type: ignore


class ReceiptConfirmRequest(BaseModel):
    """
    Request body for receipt confirmation endpoint.

    Contains the list of inventory candidates that the user has reviewed
    and confirmed for addition to their inventory.
    """

    items: list[ReceiptInventoryCandidate] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="List of confirmed items to add to inventory (must not be empty)"
    )

    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v: list[ReceiptInventoryCandidate]) -> list[ReceiptInventoryCandidate]:
        """Ensure at least one item is present."""
        if not v:
            raise ValueError('Must confirm at least one item')
        return v


class ReceiptConfirmResponse(BaseModel):
    """
    Response body for successful receipt confirmation.

    Returns the count of created items and their full details including
    generated IDs and timestamps.
    """

    created_count: int = Field(
        ...,
        ge=0,
        description="Number of inventory items created"
    )
    items: list[InventoryItemResponse] = Field(
        ...,
        description="List of created inventory items with IDs"
    )


class ReceiptSubmitRequest(BaseModel):
    """
    Request body for receipt submission endpoint.

    Accepts receipt text (e.g., from Costco copy-paste) and optional store name
    for async LLM parsing. Creates a ProcessingTask for background processing.
    """

    receipt_text: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="Receipt text content (digital receipt copy-paste or OCR output)"
    )
    store_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional store name for store-specific parsing hints (e.g., 'Costco')"
    )

    @field_validator('receipt_text')
    @classmethod
    def validate_receipt_text_not_empty(cls, v: str) -> str:
        """Ensure receipt_text is not empty or whitespace only."""
        stripped = v.strip()
        if not stripped:
            raise ValueError('Receipt text cannot be empty or only whitespace')
        return stripped

    @field_validator('store_name')
    @classmethod
    def validate_store_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure store_name is not empty or whitespace if provided."""
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError('Store name cannot be empty or only whitespace')
            return stripped
        return None


class ReceiptSubmitResponse(BaseModel):
    """
    Response body for successful receipt submission.

    Returns task ID for polling status and result retrieval.
    """

    task_id: UUID = Field(
        ...,
        description="Processing task ID for status polling"
    )
    status: str = Field(
        ...,
        description="Task status (will be 'pending' on submission)"
    )
    message: str = Field(
        ...,
        description="Human-readable message"
    )
