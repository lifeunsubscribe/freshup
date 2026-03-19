"""
Unit tests for shared validator functions.

Tests cover the five new consolidated validator functions:
- validate_name_not_empty
- validate_enum_value
- validate_non_negative
- normalize_email
- validate_dietary_profile
"""

import pytest
from enum import Enum
from src.schemas.validators import (
    validate_name_not_empty,
    validate_enum_value,
    validate_non_negative,
    normalize_email,
    validate_dietary_profile,
)


class TestValidateNameNotEmpty:
    """Tests for validate_name_not_empty function."""

    def test_valid_name_with_content(self):
        """Test that a valid name with content is accepted and stripped."""
        result = validate_name_not_empty("  John Doe  ")
        assert result == "John Doe"

    def test_valid_name_without_stripping(self):
        """Test that a valid name without stripping preserves whitespace."""
        result = validate_name_not_empty("  John Doe  ", strip=False)
        assert result == "  John Doe  "

    def test_none_value_returns_none(self):
        """Test that None input returns None."""
        result = validate_name_not_empty(None)
        assert result is None

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Name cannot be empty"):
            validate_name_not_empty("")

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Name cannot be empty"):
            validate_name_not_empty("   ")

    def test_single_character_name(self):
        """Test that single character names are valid."""
        result = validate_name_not_empty("A")
        assert result == "A"


class TestValidateEnumValue:
    """Tests for validate_enum_value function."""

    class MockEnum(Enum):
        """Mock enum for testing."""
        OPTION_A = "option_a"
        OPTION_B = "option_b"
        OPTION_C = "option_c"

    def test_valid_enum_value(self):
        """Test that valid enum values are accepted."""
        result = validate_enum_value("Field", "option_a", self.MockEnum)
        assert result == "option_a"

    def test_invalid_enum_value_raises_error(self):
        """Test that invalid enum value raises ValueError with proper message."""
        with pytest.raises(ValueError, match="Field must be one of: option_a, option_b, option_c. Got: invalid"):
            validate_enum_value("Field", "invalid", self.MockEnum)

    def test_none_value_not_allowed_by_default(self):
        """Test that None raises ValueError when allow_none is False."""
        with pytest.raises(ValueError, match="Field cannot be None"):
            validate_enum_value("Field", None, self.MockEnum)

    def test_none_value_allowed_when_specified(self):
        """Test that None is accepted when allow_none is True."""
        result = validate_enum_value("Field", None, self.MockEnum, allow_none=True)
        assert result is None

    def test_all_enum_values_accepted(self):
        """Test that all values from the enum are accepted."""
        for enum_item in self.MockEnum:
            result = validate_enum_value("Field", enum_item.value, self.MockEnum)
            assert result == enum_item.value

    def test_error_message_includes_invalid_value(self):
        """Test that error message includes the invalid value that was provided."""
        with pytest.raises(ValueError) as exc_info:
            validate_enum_value("Context", "bad_value", self.MockEnum)
        assert "Got: bad_value" in str(exc_info.value)


class TestValidateNonNegative:
    """Tests for validate_non_negative function."""

    def test_positive_value(self):
        """Test that positive values are accepted."""
        result = validate_non_negative("Field", 42.5)
        assert result == 42.5

    def test_zero_value(self):
        """Test that zero is accepted as non-negative."""
        result = validate_non_negative("Field", 0.0)
        assert result == 0.0

    def test_negative_value_raises_error(self):
        """Test that negative values raise ValueError."""
        with pytest.raises(ValueError, match="Field cannot be negative"):
            validate_non_negative("Field", -1.0)

    def test_none_value_allowed_by_default(self):
        """Test that None is accepted when allow_none is True (default)."""
        result = validate_non_negative("Field", None)
        assert result is None

    def test_none_value_not_allowed_when_specified(self):
        """Test that None raises ValueError when allow_none is False."""
        with pytest.raises(ValueError, match="Field cannot be None"):
            validate_non_negative("Field", None, allow_none=False)

    def test_integer_value(self):
        """Test that integer values work correctly."""
        result = validate_non_negative("Field", 10)
        assert result == 10

    def test_very_small_negative_value(self):
        """Test that even very small negative values are rejected."""
        with pytest.raises(ValueError, match="Field cannot be negative"):
            validate_non_negative("Field", -0.0001)


