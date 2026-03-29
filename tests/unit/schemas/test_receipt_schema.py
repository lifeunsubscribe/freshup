"""
Unit tests for receipt parsing schemas.

Tests cover validation for ReceiptLineItem and ReceiptParseResult,
including required fields, optional fields, and validation constraints.
"""

import pytest
from datetime import date
from pydantic import ValidationError

from src.schemas.receipt import ReceiptLineItem, ReceiptParseResult


class TestReceiptLineItem:
    """Tests for ReceiptLineItem schema."""

    def test_valid_line_item_with_required_fields_only(self):
        """Test creation with only required field (item_name)."""
        item_data = {
            "item_name": "Organic Bananas",
        }
        item = ReceiptLineItem(**item_data)
        assert item.item_name == "Organic Bananas"
        assert item.quantity is None
        assert item.unit_price is None
        assert item.total_price is None
        assert item.category_guess is None

    def test_valid_line_item_with_all_fields(self):
        """Test creation with all fields populated."""
        item_data = {
            "item_name": "Chicken Breast",
            "quantity": 2.5,
            "unit_price": 5.99,
            "total_price": 14.98,
            "category_guess": "protein",
        }
        item = ReceiptLineItem(**item_data)
        assert item.item_name == "Chicken Breast"
        assert item.quantity == 2.5
        assert item.unit_price == 5.99
        assert item.total_price == 14.98
        assert item.category_guess == "protein"

    def test_item_name_cannot_be_empty(self):
        """Test that item_name cannot be empty or whitespace only."""
        item_data = {
            "item_name": "   ",
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptLineItem(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("item_name",) for error in errors)

    def test_quantity_must_be_positive(self):
        """Test that quantity must be greater than 0 if provided."""
        item_data = {
            "item_name": "Test Item",
            "quantity": 0,
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptLineItem(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

    def test_negative_quantity_is_rejected(self):
        """Test that negative quantity is rejected."""
        item_data = {
            "item_name": "Test Item",
            "quantity": -2.5,
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptLineItem(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

    def test_unit_price_must_be_non_negative(self):
        """Test that unit_price cannot be negative."""
        item_data = {
            "item_name": "Test Item",
            "unit_price": -1.99,
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptLineItem(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("unit_price",) for error in errors)

    def test_total_price_must_be_non_negative(self):
        """Test that total_price cannot be negative."""
        item_data = {
            "item_name": "Test Item",
            "total_price": -5.99,
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptLineItem(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("total_price",) for error in errors)

    def test_zero_prices_are_allowed(self):
        """Test that zero prices are allowed (free items, promotional)."""
        item_data = {
            "item_name": "Free Sample",
            "unit_price": 0.0,
            "total_price": 0.0,
        }
        item = ReceiptLineItem(**item_data)
        assert item.unit_price == 0.0
        assert item.total_price == 0.0

    def test_category_guess_cannot_be_empty_string(self):
        """Test that category_guess cannot be empty or whitespace if provided."""
        item_data = {
            "item_name": "Test Item",
            "category_guess": "   ",
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptLineItem(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("category_guess",) for error in errors)

    def test_item_name_is_normalized(self):
        """Test that item_name whitespace is normalized (NFC form)."""
        item_data = {
            "item_name": "  Café Latte  ",
        }
        item = ReceiptLineItem(**item_data)
        # validate_name_not_empty strips whitespace and normalizes to NFC
        assert item.item_name == "Café Latte"


class TestReceiptParseResult:
    """Tests for ReceiptParseResult schema."""

    def test_valid_receipt_with_all_fields(self):
        """Test creation with complete receipt data."""
        receipt_data = {
            "store_name": "Costco",
            "receipt_date": "2026-03-28",
            "line_items": [
                {
                    "item_name": "Organic Bananas",
                    "quantity": 3.0,
                    "unit_price": 0.59,
                    "total_price": 1.77,
                    "category_guess": "produce",
                },
                {
                    "item_name": "Milk 1 Gallon",
                    "total_price": 3.49,
                    "category_guess": "dairy",
                },
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.store_name == "Costco"
        assert receipt.receipt_date == date(2026, 3, 28)
        assert len(receipt.line_items) == 2
        assert receipt.line_items[0].item_name == "Organic Bananas"
        assert receipt.line_items[1].item_name == "Milk 1 Gallon"

    def test_valid_receipt_without_date(self):
        """Test receipt parsing when date is illegible or missing."""
        receipt_data = {
            "store_name": "King Soopers",
            "receipt_date": None,
            "line_items": [
                {
                    "item_name": "Eggs",
                    "total_price": 2.99,
                },
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.store_name == "King Soopers"
        assert receipt.receipt_date is None
        assert len(receipt.line_items) == 1

    def test_store_name_is_required(self):
        """Test that store_name is required."""
        receipt_data = {
            "receipt_date": "2026-03-28",
            "line_items": [
                {
                    "item_name": "Test Item",
                },
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptParseResult(**receipt_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("store_name",) for error in errors)

    def test_store_name_cannot_be_empty(self):
        """Test that store_name cannot be empty or whitespace only."""
        receipt_data = {
            "store_name": "   ",
            "line_items": [
                {
                    "item_name": "Test Item",
                },
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptParseResult(**receipt_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("store_name",) for error in errors)

    def test_line_items_is_required(self):
        """Test that line_items is required."""
        receipt_data = {
            "store_name": "Test Store",
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptParseResult(**receipt_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("line_items",) for error in errors)

    def test_line_items_cannot_be_empty_list(self):
        """Test that line_items must have at least one item."""
        receipt_data = {
            "store_name": "Test Store",
            "line_items": [],
        }
        with pytest.raises(ValidationError) as exc_info:
            ReceiptParseResult(**receipt_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("line_items",) for error in errors)

    def test_receipt_with_minimal_line_item_data(self):
        """Test receipt with line items that have only item names."""
        receipt_data = {
            "store_name": "Save-A-Lot",
            "line_items": [
                {"item_name": "Item 1"},
                {"item_name": "Item 2"},
                {"item_name": "Item 3"},
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.store_name == "Save-A-Lot"
        assert len(receipt.line_items) == 3
        assert all(item.quantity is None for item in receipt.line_items)
        assert all(item.total_price is None for item in receipt.line_items)

    def test_store_name_is_normalized(self):
        """Test that store_name whitespace is normalized."""
        receipt_data = {
            "store_name": "  Costco  ",
            "line_items": [
                {"item_name": "Test Item"},
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.store_name == "Costco"

    def test_receipt_date_accepts_date_object(self):
        """Test that receipt_date can be a date object."""
        receipt_data = {
            "store_name": "Costco",
            "receipt_date": date(2026, 3, 28),
            "line_items": [
                {"item_name": "Test Item"},
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.receipt_date == date(2026, 3, 28)

    def test_sample_costco_receipt(self):
        """Test parsing a realistic Costco receipt sample."""
        receipt_data = {
            "store_name": "Costco Wholesale",
            "receipt_date": "2026-03-28",
            "line_items": [
                {
                    "item_name": "Organic Bananas",
                    "quantity": 3.0,
                    "unit_price": 0.59,
                    "total_price": 1.77,
                    "category_guess": "produce",
                },
                {
                    "item_name": "Kirkland Signature Milk 1 Gal",
                    "quantity": 2.0,
                    "unit_price": 3.49,
                    "total_price": 6.98,
                    "category_guess": "dairy",
                },
                {
                    "item_name": "Rotisserie Chicken",
                    "quantity": 1.0,
                    "total_price": 4.99,
                    "category_guess": "protein",
                },
                {
                    "item_name": "Kirkland Signature Olive Oil",
                    "total_price": 15.99,
                    "category_guess": "pantry_staple",
                },
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.store_name == "Costco Wholesale"
        assert receipt.receipt_date == date(2026, 3, 28)
        assert len(receipt.line_items) == 4

        # Verify specific items
        bananas = receipt.line_items[0]
        assert bananas.item_name == "Organic Bananas"
        assert bananas.quantity == 3.0
        assert bananas.total_price == 1.77
        assert bananas.category_guess == "produce"

        chicken = receipt.line_items[2]
        assert chicken.item_name == "Rotisserie Chicken"
        assert chicken.quantity == 1.0
        assert chicken.unit_price is None  # Not specified
        assert chicken.total_price == 4.99

    def test_sample_receipt_with_ocr_errors(self):
        """Test parsing a receipt with cleaned OCR errors."""
        receipt_data = {
            "store_name": "King Soopers",
            "receipt_date": None,  # Date was illegible
            "line_items": [
                {
                    "item_name": "Oranges",  # OCR said "0RANGES"
                    "total_price": 3.99,
                    "category_guess": "produce",
                },
                {
                    "item_name": "Chicken Breast",  # OCR said "CHlCKEN"
                    "quantity": 2.5,
                    "unit_price": 5.99,
                    "total_price": 14.98,
                    "category_guess": "protein",
                },
            ],
        }
        receipt = ReceiptParseResult(**receipt_data)
        assert receipt.store_name == "King Soopers"
        assert receipt.receipt_date is None
        assert len(receipt.line_items) == 2
        assert receipt.line_items[0].item_name == "Oranges"
        assert receipt.line_items[1].item_name == "Chicken Breast"

    def test_json_schema_generation(self):
        """Test that model_json_schema() generates valid JSON schema."""
        schema = ReceiptParseResult.model_json_schema()

        # Verify top-level structure
        assert "properties" in schema
        assert "required" in schema

        # Verify required fields
        assert "store_name" in schema["required"]
        assert "line_items" in schema["required"]
        assert "receipt_date" not in schema["required"]  # Optional

        # Verify properties exist
        assert "store_name" in schema["properties"]
        assert "receipt_date" in schema["properties"]
        assert "line_items" in schema["properties"]
