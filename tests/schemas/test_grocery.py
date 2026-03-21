"""
Unit tests for grocery schemas.

Tests cover validation for grocery item creation, updates, and enum constraints.
"""

import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from src.schemas.grocery import (
    GroceryItemCreate,
    GroceryItemUpdate,
    GroceryItemResponse,
    StoreGroupedGroceryResponse,
    StoreGroupedItems,
    BulkPurchaseRequest,
)
from src.db.models.grocery_list import GrocerySource
from src.db.models.inventory_item import Category, UnitType, StorageLocation


class TestGroceryItemCreate:
    """Tests for GroceryItemCreate schema."""

    def test_valid_create_with_required_fields(self):
        """Test creation with all required fields."""
        item_data = {
            "item_name": "Milk",
            "quantity": 1.0,
            "unit": "gallon",
        }
        item = GroceryItemCreate(**item_data)
        assert item.item_name == "Milk"
        assert item.quantity == 1.0
        assert item.unit == "gallon"
        assert item.source == "manual"  # Default value
        assert item.target_store is None

    def test_source_defaults_to_manual(self):
        """Test that source field defaults to 'manual'."""
        item_data = {
            "item_name": "Milk",
            "quantity": 1.0,
            "unit": "gallon",
        }
        item = GroceryItemCreate(**item_data)
        assert item.source == "manual"

    def test_valid_create_with_all_fields(self):
        """Test creation with all fields including optional ones."""
        store_id = uuid4()
        item_data = {
            "item_name": "Chicken Breast",
            "quantity": 2.5,
            "unit": "lb",
            "target_store": store_id,
            "source": "manual",
        }
        item = GroceryItemCreate(**item_data)
        assert item.item_name == "Chicken Breast"
        assert item.quantity == 2.5
        assert item.unit == "lb"
        assert item.target_store == store_id
        assert item.source == "manual"

    def test_quantity_must_be_positive(self):
        """Test that quantity must be greater than 0."""
        item_data = {
            "item_name": "Test Item",
            "quantity": 0,
            "unit": "count",
        }
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

    def test_negative_quantity_is_rejected(self):
        """Test that negative quantity is rejected."""
        item_data = {
            "item_name": "Test Item",
            "quantity": -5.0,
            "unit": "count",
        }
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

    def test_invalid_unit_is_rejected(self):
        """Test that invalid unit value is rejected."""
        item_data = {
            "item_name": "Test Item",
            "quantity": 5.0,
            "unit": "invalid_unit",
        }
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("unit",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_source_is_rejected(self):
        """Test that invalid source value is rejected."""
        item_data = {
            "item_name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "source": "invalid_source",
        }
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("source",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_all_valid_units_are_accepted(self):
        """Test that all valid UnitType enum values are accepted."""
        for unit in UnitType:
            item_data = {
                "item_name": "Test Item",
                "quantity": 1.0,
                "unit": unit.value,
            }
            item = GroceryItemCreate(**item_data)
            assert item.unit == unit.value

    def test_all_valid_sources_are_accepted(self):
        """Test that all valid GrocerySource enum values are accepted."""
        for source in GrocerySource:
            item_data = {
                "item_name": "Test Item",
                "quantity": 1.0,
                "unit": "count",
                "source": source.value,
            }
            item = GroceryItemCreate(**item_data)
            assert item.source == source.value

    def test_item_name_cannot_be_empty(self):
        """Test that empty item_name is rejected."""
        item_data = {
            "item_name": "   ",
            "quantity": 5.0,
            "unit": "count",
        }
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("item_name",) for error in errors)
        assert any("cannot be empty" in error["msg"].lower() for error in errors)

    def test_item_name_whitespace_is_stripped(self):
        """Test that whitespace in item_name is stripped."""
        item_data = {
            "item_name": "  Test Item  ",
            "quantity": 5.0,
            "unit": "count",
        }
        item = GroceryItemCreate(**item_data)
        assert item.item_name == "Test Item"


class TestGroceryItemUpdate:
    """Tests for GroceryItemUpdate schema (partial updates)."""

    def test_update_with_single_field(self):
        """Test partial update with only one field."""
        update_data = {"quantity": 10.0}
        update = GroceryItemUpdate(**update_data)
        assert update.quantity == 10.0
        assert update.item_name is None
        assert update.unit is None

    def test_update_with_multiple_fields(self):
        """Test partial update with multiple fields."""
        store_id = uuid4()
        update_data = {
            "quantity": 3.0,
            "target_store": store_id,
        }
        update = GroceryItemUpdate(**update_data)
        assert update.quantity == 3.0
        assert update.target_store == store_id

    def test_update_quantity_must_be_positive(self):
        """Test that quantity must be greater than 0 in updates."""
        update_data = {"quantity": 0}
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

    def test_update_negative_quantity_is_rejected(self):
        """Test that negative quantity is rejected in updates."""
        update_data = {"quantity": -5.0}
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("quantity",) for error in errors)

    def test_update_invalid_unit_is_rejected(self):
        """Test that invalid unit is rejected in updates."""
        update_data = {"unit": "invalid_unit"}
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("unit",) for error in errors)

    def test_update_item_name_cannot_be_empty(self):
        """Test that empty item_name is rejected in updates."""
        update_data = {"item_name": "   "}
        with pytest.raises(ValidationError) as exc_info:
            GroceryItemUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("item_name",) for error in errors)
        assert any("cannot be empty" in error["msg"].lower() for error in errors)

    def test_update_item_name_whitespace_is_stripped(self):
        """Test that whitespace in item_name is stripped during updates."""
        update_data = {"item_name": "  Updated Name  "}
        update = GroceryItemUpdate(**update_data)
        assert update.item_name == "Updated Name"

    def test_update_ignores_unknown_fields(self):
        """Test that unknown fields are silently ignored."""
        update_data = {
            "quantity": 5.0,
            "unknown_field": "should be ignored",
        }
        update = GroceryItemUpdate(**update_data)
        assert update.quantity == 5.0
        assert not hasattr(update, "unknown_field")

    def test_update_does_not_have_source_field(self):
        """Test that source field is not present in update schema (system-managed)."""
        update_data = {"item_name": "Test"}
        update = GroceryItemUpdate(**update_data)
        assert not hasattr(update, "source")

    def test_empty_update_is_valid(self):
        """Test that an empty update object is valid."""
        update = GroceryItemUpdate()
        assert update.item_name is None
        assert update.quantity is None


