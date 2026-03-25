"""
Unit tests for scraper schemas.

Tests cover:
- ScrapedRecipeData validation
- Field constraints and defaults
- Edge cases for optional fields
"""

import pytest
from src.schemas.scraper import ScrapedRecipeData


class TestScrapedRecipeData:
    """Tests for ScrapedRecipeData schema."""

    def test_minimal_valid_data(self):
        """Test creating ScrapedRecipeData with minimal required fields."""
        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import"
        )

        assert data.source_url == "https://example.com/recipe"
        assert data.source_type == "url_import"
        assert data.title is None
        assert data.ingredients == []
        assert data.instructions == []
        assert data.tags == []

    def test_full_valid_data(self):
        """Test creating ScrapedRecipeData with all fields populated."""
        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="hellofresh_web",
            title="Test Recipe",
            image_url="https://example.com/image.jpg",
            prep_time_minutes=15,
            cook_time_minutes=30,
            total_time_minutes=45,
            servings=4,
            ingredients=["1 cup flour", "2 eggs"],
            instructions=["Mix ingredients", "Cook for 30 minutes"],
            tags=["dinner", "easy"],
            nutrients={"calories": "250", "protein": "10g"},
            author="Chef Test",
            site_name="Example Recipe Site"
        )

        assert data.title == "Test Recipe"
        assert data.prep_time_minutes == 15
        assert data.cook_time_minutes == 30
        assert data.servings == 4
        assert len(data.ingredients) == 2
        assert len(data.instructions) == 2
        assert len(data.tags) == 2

    def test_negative_time_validation(self):
        """Test that negative time values are rejected."""
        with pytest.raises(ValueError, match="Value must be non-negative"):
            ScrapedRecipeData(
                source_url="https://example.com/recipe",
                source_type="url_import",
                prep_time_minutes=-5
            )

        with pytest.raises(ValueError, match="Value must be non-negative"):
            ScrapedRecipeData(
                source_url="https://example.com/recipe",
                source_type="url_import",
                cook_time_minutes=-10
            )

    def test_negative_servings_validation(self):
        """Test that negative servings are rejected."""
        with pytest.raises(ValueError, match="servings must be positive"):
            ScrapedRecipeData(
                source_url="https://example.com/recipe",
                source_type="url_import",
                servings=-2
            )

    def test_zero_time_values_allowed(self):
        """Test that zero values are allowed for time fields (e.g., no-cook recipes)."""
        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            prep_time_minutes=0,
            cook_time_minutes=0,
            total_time_minutes=0
        )

        assert data.prep_time_minutes == 0
        assert data.cook_time_minutes == 0
        assert data.total_time_minutes == 0

    def test_zero_servings_rejected(self):
        """Test that zero servings are rejected (semantically invalid)."""
        with pytest.raises(ValueError, match="servings must be positive"):
            ScrapedRecipeData(
                source_url="https://example.com/recipe",
                source_type="url_import",
                servings=0
            )

    def test_title_whitespace_stripping(self):
        """Test that title whitespace is stripped."""
        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            title="  Test Recipe  "
        )

        assert data.title == "Test Recipe"

    def test_title_empty_string_becomes_none(self):
        """Test that empty or whitespace-only title becomes None."""
        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            title="   "
        )

        assert data.title is None

    def test_empty_lists_default_to_empty(self):
        """Test that list fields default to empty lists."""
        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import"
        )

        assert data.ingredients == []
        assert data.instructions == []
        assert data.tags == []
        assert isinstance(data.ingredients, list)
        assert isinstance(data.instructions, list)
        assert isinstance(data.tags, list)

    def test_source_type_values(self):
        """Test various source_type values."""
        source_types = [
            "hellofresh_web",
            "kitchen_sanctuary",
            "url_import",
            "manual"
        ]

        for source_type in source_types:
            data = ScrapedRecipeData(
                source_url="https://example.com/recipe",
                source_type=source_type
            )
            assert data.source_type == source_type

    def test_nutrients_as_dict(self):
        """Test that nutrients can be a dictionary."""
        nutrients = {
            "calories": "250 kcal",
            "protein": "10g",
            "fat": "5g",
            "carbohydrates": "30g"
        }

        data = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            nutrients=nutrients
        )

        assert data.nutrients == nutrients
        assert data.nutrients["calories"] == "250 kcal"

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValueError):
            ScrapedRecipeData(source_type="url_import")  # Missing source_url

        with pytest.raises(ValueError):
            ScrapedRecipeData(source_url="https://example.com/recipe")  # Missing source_type
