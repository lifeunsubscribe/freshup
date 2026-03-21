"""
Unit tests for recipe schema validation.

Tests cover:
- RecipeCreate validation (notes field length)
- RecipeUpdate validation (notes field length)
- AdHocRecipeCreate validation (notes field length)
"""

import pytest
from pydantic import ValidationError
from uuid import uuid4

from src.schemas.recipe import RecipeCreate, RecipeUpdate, AdHocRecipeCreate, InventoryItemUsage


class TestRecipeCreateNotesValidation:
    """Test notes field length validation for RecipeCreate schema."""

    def test_create_recipe_with_valid_notes(self):
        """Test creating a recipe with notes within the length limit."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "notes": "These are some valid notes about the recipe."
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.notes == "These are some valid notes about the recipe."

    def test_create_recipe_with_notes_at_max_length(self):
        """Test creating a recipe with notes at exactly 10,000 characters."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "notes": "A" * 10000  # Exactly at the limit
        }
        recipe = RecipeCreate(**valid_data)
        assert len(recipe.notes) == 10000

    def test_create_recipe_with_notes_exceeding_max_length(self):
        """Test that notes exceeding 10,000 characters raise a validation error."""
        invalid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "notes": "A" * 10001  # One character over the limit
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("notes",)
        assert "String should have at most 10000 characters" in errors[0]["msg"]

    def test_create_recipe_with_empty_notes(self):
        """Test creating a recipe with empty notes (should be valid)."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "notes": ""
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.notes == ""

    def test_create_recipe_with_none_notes(self):
        """Test creating a recipe with None notes (should be valid)."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "notes": None
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.notes is None

    def test_create_recipe_without_notes_field(self):
        """Test creating a recipe without providing notes field (should default to None)."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual"
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.notes is None


class TestRecipeUpdateNotesValidation:
    """Test notes field length validation for RecipeUpdate schema."""

    def test_update_recipe_with_valid_notes(self):
        """Test updating a recipe with notes within the length limit."""
        valid_data = {
            "notes": "Updated notes about the recipe."
        }
        recipe = RecipeUpdate(**valid_data)
        assert recipe.notes == "Updated notes about the recipe."

    def test_update_recipe_with_notes_at_max_length(self):
        """Test updating a recipe with notes at exactly 10,000 characters."""
        valid_data = {
            "notes": "B" * 10000  # Exactly at the limit
        }
        recipe = RecipeUpdate(**valid_data)
        assert len(recipe.notes) == 10000

    def test_update_recipe_with_notes_exceeding_max_length(self):
        """Test that notes exceeding 10,000 characters raise a validation error."""
        invalid_data = {
            "notes": "B" * 10001  # One character over the limit
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeUpdate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("notes",)
        assert "String should have at most 10000 characters" in errors[0]["msg"]

    def test_update_recipe_with_empty_notes(self):
        """Test updating a recipe with empty notes (should be valid)."""
        valid_data = {
            "notes": ""
        }
        recipe = RecipeUpdate(**valid_data)
        assert recipe.notes == ""

    def test_update_recipe_with_none_notes(self):
        """Test updating a recipe with None notes (should be valid)."""
        valid_data = {
            "notes": None
        }
        recipe = RecipeUpdate(**valid_data)
        assert recipe.notes is None


class TestAdHocRecipeCreateNotesValidation:
    """Test notes field length validation for AdHocRecipeCreate schema."""

    def test_create_adhoc_recipe_with_valid_notes(self):
        """Test creating an ad-hoc recipe with notes within the length limit."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "notes": "Made this on the fly with leftover ingredients!",
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 2.0,
                    "unit": "cups"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert recipe.notes == "Made this on the fly with leftover ingredients!"

    def test_create_adhoc_recipe_with_notes_at_max_length(self):
        """Test creating an ad-hoc recipe with notes at exactly 10,000 characters."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "notes": "C" * 10000,  # Exactly at the limit
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 1.0,
                    "unit": "cup"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert len(recipe.notes) == 10000

    def test_create_adhoc_recipe_with_notes_exceeding_max_length(self):
        """Test that notes exceeding 10,000 characters raise a validation error."""
        inventory_item_id = uuid4()
        invalid_data = {
            "name": "Ad-Hoc Recipe",
            "notes": "C" * 10001,  # One character over the limit
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 1.0,
                    "unit": "cup"
                }
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            AdHocRecipeCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("notes",)
        assert "String should have at most 10000 characters" in errors[0]["msg"]

    def test_create_adhoc_recipe_with_empty_notes(self):
        """Test creating an ad-hoc recipe with empty notes (should be valid)."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "notes": "",
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 1.0,
                    "unit": "cup"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert recipe.notes == ""

    def test_create_adhoc_recipe_with_none_notes(self):
        """Test creating an ad-hoc recipe with None notes (should be valid)."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "notes": None,
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 1.0,
                    "unit": "cup"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert recipe.notes is None

    def test_create_adhoc_recipe_without_notes_field(self):
        """Test creating an ad-hoc recipe without providing notes field (should default to None)."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 1.0,
                    "unit": "cup"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert recipe.notes is None


class TestNotesValidationConsistency:
    """Test that notes validation is consistent across all recipe schemas."""

    def test_all_recipe_schemas_have_same_notes_max_length(self):
        """Verify that all recipe schemas enforce the same max_length for notes."""
        # Get field info for notes in each schema
        create_notes_field = RecipeCreate.model_fields['notes']
        update_notes_field = RecipeUpdate.model_fields['notes']
        adhoc_notes_field = AdHocRecipeCreate.model_fields['notes']

        # Extract max_length from Field metadata
        create_max = create_notes_field.metadata[0].max_length if create_notes_field.metadata else None
        update_max = update_notes_field.metadata[0].max_length if update_notes_field.metadata else None
        adhoc_max = adhoc_notes_field.metadata[0].max_length if adhoc_notes_field.metadata else None

        # All should have the same max_length of 10000
        assert create_max == 10000, f"RecipeCreate notes max_length should be 10000, got {create_max}"
        assert update_max == 10000, f"RecipeUpdate notes max_length should be 10000, got {update_max}"
        assert adhoc_max == 10000, f"AdHocRecipeCreate notes max_length should be 10000, got {adhoc_max}"