class TestGroceryItemResponse:
    """Tests for GroceryItemResponse schema."""

    def test_response_schema_has_all_fields(self):
        """Test that response schema includes all expected fields."""
        item_id = uuid4()
        user_id = uuid4()
        store_id = uuid4()
        now = datetime.now()

        response_data = {
            "id": item_id,
            "item_name": "Test Item",
            "quantity": 5.0,
            "unit": "count",
            "source": "manual",
            "target_store": store_id,
            "purchased": False,
            "purchased_by": None,
            "purchased_date": None,
            "added_by": user_id,
        }
        response = GroceryItemResponse(**response_data)
        assert response.id == item_id
        assert response.item_name == "Test Item"
        assert response.quantity == 5.0
        assert response.unit == "count"
        assert response.source == "manual"
        assert response.target_store == store_id
        assert response.purchased is False
        assert response.purchased_by is None
        assert response.purchased_date is None
        assert response.added_by == user_id

    def test_response_with_purchased_fields(self):
        """Test response schema with purchased item."""
        item_id = uuid4()
        user_id = uuid4()
        purchaser_id = uuid4()
        purchase_date = datetime.now()

        response_data = {
            "id": item_id,
            "item_name": "Purchased Item",
            "quantity": 2.0,
            "unit": "lb",
            "source": "manual",
            "target_store": None,
            "purchased": True,
            "purchased_by": purchaser_id,
            "purchased_date": purchase_date,
            "added_by": user_id,
        }
        response = GroceryItemResponse(**response_data)
        assert response.purchased is True
        assert response.purchased_by == purchaser_id
        assert response.purchased_date == purchase_date