class TestNormalizeEmail:
    """Tests for normalize_email function."""

    def test_uppercase_email(self):
        """Test that uppercase email is converted to lowercase."""
        result = normalize_email("USER@EXAMPLE.COM")
        assert result == "user@example.com"

    def test_mixed_case_email(self):
        """Test that mixed case email is converted to lowercase."""
        result = normalize_email("User@Example.Com")
        assert result == "user@example.com"

    def test_already_lowercase_email(self):
        """Test that already lowercase email remains unchanged."""
        result = normalize_email("user@example.com")
        assert result == "user@example.com"

    def test_email_with_plus_addressing(self):
        """Test that email with plus addressing is normalized correctly."""
        result = normalize_email("User+Tag@Example.Com")
        assert result == "user+tag@example.com"

    def test_email_with_subdomain(self):
        """Test that email with subdomain is normalized correctly."""
        result = normalize_email("User@Mail.Example.Com")
        assert result == "user@mail.example.com"


class TestValidateDietaryProfile:
    """Tests for validate_dietary_profile function."""

    VALID_PROFILES = ["vegetarian", "vegan", "gluten-free", "dairy-free"]

    def test_valid_single_profile(self):
        """Test that a single valid profile is accepted."""
        result = validate_dietary_profile(["vegetarian"], self.VALID_PROFILES)
        assert result == ["vegetarian"]

    def test_valid_multiple_profiles(self):
        """Test that multiple valid profiles are accepted."""
        result = validate_dietary_profile(["vegetarian", "gluten-free"], self.VALID_PROFILES)
        assert result == ["vegetarian", "gluten-free"]

    def test_none_value_returns_none(self):
        """Test that None input returns None."""
        result = validate_dietary_profile(None, self.VALID_PROFILES)
        assert result is None

    def test_invalid_profile_raises_error(self):
        """Test that invalid profile raises ValueError."""
        with pytest.raises(ValueError, match="Invalid dietary profile: invalid"):
            validate_dietary_profile(["invalid"], self.VALID_PROFILES)

    def test_mixed_valid_and_invalid_raises_error(self):
        """Test that mix of valid and invalid profiles raises ValueError."""
        with pytest.raises(ValueError, match="Invalid dietary profile: bad-profile"):
            validate_dietary_profile(["vegetarian", "bad-profile"], self.VALID_PROFILES)

    def test_whitespace_stripping(self):
        """Test that whitespace is stripped from profile values."""
        result = validate_dietary_profile(["  vegetarian  ", "vegan"], self.VALID_PROFILES)
        assert result == ["vegetarian", "vegan"]

    def test_empty_strings_filtered_out(self):
        """Test that empty strings are filtered out."""
        result = validate_dietary_profile(["vegetarian", "", "  ", "vegan"], self.VALID_PROFILES)
        assert result == ["vegetarian", "vegan"]

    def test_all_empty_strings_returns_empty_list(self):
        """Test that list of only empty strings returns empty list."""
        result = validate_dietary_profile(["", "  ", "   "], self.VALID_PROFILES)
        assert result == []

    def test_error_message_includes_valid_options(self):
        """Test that error message includes list of valid options."""
        with pytest.raises(ValueError) as exc_info:
            validate_dietary_profile(["invalid"], self.VALID_PROFILES)
        assert "vegetarian" in str(exc_info.value)
        assert "vegan" in str(exc_info.value)
        assert "gluten-free" in str(exc_info.value)
        assert "dairy-free" in str(exc_info.value)
