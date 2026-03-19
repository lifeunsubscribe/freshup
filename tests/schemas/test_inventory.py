"""
Unit tests for inventory schemas.

Tests cover validation for inventory item creation, updates, and enum constraints.
"""

import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from src.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
)
from src.db.models.inventory_item import Category, UnitType, StorageLocation, Shareability


class TestInventoryItemCreate:
    """Tests for InventoryItemCreate schema."""

    def test_valid_create_with_required_fields(self):
        """Test creation with all required fields."""
        user_id = uuid4()
        item_data = {
            "name": "Tomatoes",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "fridge",
            "added_by": user_id,
        }
        item = InventoryItemCreate(**item_data)
        assert item.name == "Tomatoes"
        assert item.quantity == 5.0
        assert item.unit == "count"
        assert item.category == "produce"
        assert item.storage_location == "fridge"
        assert item.added_by == user_id

    def test_valid_create_with_all_fields(self):
        """Test creation with all fields including optional ones."""
        user_id = uuid4()
        store_id = uuid4()
        expiration = datetime(2025, 12, 31)
        frozen = datetime(2024, 1, 15)

        item_data = {
            "name": "Chicken Breast",
            "quantity": 2.5,
            "unit": "lb",
            "category": "protein",
            "storage_location": "freezer",
            "added_by": user_id,
            "expiration_date": expiration,
            "frozen_date": frozen,
            "is_staple": False,
            "minimum_threshold": 1.0,
            "shareability": "shared",
            "reserved_note": "For dinner party",
            "price": 12.99,
            "brand": "Organic Farms",
            "preferred_store": store_id,
            "vegan_friendly": False,
        }
        item = InventoryItemCreate(**item_data)
        assert item.name == "Chicken Breast"
        assert item.quantity == 2.5
        assert item.expiration_date == expiration
        assert item.price == 12.99

    def test_quantity_must_be_non_negative(self):
        """Test that negative quantity is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": -5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)
        assert any("negative" in error["msg"].lower() for error in errors)

    def test_minimum_threshold_must_be_non_negative(self):
        """Test that negative minimum threshold is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
            "minimum_threshold": -2.0,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("minimum_threshold",) for error in errors)
        assert any("negative" in error["msg"].lower() for error in errors)

    def test_price_must_be_non_negative(self):
        """Test that negative price is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
            "price": -10.50,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("price",) for error in errors)
        assert any("negative" in error["msg"].lower() for error in errors)

    def test_invalid_unit_is_rejected(self):
        """Test that invalid unit value is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "invalid_unit",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("unit",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_category_is_rejected(self):
        """Test that invalid category value is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "invalid_category",
            "storage_location": "pantry",
            "added_by": user_id,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("category",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_storage_location_is_rejected(self):
        """Test that invalid storage_location value is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "garage",
            "added_by": user_id,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("storage_location",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_shareability_is_rejected(self):
        """Test that invalid shareability value is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
            "shareability": "invalid_shareability",
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("shareability",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_all_valid_units_are_accepted(self):
        """Test that all valid UnitType enum values are accepted."""
        user_id = uuid4()
        for unit in UnitType:
            item_data = {
                "name": "Test Item",
                "quantity": 1.0,
                "unit": unit.value,
                "category": "produce",
                "storage_location": "pantry",
                "added_by": user_id,
            }
            item = InventoryItemCreate(**item_data)
            assert item.unit == unit.value

    def test_all_valid_categories_are_accepted(self):
        """Test that all valid Category enum values are accepted."""
        user_id = uuid4()
        for category in Category:
            item_data = {
                "name": "Test Item",
                "quantity": 1.0,
                "unit": "count",
                "category": category.value,
                "storage_location": "pantry",
                "added_by": user_id,
            }
            item = InventoryItemCreate(**item_data)
            assert item.category == category.value

    def test_all_valid_storage_locations_are_accepted(self):
        """Test that all valid StorageLocation enum values are accepted."""
        user_id = uuid4()
        for location in StorageLocation:
            item_data = {
                "name": "Test Item",
                "quantity": 1.0,
                "unit": "count",
                "category": "produce",
                "storage_location": location.value,
                "added_by": user_id,
            }
            item = InventoryItemCreate(**item_data)
            assert item.storage_location == location.value

    def test_all_valid_shareability_values_are_accepted(self):
        """Test that all valid Shareability enum values are accepted."""
        user_id = uuid4()
        for shareability in Shareability:
            item_data = {
                "name": "Test Item",
                "quantity": 1.0,
                "unit": "count",
                "category": "produce",
                "storage_location": "pantry",
                "added_by": user_id,
                "shareability": shareability.value,
            }
            item = InventoryItemCreate(**item_data)
            assert item.shareability == shareability.value

    def test_name_cannot_be_empty(self):
        """Test that empty name is rejected."""
        user_id = uuid4()
        item_data = {
            "name": "   ",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
        }
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)
        assert any("cannot be empty" in error["msg"].lower() for error in errors)

    def test_name_whitespace_is_stripped(self):
        """Test that whitespace in name is stripped."""
        user_id = uuid4()
        item_data = {
            "name": "  Test Item  ",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "pantry",
            "added_by": user_id,
        }
        item = InventoryItemCreate(**item_data)
        assert item.name == "Test Item"


class TestInventoryItemUpdate:
    """Tests for InventoryItemUpdate schema (partial updates)."""

    def test_update_with_single_field(self):
        """Test partial update with only one field."""
        update_data = {"quantity": 10.0}
        update = InventoryItemUpdate(**update_data)
        assert update.quantity == 10.0
        assert update.name is None
        assert update.category is None

    def test_update_with_multiple_fields(self):
        """Test partial update with multiple fields."""
        update_data = {
            "quantity": 3.0,
            "price": 15.99,
            "is_staple": True,
        }
        update = InventoryItemUpdate(**update_data)
        assert update.quantity == 3.0
        assert update.price == 15.99
        assert update.is_staple is True

    def test_update_quantity_must_be_non_negative(self):
        """Test that negative quantity is rejected in updates."""
        update_data = {"quantity": -5.0}
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)
        assert any("negative" in error["msg"].lower() for error in errors)

    def test_update_invalid_unit_is_rejected(self):
        """Test that invalid unit is rejected in updates."""
        update_data = {"unit": "invalid_unit"}
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("unit",) for error in errors)

    def test_update_invalid_category_is_rejected(self):
        """Test that invalid category is rejected in updates."""
        update_data = {"category": "invalid_category"}
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("category",) for error in errors)

    def test_update_invalid_storage_location_is_rejected(self):
        """Test that invalid storage_location is rejected in updates."""
        update_data = {"storage_location": "garage"}
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("storage_location",) for error in errors)

    def test_update_invalid_shareability_is_rejected(self):
        """Test that invalid shareability is rejected in updates."""
        update_data = {"shareability": "invalid_value"}
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("shareability",) for error in errors)

    def test_update_name_cannot_be_empty(self):
        """Test that empty name is rejected in updates."""
        update_data = {"name": "   "}
        with pytest.raises(ValidationError) as exc_info:
            InventoryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)
        assert any("cannot be empty" in error["msg"].lower() for error in errors)

    def test_update_name_whitespace_is_stripped(self):
        """Test that whitespace in name is stripped during updates."""
        update_data = {"name": "  Updated Name  "}
        update = InventoryItemUpdate(**update_data)
        assert update.name == "Updated Name"

    def test_update_ignores_unknown_fields(self):
        """Test that unknown fields are silently ignored."""
        update_data = {
            "quantity": 5.0,
            "unknown_field": "should be ignored",
        }
        update = InventoryItemUpdate(**update_data)
        assert update.quantity == 5.0
        assert not hasattr(update, "unknown_field")

    def test_empty_update_is_valid(self):
        """Test that an empty update object is valid."""
        update = InventoryItemUpdate()
        assert update.name is None
        assert update.quantity is None


class TestInventoryItemResponse:
    """Tests for InventoryItemResponse schema."""

    def test_response_schema_has_all_fields(self):
        """Test that response schema includes all expected fields."""
        item_id = uuid4()
        user_id = uuid4()
        now = datetime.now()

        response_data = {
            "id": item_id,
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "vegan_friendly": True,
            "storage_location": "fridge",
            "date_added": now,
            "expiration_date": None,
            "frozen_date": None,
            "is_staple": False,
            "minimum_threshold": None,
            "shareability": "shared",
            "reserved_for": None,
            "reserved_note": None,
            "added_by": user_id,
            "price": None,
            "brand": None,
            "preferred_store": None,
        }
        response = InventoryItemResponse(**response_data)
        assert response.id == item_id
        assert response.name == "Test Item"
        assert response.date_added == now


class TestInventoryItemListResponse:
    """Tests for InventoryItemListResponse schema (summary fields)."""

    def test_list_response_has_summary_fields(self):
        """Test that list response includes summary fields only."""
        item_id = uuid4()

        response_data = {
            "id": item_id,
            "name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "category": "produce",
            "storage_location": "fridge",
            "shareability": "shared",
            "is_staple": False,
            "expiration_date": None,
        }
        response = InventoryItemListResponse(**response_data)
        assert response.id == item_id
        assert response.name == "Test Item"
        assert response.quantity == 5.0
