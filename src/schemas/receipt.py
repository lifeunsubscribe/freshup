"""
Pydantic schemas for receipt parsing.

Defines the structured output format for LLM-based receipt text parsing.
Used by OllamaClient to validate receipt parsing results from raw OCR text.

Per ADR Phase 4B: Receipt parsing handles messy OCR output from grocery receipts,
extracting store name, date, and line items with quantities and prices.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from src.schemas.validators import validate_name_not_empty


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