class TestStoreGroupedGroceryResponse:
    """Tests for StoreGroupedGroceryResponse schema."""

    def test_store_grouped_response_structure(self):
        """Test that store grouped response has correct structure."""
        store_id_1 = uuid4()
        store_id_2 = uuid4()
        item_id_1 = uuid4()
        item_id_2 = uuid4()
        item_id_3 = uuid4()
        user_id = uuid4()

        item_1 = GroceryItemResponse(
            id=item_id_1,
            item_name="Item 1",
            quantity=1.0,
            unit="count",
            source="manual",
            target_store=store_id_1,
            purchased=False,
            purchased_by=None,
            purchased_date=None,
            added_by=user_id,
        )
        item_2 = GroceryItemResponse(
            id=item_id_2,
            item_name="Item 2",
            quantity=2.0,
            unit="lb",
            source="manual",
            target_store=store_id_2,
            purchased=False,
            purchased_by=None,
            purchased_date=None,
            added_by=user_id,
        )
        item_3 = GroceryItemResponse(
            id=item_id_3,
            item_name="Item 3",
            quantity=3.0,
            unit="count",
            source="manual",
            target_store=None,
            purchased=False,
            purchased_by=None,
            purchased_date=None,
            added_by=user_id,
        )

        store_group_1 = StoreGroupedItems(
            store_id=store_id_1,
            store_name="Store 1",
            items=[item_1],
        )
        store_group_2 = StoreGroupedItems(
            store_id=store_id_2,
            store_name="Store 2",
            items=[item_2],
        )

        response = StoreGroupedGroceryResponse(
            stores=[store_group_1, store_group_2],
            unassigned=[item_3],
        )

        assert len(response.stores) == 2
        assert len(response.unassigned) == 1
        assert response.stores[0].store_id == store_id_1
        assert response.stores[0].store_name == "Store 1"
        assert len(response.stores[0].items) == 1
        assert response.unassigned[0].id == item_id_3

    def test_empty_store_grouped_response(self):
        """Test store grouped response with no items."""
        response = StoreGroupedGroceryResponse(
            stores=[],
            unassigned=[],
        )
        assert len(response.stores) == 0
        assert len(response.unassigned) == 0


class TestBulkPurchaseRequest:
    """Tests for BulkPurchaseRequest schema."""

    def test_valid_bulk_purchase_with_required_fields(self):
        """Test bulk purchase with only required fields."""
        item_id_1 = uuid4()
        item_id_2 = uuid4()

        request_data = {
            "item_ids": [item_id_1, item_id_2],
        }
        request = BulkPurchaseRequest(**request_data)
        assert len(request.item_ids) == 2
        assert request.create_inventory_item is False  # Default
        assert request.storage_location is None
        assert request.category is None

    def test_valid_bulk_purchase_with_inventory_creation(self):
        """Test bulk purchase with inventory item creation."""
        item_id_1 = uuid4()

        request_data = {
            "item_ids": [item_id_1],
            "create_inventory_item": True,
            "storage_location": "pantry",
            "category": "produce",
        }
        request = BulkPurchaseRequest(**request_data)
        assert len(request.item_ids) == 1
        assert request.create_inventory_item is True
        assert request.storage_location == "pantry"
        assert request.category == "produce"

    def test_item_ids_cannot_be_empty(self):
        """Test that item_ids list cannot be empty."""
        request_data = {
            "item_ids": [],
        }
        with pytest.raises(ValidationError) as exc_info:
            BulkPurchaseRequest(**request_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("item_ids",) for error in errors)

    def test_invalid_storage_location_is_rejected(self):
        """Test that invalid storage_location is rejected."""
        item_id = uuid4()
        request_data = {
            "item_ids": [item_id],
            "storage_location": "invalid_location",
        }
        with pytest.raises(ValidationError) as exc_info:
            BulkPurchaseRequest(**request_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("storage_location",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_category_is_rejected(self):
        """Test that invalid category is rejected."""
        item_id = uuid4()
        request_data = {
            "item_ids": [item_id],
            "category": "invalid_category",
        }
        with pytest.raises(ValidationError) as exc_info:
            BulkPurchaseRequest(**request_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("category",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_all_valid_storage_locations_are_accepted(self):
        """Test that all valid StorageLocation enum values are accepted."""
        item_id = uuid4()
        for location in StorageLocation:
            request_data = {
                "item_ids": [item_id],
                "storage_location": location.value,
            }
            request = BulkPurchaseRequest(**request_data)
            assert request.storage_location == location.value

    def test_all_valid_categories_are_accepted(self):
        """Test that all valid Category enum values are accepted."""
        item_id = uuid4()
        for category in Category:
            request_data = {
                "item_ids": [item_id],
                "category": category.value,
            }
            request = BulkPurchaseRequest(**request_data)
            assert request.category == category.value
