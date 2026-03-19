"""
Unit tests for shared validation functions.

Tests cover the validate_enum_value function and other validators in the validators module.
"""

import pytest
from enum import Enum
from fastapi import HTTPException

from src.schemas.validators import validate_enum_value
from src.db.models.inventory_item import Category, StorageLocation, Shareability


class TestEnum(str, Enum):
    """Test enum for validation testing."""
    option_a = "option_a"
    option_b = "option_b"
    option_c = "option_c"


class TestValidateEnumValue:
    """Tests for validate_enum_value function."""

    def test_valid_enum_value_does_not_raise(self):
        """Test that a valid enum value does not raise an exception."""
        # Should not raise
        validate_enum_value("test_field", "option_a", TestEnum)
        validate_enum_value("test_field", "option_b", TestEnum)
        validate_enum_value("test_field", "option_c", TestEnum)

    def test_invalid_enum_value_raises_http_exception(self):
        """Test that an invalid enum value raises HTTPException with 422 status."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("test_field", "invalid_value", TestEnum)

        assert exc_info.value.status_code == 422
        assert "Invalid test_field" in exc_info.value.detail
        assert "option_a, option_b, option_c" in exc_info.value.detail

    def test_error_message_includes_field_name(self):
        """Test that error message includes the field name."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("my_custom_field", "bad_value", TestEnum)

        assert "Invalid my_custom_field" in exc_info.value.detail

    def test_error_message_lists_valid_values(self):
        """Test that error message lists all valid enum values."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("test_field", "bad_value", TestEnum)

        detail = exc_info.value.detail
        assert "option_a" in detail
        assert "option_b" in detail
        assert "option_c" in detail
        assert "Must be one of:" in detail

    def test_category_enum_valid_values(self):
        """Test validate_enum_value with Category enum - valid values."""
        # Test a few valid Category values
        validate_enum_value("category", "produce", Category)
        validate_enum_value("category", "protein", Category)
        validate_enum_value("category", "dairy", Category)
        validate_enum_value("category", "frozen", Category)

    def test_category_enum_invalid_value(self):
        """Test validate_enum_value with Category enum - invalid value."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("category", "invalid_category", Category)

        assert exc_info.value.status_code == 422
        assert "Invalid category" in exc_info.value.detail
        assert "produce" in exc_info.value.detail

    def test_storage_location_enum_valid_values(self):
        """Test validate_enum_value with StorageLocation enum - valid values."""
        validate_enum_value("storage_location", "pantry", StorageLocation)
        validate_enum_value("storage_location", "fridge", StorageLocation)
        validate_enum_value("storage_location", "freezer", StorageLocation)

    def test_storage_location_enum_invalid_value(self):
        """Test validate_enum_value with StorageLocation enum - invalid value."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("storage_location", "garage", StorageLocation)

        assert exc_info.value.status_code == 422
        assert "Invalid storage_location" in exc_info.value.detail

    def test_shareability_enum_valid_values(self):
        """Test validate_enum_value with Shareability enum - valid values."""
        validate_enum_value("shareability", "shared", Shareability)
        validate_enum_value("shareability", "reserved", Shareability)
        validate_enum_value("shareability", "personal", Shareability)

    def test_shareability_enum_invalid_value(self):
        """Test validate_enum_value with Shareability enum - invalid value."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("shareability", "public", Shareability)

        assert exc_info.value.status_code == 422
        assert "Invalid shareability" in exc_info.value.detail

    def test_case_sensitive_validation(self):
        """Test that enum validation is case-sensitive."""
        # "Produce" with capital P should not match "produce"
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("category", "Produce", Category)

        assert exc_info.value.status_code == 422

    def test_whitespace_not_trimmed(self):
        """Test that whitespace is not automatically trimmed from values."""
        # " produce " with spaces should not match "produce"
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("category", " produce ", Category)

        assert exc_info.value.status_code == 422

    def test_empty_string_raises_exception(self):
        """Test that empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("category", "", Category)

        assert exc_info.value.status_code == 422

    def test_all_category_values_accepted(self):
        """Test that all valid Category enum values are accepted."""
        for category in Category:
            # Should not raise
            validate_enum_value("category", category.value, Category)

    def test_all_storage_location_values_accepted(self):
        """Test that all valid StorageLocation enum values are accepted."""
        for location in StorageLocation:
            # Should not raise
            validate_enum_value("storage_location", location.value, StorageLocation)

    def test_all_shareability_values_accepted(self):
        """Test that all valid Shareability enum values are accepted."""
        for shareability in Shareability:
            # Should not raise
            validate_enum_value("shareability", shareability.value, Shareability)

    def test_similar_but_different_value_rejected(self):
        """Test that similar but non-matching values are rejected."""
        # "produce1" is similar to "produce" but should be rejected
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("category", "produce1", Category)

        assert exc_info.value.status_code == 422

    def test_partial_match_rejected(self):
        """Test that partial matches are rejected."""
        # "prod" is a partial match of "produce" but should be rejected
        with pytest.raises(HTTPException) as exc_info:
            validate_enum_value("category", "prod", Category)

        assert exc_info.value.status_code == 422
