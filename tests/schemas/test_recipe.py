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

from src.schemas.recipe import RecipeCreate, RecipeUpdate, AdHocRecipeCreate, InventoryItemUsage, UserRecipeRelationCreate


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


class TestRecipeCreateTagsAndStepsValidation:
    """Test tags and steps field validation for RecipeCreate schema."""

    def test_create_recipe_with_valid_tags(self):
        """Test creating a recipe with valid tags."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": ["vegetarian", "quick", "easy"]
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.tags == ["vegetarian", "quick", "easy"]

    def test_create_recipe_with_valid_steps(self):
        """Test creating a recipe with valid steps."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "steps": ["Preheat oven to 350F", "Mix ingredients", "Bake for 30 minutes"]
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.steps == ["Preheat oven to 350F", "Mix ingredients", "Bake for 30 minutes"]

    def test_create_recipe_with_unicode_tags(self):
        """Test that tags with Unicode characters are normalized and accepted."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": ["café-style", "jalapeño", "crème fraîche"]
        }
        recipe = RecipeCreate(**valid_data)
        assert "café-style" in recipe.tags
        assert "jalapeño" in recipe.tags
        assert "crème fraîche" in recipe.tags

    def test_create_recipe_with_empty_tags_list(self):
        """Test creating a recipe with an empty tags list."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": []
        }
        recipe = RecipeCreate(**valid_data)
        assert recipe.tags == []

    def test_create_recipe_with_whitespace_in_tags(self):
        """Test that whitespace is stripped from tags and empty strings are filtered."""
        valid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": ["  vegetarian  ", "quick", "  ", ""]
        }
        recipe = RecipeCreate(**valid_data)
        # Empty strings and whitespace-only strings should be filtered out
        assert recipe.tags == ["vegetarian", "quick"]

    def test_create_recipe_with_tag_exceeding_max_length(self):
        """Test that tags exceeding max item length raise a validation error."""
        long_tag = "a" * 101  # Exceeds MAX_LIST_ITEM_LENGTH (100)
        invalid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": [long_tag]
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("tags",)
        assert "cannot exceed 100 characters" in str(errors[0]["msg"])

    def test_create_recipe_with_too_many_tags(self):
        """Test that tags list exceeding max size raises a validation error."""
        invalid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": [f"tag{i}" for i in range(101)]  # Exceeds MAX_LIST_SIZE (100)
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("tags",)
        assert "cannot contain more than 100 items" in str(errors[0]["msg"])

    def test_create_recipe_with_invalid_characters_in_tags(self):
        """Test that tags with invalid characters raise a validation error."""
        invalid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "tags": ["valid-tag", "invalid@tag"]  # @ is not allowed
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("tags",)
        assert "can only contain letters, numbers, spaces, and common punctuation" in str(errors[0]["msg"])

    def test_create_recipe_with_control_characters_in_steps(self):
        """Test that steps with Unicode control characters are blocked."""
        invalid_data = {
            "name": "Test Recipe",
            "source_type": "manual",
            "steps": ["Valid step", "Step with\x00control char"]  # Null byte
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("steps",)
        assert "cannot contain control or format characters" in str(errors[0]["msg"])


class TestRecipeUpdateTagsAndStepsValidation:
    """Test tags and steps field validation for RecipeUpdate schema."""

    def test_update_recipe_with_valid_tags(self):
        """Test updating a recipe with valid tags."""
        valid_data = {
            "tags": ["vegan", "gluten-free"]
        }
        recipe = RecipeUpdate(**valid_data)
        assert recipe.tags == ["vegan", "gluten-free"]

    def test_update_recipe_with_valid_steps(self):
        """Test updating a recipe with valid steps."""
        valid_data = {
            "steps": ["Step 1", "Step 2", "Step 3"]
        }
        recipe = RecipeUpdate(**valid_data)
        assert recipe.steps == ["Step 1", "Step 2", "Step 3"]

    def test_update_recipe_with_none_tags(self):
        """Test updating a recipe with None tags (should be valid)."""
        valid_data = {
            "tags": None
        }
        recipe = RecipeUpdate(**valid_data)
        assert recipe.tags is None

    def test_update_recipe_with_tag_exceeding_max_length(self):
        """Test that tags exceeding max item length raise a validation error."""
        long_tag = "b" * 101
        invalid_data = {
            "tags": [long_tag]
        }
        with pytest.raises(ValidationError) as exc_info:
            RecipeUpdate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("tags",)
        assert "cannot exceed 100 characters" in str(errors[0]["msg"])


class TestAdHocRecipeCreateTagsAndStepsValidation:
    """Test tags and steps field validation for AdHocRecipeCreate schema."""

    def test_create_adhoc_recipe_with_valid_tags_and_steps(self):
        """Test creating an ad-hoc recipe with valid tags and steps."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "tags": ["leftover", "quick"],
            "steps": ["Mix everything", "Cook"],
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 2.0,
                    "unit": "cups"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert recipe.tags == ["leftover", "quick"]
        assert recipe.steps == ["Mix everything", "Cook"]

    def test_create_adhoc_recipe_with_empty_tags_and_steps(self):
        """Test creating an ad-hoc recipe with empty tags and steps lists."""
        inventory_item_id = uuid4()
        valid_data = {
            "name": "Ad-Hoc Recipe",
            "tags": [],
            "steps": [],
            "inventory_items": [
                {
                    "inventory_item_id": inventory_item_id,
                    "quantity_used": 1.0,
                    "unit": "cup"
                }
            ]
        }
        recipe = AdHocRecipeCreate(**valid_data)
        assert recipe.tags == []
        assert recipe.steps == []

    def test_create_adhoc_recipe_with_invalid_step(self):
        """Test that steps with invalid characters raise a validation error."""
        inventory_item_id = uuid4()
        invalid_data = {
            "name": "Ad-Hoc Recipe",
            "steps": ["Valid step", "Invalid # step"],  # # is not allowed
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
        assert errors[0]["loc"] == ("steps",)
        assert "can only contain letters, numbers, spaces, and common punctuation" in str(errors[0]["msg"])


class TestUserRecipeRelationCreateRatingPhotosValidation:
    """Test rating_photos field URL validation for UserRecipeRelationCreate schema."""

    def test_create_relation_with_valid_single_photo_url(self):
        """Test creating relation with a single valid photo URL."""
        valid_data = {
            "rating_photos": ["https://example.com/photo1.jpg"]
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert relation.rating_photos == ["https://example.com/photo1.jpg"]

    def test_create_relation_with_multiple_valid_photo_urls(self):
        """Test creating relation with multiple valid photo URLs."""
        valid_data = {
            "rating_photos": [
                "https://example.com/photo1.jpg",
                "https://example.com/photo2.png",
                "http://test.com/photo3.jpg"
            ]
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert len(relation.rating_photos) == 3

    def test_create_relation_with_none_rating_photos(self):
        """Test creating relation with None rating_photos (should be valid)."""
        valid_data = {
            "rating_photos": None
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert relation.rating_photos is None

    def test_create_relation_without_rating_photos_field(self):
        """Test creating relation without rating_photos field (should default to None)."""
        valid_data = {}
        relation = UserRecipeRelationCreate(**valid_data)
        assert relation.rating_photos is None

    def test_create_relation_with_empty_rating_photos_list(self):
        """Test creating relation with empty rating_photos list."""
        valid_data = {
            "rating_photos": []
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert relation.rating_photos == []

    def test_create_relation_rating_photos_strips_whitespace(self):
        """Test that whitespace is stripped from photo URLs."""
        valid_data = {
            "rating_photos": ["  https://example.com/photo.jpg  "]
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert relation.rating_photos == ["https://example.com/photo.jpg"]

    def test_create_relation_rating_photos_filters_empty_strings(self):
        """Test that empty strings are filtered from photo URLs."""
        valid_data = {
            "rating_photos": ["https://example.com/1.jpg", "", "  ", "https://example.com/2.jpg"]
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert relation.rating_photos == ["https://example.com/1.jpg", "https://example.com/2.jpg"]

    # Security tests - Invalid protocols

    def test_create_relation_rating_photos_rejects_javascript_protocol(self):
        """Test that javascript: protocol is rejected in rating_photos."""
        invalid_data = {
            "rating_photos": ["javascript:alert('xss')"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "must use http:// or https:// protocol" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_rejects_file_protocol(self):
        """Test that file: protocol is rejected in rating_photos."""
        invalid_data = {
            "rating_photos": ["file:///etc/passwd"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "must use http:// or https:// protocol" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_rejects_data_protocol(self):
        """Test that data: protocol is rejected in rating_photos."""
        invalid_data = {
            "rating_photos": ["data:text/html,<script>alert('xss')</script>"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "must use http:// or https:// protocol" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_rejects_missing_protocol(self):
        """Test that URLs without protocol are rejected in rating_photos."""
        invalid_data = {
            "rating_photos": ["example.com/photo.jpg"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "must include protocol" in str(errors[0]["msg"])

    # Security tests - SSRF protection

    def test_create_relation_rating_photos_rejects_localhost(self):
        """Test that localhost is rejected in rating_photos (SSRF protection)."""
        invalid_data = {
            "rating_photos": ["http://localhost/photo.jpg"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "cannot contain URLs targeting localhost" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_rejects_127_0_0_1(self):
        """Test that 127.0.0.1 is rejected in rating_photos (SSRF protection)."""
        invalid_data = {
            "rating_photos": ["http://127.0.0.1/photo.jpg"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "cannot contain URLs targeting localhost" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_rejects_127_x_x_x(self):
        """Test that 127.x.x.x addresses are rejected in rating_photos."""
        invalid_data = {
            "rating_photos": ["http://127.1.2.3/photo.jpg"]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "private or internal IP addresses" in str(errors[0]["msg"])

    # Length validation tests

    def test_create_relation_rating_photos_rejects_url_exceeding_max_length(self):
        """Test that URLs exceeding 2048 characters are rejected in rating_photos."""
        long_url = "https://example.com/" + "a" * 2100
        invalid_data = {
            "rating_photos": [long_url]
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "cannot exceed 2048 characters" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_accepts_url_at_max_length(self):
        """Test that URLs at exactly 2048 characters are accepted in rating_photos."""
        base = "https://example.com/"
        path = "a" * (2048 - len(base))
        url = base + path
        valid_data = {
            "rating_photos": [url]
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert len(relation.rating_photos[0]) == 2048

    def test_create_relation_rating_photos_rejects_list_exceeding_max_size(self):
        """Test that rating_photos lists exceeding 10 URLs are rejected."""
        urls = [f"https://example.com/photo{i}.jpg" for i in range(15)]
        invalid_data = {
            "rating_photos": urls
        }
        with pytest.raises(ValidationError) as exc_info:
            UserRecipeRelationCreate(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("rating_photos",)
        assert "cannot contain more than 10 URLs" in str(errors[0]["msg"])

    def test_create_relation_rating_photos_accepts_list_at_max_size(self):
        """Test that rating_photos lists at exactly 10 URLs are accepted."""
        urls = [f"https://example.com/photo{i}.jpg" for i in range(10)]
        valid_data = {
            "rating_photos": urls
        }
        relation = UserRecipeRelationCreate(**valid_data)
        assert len(relation.rating_photos) == 10
