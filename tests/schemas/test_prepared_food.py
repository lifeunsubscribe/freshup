"""
Unit tests for prepared food schemas.

Tests cover validation for prepared food creation, updates, and enum constraints.
"""

import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from src.schemas.prepared_food import (
    PreparedFoodCreate,
    PreparedFoodUpdate,
    PreparedFoodResponse,
    PreparedFoodListResponse,
    PreparedFoodConsumptionResponse,
    ConsumptionRequest,
)
from src.db.models.prepared_food import PreparedFoodType
from src.db.models.inventory_item import StorageLocation, Shareability


class TestPreparedFoodCreate:
    """Tests for PreparedFoodCreate schema."""

    def test_valid_create_with_required_fields(self):
        """Test creation with all required fields."""
        item_data = {
            "name": "Leftover Pasta",
            "type": "complete_meal",
            "servings_remaining": 3.0,
            "storage_location": "fridge",
        }
        item = PreparedFoodCreate(**item_data)
        assert item.name == "Leftover Pasta"
        assert item.type == "complete_meal"
        assert item.servings_remaining == 3.0
        assert item.storage_location == "fridge"
        assert item.shareability == Shareability.shared.value  # Default value
        assert item.source_recipe is None
        assert item.estimated_expiration is None
        assert item.notes is None

    def test_valid_create_with_all_fields(self):
        """Test creation with all fields including optional ones."""
        recipe_id = uuid4()
        expiration = datetime(2025, 12, 31)

        item_data = {
            "name": "Batch Cooked Quinoa",
            "source_recipe": recipe_id,
            "type": "batch_portion",
            "servings_remaining": 8.0,
            "storage_location": "fridge",
            "estimated_expiration": expiration,
            "shareability": "shared",
            "notes": "For meal prep this week",
        }
        item = PreparedFoodCreate(**item_data)
        assert item.name == "Batch Cooked Quinoa"
        assert item.source_recipe == recipe_id
        assert item.type == "batch_portion"
        assert item.servings_remaining == 8.0
        assert item.storage_location == "fridge"
        assert item.estimated_expiration == expiration
        assert item.shareability == "shared"
        assert item.notes == "For meal prep this week"

    def test_servings_remaining_must_be_non_negative(self):
        """Test that negative servings_remaining is rejected."""
        item_data = {
            "name": "Test Item",
            "type": "complete_meal",
            "servings_remaining": -2.0,
            "storage_location": "fridge",
        }
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("servings_remaining",) for error in errors)
        assert any("negative" in error["msg"].lower() for error in errors)

    def test_invalid_type_is_rejected(self):
        """Test that invalid PreparedFoodType value is rejected."""
        item_data = {
            "name": "Test Item",
            "type": "invalid_type",
            "servings_remaining": 2.0,
            "storage_location": "fridge",
        }
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("type",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_storage_location_is_rejected(self):
        """Test that invalid storage_location value is rejected."""
        item_data = {
            "name": "Test Item",
            "type": "complete_meal",
            "servings_remaining": 2.0,
            "storage_location": "garage",
        }
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("storage_location",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_invalid_shareability_is_rejected(self):
        """Test that invalid shareability value is rejected."""
        item_data = {
            "name": "Test Item",
            "type": "complete_meal",
            "servings_remaining": 2.0,
            "storage_location": "fridge",
            "shareability": "invalid_shareability",
        }
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("shareability",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_empty_name_is_rejected(self):
        """Test that empty name is rejected."""
        item_data = {
            "name": "   ",
            "type": "complete_meal",
            "servings_remaining": 2.0,
            "storage_location": "fridge",
        }
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodCreate(**item_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_prepared_by_not_in_create_schema(self):
        """Test that prepared_by field is excluded from Create schema (system-managed)."""
        # Verify field doesn't exist in schema
        assert "prepared_by" not in PreparedFoodCreate.model_fields

        # Extra fields are ignored by default in Pydantic, so prepared_by will be silently dropped
        item_data = {
            "name": "Test Item",
            "type": "complete_meal",
            "servings_remaining": 2.0,
            "storage_location": "fridge",
            "prepared_by": uuid4(),  # Should be ignored
        }
        item = PreparedFoodCreate(**item_data)
        # Verify the created item doesn't have prepared_by attribute
        assert not hasattr(item, "prepared_by") or "prepared_by" not in item.model_fields


class TestPreparedFoodUpdate:
    """Tests for PreparedFoodUpdate schema."""

    def test_partial_update_with_single_field(self):
        """Test partial update with only one field."""
        update_data = {"servings_remaining": 1.5}
        update = PreparedFoodUpdate(**update_data)
        assert update.servings_remaining == 1.5
        assert update.name is None
        assert update.type is None
        assert update.storage_location is None

    def test_partial_update_with_multiple_fields(self):
        """Test partial update with multiple fields."""
        update_data = {
            "servings_remaining": 1.0,
            "storage_location": "freezer",
            "notes": "Moving to freezer for longer storage",
        }
        update = PreparedFoodUpdate(**update_data)
        assert update.servings_remaining == 1.0
        assert update.storage_location == "freezer"
        assert update.notes == "Moving to freezer for longer storage"

    def test_update_with_invalid_enum_is_rejected(self):
        """Test that invalid enum values are rejected in updates."""
        update_data = {"type": "invalid_type"}
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("type",) for error in errors)
        assert any("must be one of" in error["msg"].lower() for error in errors)

    def test_update_with_negative_servings_is_rejected(self):
        """Test that negative servings_remaining is rejected in updates."""
        update_data = {"servings_remaining": -1.0}
        with pytest.raises(ValidationError) as exc_info:
            PreparedFoodUpdate(**update_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("servings_remaining",) for error in errors)
        assert any("negative" in error["msg"].lower() for error in errors)


class TestPreparedFoodResponse:
    """Tests for PreparedFoodResponse schema."""

    def test_response_includes_all_fields(self):
        """Test that response schema includes all model fields."""
        item_id = uuid4()
        user_id = uuid4()
        recipe_id = uuid4()
        date_prepared = datetime(2025, 3, 15, 12, 0, 0)
        expiration = datetime(2025, 3, 20, 12, 0, 0)

        response_data = {
            "id": item_id,
            "name": "Leftover Soup",
            "source_recipe": recipe_id,
            "type": "complete_meal",
            "servings_remaining": 4.0,
            "storage_location": "fridge",
            "date_prepared": date_prepared,
            "estimated_expiration": expiration,
            "shareability": "shared",
            "prepared_by": user_id,
            "notes": "Very tasty",
        }
        response = PreparedFoodResponse(**response_data)
        assert response.id == item_id
        assert response.name == "Leftover Soup"
        assert response.source_recipe == recipe_id
        assert response.type == "complete_meal"
        assert response.servings_remaining == 4.0
        assert response.storage_location == "fridge"
        assert response.date_prepared == date_prepared
        assert response.estimated_expiration == expiration
        assert response.shareability == "shared"
        assert response.prepared_by == user_id
        assert response.notes == "Very tasty"


class TestPreparedFoodListResponse:
    """Tests for PreparedFoodListResponse schema."""

    def test_list_response_includes_summary_fields(self):
        """Test that list response includes summary fields for list views."""
        item_id = uuid4()
        expiration = datetime(2025, 3, 20, 12, 0, 0)

        response_data = {
            "id": item_id,
            "name": "Batch Rice",
            "type": "batch_portion",
            "servings_remaining": 6.0,
            "storage_location": "fridge",
            "estimated_expiration": expiration,
            "shareability": "shared",
        }
        response = PreparedFoodListResponse(**response_data)
        assert response.id == item_id
        assert response.name == "Batch Rice"
        assert response.type == "batch_portion"
        assert response.servings_remaining == 6.0
        assert response.storage_location == "fridge"
        assert response.estimated_expiration == expiration
        assert response.shareability == "shared"


class TestPreparedFoodConsumptionResponse:
    """Tests for PreparedFoodConsumptionResponse schema."""

    def test_consumption_response_with_deleted_item(self):
        """Test consumption response when item is deleted."""
        response_data = {
            "message": "Item fully consumed and deleted",
            "deleted": True,
            "item": None,
        }
        response = PreparedFoodConsumptionResponse(**response_data)
        assert response.message == "Item fully consumed and deleted"
        assert response.deleted is True
        assert response.item is None

    def test_consumption_response_with_remaining_item(self):
        """Test consumption response when item has remaining servings."""
        item_id = uuid4()
        user_id = uuid4()
        date_prepared = datetime(2025, 3, 15, 12, 0, 0)

        item_data = {
            "id": item_id,
            "name": "Leftover Chili",
            "source_recipe": None,
            "type": "complete_meal",
            "servings_remaining": 2.0,
            "storage_location": "fridge",
            "date_prepared": date_prepared,
            "estimated_expiration": None,
            "shareability": "shared",
            "prepared_by": user_id,
            "notes": None,
        }

        response_data = {
            "message": "Consumed 1.0 servings, 2.0 remaining",
            "deleted": False,
            "item": item_data,
        }
        response = PreparedFoodConsumptionResponse(**response_data)
        assert response.message == "Consumed 1.0 servings, 2.0 remaining"
        assert response.deleted is False
        assert response.item is not None
        assert response.item.servings_remaining == 2.0


class TestConsumptionRequest:
    """Tests for ConsumptionRequest schema (imported from inventory)."""

    def test_consumption_request_import_works(self):
        """Test that ConsumptionRequest can be imported from prepared_food schemas."""
        # Verify import works
        assert ConsumptionRequest is not None

        # Test basic usage
        request_data = {"amount": 1.5, "delete_when_empty": True}
        request = ConsumptionRequest(**request_data)
        assert request.amount == 1.5
        assert request.delete_when_empty is True

    def test_consumption_request_defaults(self):
        """Test ConsumptionRequest default values."""
        request = ConsumptionRequest()
        assert request.amount == 1.0
        assert request.delete_when_empty is True
