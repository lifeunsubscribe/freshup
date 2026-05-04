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
    validate_url_list,
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

    def test_unicode_normalization_nfc(self):
        """Test that Unicode is normalized to NFC form."""
        # "café" with decomposed é (U+0065 U+0301)
        decomposed = "cafe\u0301"
        # "café" with composed é (U+00E9)
        composed = "caf\u00e9"

        result = validate_name_not_empty(decomposed)
        # Result should be normalized to composed form (NFC)
        assert result == composed
        assert result == "café"

    def test_unicode_normalization_with_multiple_accents(self):
        """Test normalization with multiple accented characters."""
        # "crème fraîche" with decomposed accents
        decomposed = "cre\u0300me frai\u0302che"
        # "crème fraîche" with composed accents
        composed = "cr\u00e8me fra\u00eeche"

        result = validate_name_not_empty(decomposed)
        assert result == composed
        assert result == "crème fraîche"

    def test_unicode_normalization_preserves_non_latin(self):
        """Test that normalization works with non-Latin scripts."""
        # Japanese characters (should be unaffected by NFC as they're already normalized)
        japanese = "寿司"
        result = validate_name_not_empty(japanese)
        assert result == japanese

        # Arabic characters
        arabic = "مرحبا"
        result = validate_name_not_empty(arabic)
        assert result == arabic

    def test_unicode_normalization_without_strip(self):
        """Test that normalization works when strip=False."""
        # "café" with decomposed é and surrounding whitespace
        decomposed = "  cafe\u0301  "
        composed = "caf\u00e9"

        result = validate_name_not_empty(decomposed, strip=False)
        # Should normalize but preserve original spacing (not strip)
        assert result == f"  {composed}  "
        assert result == "  café  "


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

    def test_case_sensitivity(self):
        """Test that enum validation is case-sensitive."""
        # Uppercase version should not match lowercase enum value
        with pytest.raises(ValueError, match="Field must be one of: option_a, option_b, option_c. Got: OPTION_A"):
            validate_enum_value("Field", "OPTION_A", self.MockEnum)

        # Mixed case should not match
        with pytest.raises(ValueError, match="Field must be one of: option_a, option_b, option_c. Got: Option_A"):
            validate_enum_value("Field", "Option_A", self.MockEnum)

    def test_empty_string_input(self):
        """Test that empty string is rejected as invalid enum value."""
        with pytest.raises(ValueError, match="Field must be one of: option_a, option_b, option_c. Got: "):
            validate_enum_value("Field", "", self.MockEnum)


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


class TestValidateUrlList:
    """Tests for validate_url_list function."""

    def test_valid_single_url_https(self):
        """Test that a single valid HTTPS URL is accepted."""
        result = validate_url_list("Field", ["https://example.com/image.jpg"])
        assert result == ["https://example.com/image.jpg"]

    def test_valid_single_url_http(self):
        """Test that HTTP URLs are accepted (may redirect to HTTPS)."""
        result = validate_url_list("Field", ["http://example.com/image.jpg"])
        assert result == ["http://example.com/image.jpg"]

    def test_valid_multiple_urls(self):
        """Test that multiple valid URLs are accepted."""
        urls = [
            "https://example.com/photo1.jpg",
            "https://example.com/photo2.png",
            "http://test.com/photo3.jpg"
        ]
        result = validate_url_list("Field", urls)
        assert result == urls

    def test_none_value_returns_none(self):
        """Test that None input returns None."""
        result = validate_url_list("Field", None)
        assert result is None

    def test_empty_list_returns_empty_list(self):
        """Test that empty list returns empty list."""
        result = validate_url_list("Field", [])
        assert result == []

    def test_whitespace_stripping(self):
        """Test that whitespace is stripped from URLs."""
        result = validate_url_list("Field", ["  https://example.com/image.jpg  "])
        assert result == ["https://example.com/image.jpg"]

    def test_empty_strings_filtered_out(self):
        """Test that empty strings are filtered out."""
        result = validate_url_list("Field", ["https://example.com/1.jpg", "", "  ", "https://example.com/2.jpg"])
        assert result == ["https://example.com/1.jpg", "https://example.com/2.jpg"]

    def test_url_with_path_and_query(self):
        """Test that URLs with paths and query parameters are accepted."""
        url = "https://example.com/path/to/image.jpg?size=large&format=png"
        result = validate_url_list("Field", [url])
        assert result == [url]

    def test_url_with_port(self):
        """Test that URLs with port numbers are accepted."""
        url = "https://example.com:8080/image.jpg"
        result = validate_url_list("Field", [url])
        assert result == [url]

    def test_url_with_fragment(self):
        """Test that URLs with fragments are accepted."""
        url = "https://example.com/image.jpg#section"
        result = validate_url_list("Field", [url])
        assert result == [url]

    # Security tests - Invalid protocols

    def test_javascript_protocol_rejected(self):
        """Test that javascript: protocol is rejected."""
        with pytest.raises(ValueError, match="must use http:// or https:// protocol"):
            validate_url_list("Field", ["javascript:alert('xss')"])

    def test_file_protocol_rejected(self):
        """Test that file: protocol is rejected."""
        with pytest.raises(ValueError, match="must use http:// or https:// protocol"):
            validate_url_list("Field", ["file:///etc/passwd"])

    def test_data_protocol_rejected(self):
        """Test that data: protocol is rejected."""
        with pytest.raises(ValueError, match="must use http:// or https:// protocol"):
            validate_url_list("Field", ["data:text/html,<script>alert('xss')</script>"])

    def test_ftp_protocol_rejected(self):
        """Test that ftp: protocol is rejected."""
        with pytest.raises(ValueError, match="must use http:// or https:// protocol"):
            validate_url_list("Field", ["ftp://example.com/file.jpg"])

    def test_missing_protocol_rejected(self):
        """Test that URLs without protocol are rejected."""
        with pytest.raises(ValueError, match="must include protocol"):
            validate_url_list("Field", ["example.com/image.jpg"])

    # Security tests - SSRF protection

    def test_localhost_hostname_rejected(self):
        """Test that localhost is rejected (SSRF protection)."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost"):
            validate_url_list("Field", ["http://localhost/image.jpg"])

    def test_localhost_uppercase_rejected(self):
        """Test that LOCALHOST (uppercase) is rejected."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost"):
            validate_url_list("Field", ["http://LOCALHOST/image.jpg"])

    def test_127_0_0_1_rejected(self):
        """Test that 127.0.0.1 is rejected (SSRF protection)."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost"):
            validate_url_list("Field", ["http://127.0.0.1/image.jpg"])

    def test_127_x_x_x_rejected(self):
        """Test that 127.x.x.x addresses are rejected."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost \\(127\\.x\\.x\\.x\\)"):
            validate_url_list("Field", ["http://127.1.2.3/image.jpg"])

    def test_0_0_0_0_rejected(self):
        """Test that 0.0.0.0 is rejected."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost"):
            validate_url_list("Field", ["http://0.0.0.0/image.jpg"])

    def test_ipv6_loopback_rejected(self):
        """Test that IPv6 loopback (::1) is rejected."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost"):
            validate_url_list("Field", ["http://[::1]/image.jpg"])

    def test_localhost_with_port_rejected(self):
        """Test that localhost with port is rejected."""
        with pytest.raises(ValueError, match="cannot contain URLs targeting localhost"):
            validate_url_list("Field", ["http://localhost:8080/image.jpg"])

    # Length validation tests

    def test_url_exceeds_max_length(self):
        """Test that URLs exceeding max length are rejected."""
        long_url = "https://example.com/" + "a" * 2100  # Exceeds 2048
        with pytest.raises(ValueError, match="cannot exceed 2048 characters"):
            validate_url_list("Field", [long_url])

    def test_url_at_max_length_accepted(self):
        """Test that URLs at exactly max length are accepted."""
        # Create URL exactly at 2048 chars
        base = "https://example.com/"
        path = "a" * (2048 - len(base))
        url = base + path
        result = validate_url_list("Field", [url])
        assert result == [url]

    def test_list_exceeds_max_size(self):
        """Test that URL lists exceeding max size are rejected."""
        urls = [f"https://example.com/photo{i}.jpg" for i in range(15)]  # Exceeds 10
        with pytest.raises(ValueError, match="cannot contain more than 10 URLs"):
            validate_url_list("Field", urls)

    def test_list_at_max_size_accepted(self):
        """Test that URL lists at exactly max size are accepted."""
        urls = [f"https://example.com/photo{i}.jpg" for i in range(10)]  # Exactly 10
        result = validate_url_list("Field", urls)
        assert result == urls

    # Format validation tests

    def test_missing_hostname_rejected(self):
        """Test that URLs without hostname are rejected."""
        with pytest.raises(ValueError, match="must include a hostname"):
            validate_url_list("Field", ["https:///path/to/file.jpg"])

    def test_malformed_url_rejected(self):
        """Test that malformed URLs are handled gracefully."""
        # Most malformed URLs will be caught by missing protocol or hostname checks
        with pytest.raises(ValueError, match="must include protocol"):
            validate_url_list("Field", ["not a url at all"])

    # Edge cases

    def test_url_with_username_password(self):
        """Test that URLs with credentials are accepted (though not recommended)."""
        url = "https://user:pass@example.com/image.jpg"
        result = validate_url_list("Field", [url])
        assert result == [url]

    def test_url_with_international_domain(self):
        """Test that international domain names work."""
        # Using punycode representation
        url = "https://xn--e1afmkfd.xn--p1ai/image.jpg"
        result = validate_url_list("Field", [url])
        assert result == [url]

    def test_error_message_includes_field_name(self):
        """Test that error messages include the field name."""
        with pytest.raises(ValueError, match="rating_photos"):
            validate_url_list("rating_photos", ["javascript:alert()"])

    def test_error_message_truncates_long_urls(self):
        """Test that error messages truncate long URLs for readability."""
        long_url = "https://example.com/" + "a" * 2100
        with pytest.raises(ValueError) as exc_info:
            validate_url_list("Field", [long_url])
        # Should show truncated URL (first 50 chars + ...)
        assert "..." in str(exc_info.value)


# Integration tests for auth schemas using consolidated validators
class TestUserCreateSchemaIntegration:
    """Integration tests for UserCreate schema validation using consolidated validators."""

    def test_valid_user_create_minimal(self):
        """Test creating user with minimal required fields."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "password": "SecurePass123!"
        }
        user = UserCreate(**user_data)
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert user.password == "SecurePass123!"
        assert user.dietary_profile is None
        assert user.allergies is None
        assert user.disliked_ingredients is None
        assert user.favorite_ingredients is None
        assert user.role is None

    def test_valid_user_create_with_all_fields(self):
        """Test creating user with all fields populated."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "Jane Smith",
            "email": "JANE@EXAMPLE.COM",
            "password": "AnotherPass456!",
            "dietary_profile": ["vegetarian", "vegan"],
            "allergies": ["peanuts", "shellfish"],
            "disliked_ingredients": ["olives", "mushrooms"],
            "favorite_ingredients": ["tomatoes", "basil"],
            "role": "coordinator"
        }
        user = UserCreate(**user_data)
        assert user.name == "Jane Smith"
        assert user.email == "jane@example.com"  # Email normalized to lowercase
        assert user.dietary_profile == ["vegetarian", "vegan"]
        assert user.allergies == ["peanuts", "shellfish"]
        assert user.role == "coordinator"

    def test_user_create_email_normalization(self):
        """Test that email is normalized to lowercase."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "Test User",
            "email": "Test.User@EXAMPLE.COM",
            "password": "Password123!"
        }
        user = UserCreate(**user_data)
        assert user.email == "test.user@example.com"

    def test_user_create_name_validation_strips_whitespace(self):
        """Test that name validator strips whitespace."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "  John Doe  ",
            "email": "john@example.com",
            "password": "Password123!"
        }
        user = UserCreate(**user_data)
        assert user.name == "John Doe"

    def test_user_create_name_validation_rejects_empty(self):
        """Test that empty name is rejected."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "   ",
            "email": "john@example.com",
            "password": "Password123!"
        }
        with pytest.raises(ValueError, match="Name cannot be empty"):
            UserCreate(**user_data)

    def test_user_create_role_validation_valid_roles(self):
        """Test that valid role values are accepted."""
        from src.schemas.auth import UserCreate

        for role in ["coordinator", "member"]:
            user_data = {
                "name": "Test User",
                "email": "test@example.com",
                "password": "Password123!",
                "role": role
            }
            user = UserCreate(**user_data)
            assert user.role == role

    def test_user_create_role_validation_invalid_role(self):
        """Test that invalid role is rejected."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123!",
            "role": "admin"
        }
        with pytest.raises(ValueError, match="Role must be one of: coordinator, member"):
            UserCreate(**user_data)

    def test_user_create_dietary_profile_validation(self):
        """Test dietary profile validation with valid and invalid values."""
        from src.schemas.auth import UserCreate

        # Valid profiles
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123!",
            "dietary_profile": ["vegetarian", "vegan"]
        }
        user = UserCreate(**user_data)
        assert user.dietary_profile == ["vegetarian", "vegan"]

        # Invalid profile
        user_data["dietary_profile"] = ["invalid-profile"]
        with pytest.raises(ValueError, match="Invalid dietary profile: invalid-profile"):
            UserCreate(**user_data)

    def test_user_create_dietary_profile_whitespace_handling(self):
        """Test that dietary profile strips whitespace and filters empty strings."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123!",
            "dietary_profile": ["  vegetarian  ", "", "  ", "vegan"]
        }
        user = UserCreate(**user_data)
        assert user.dietary_profile == ["vegetarian", "vegan"]

    def test_user_create_ingredient_lists_validation(self):
        """Test that ingredient lists are validated correctly."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123!",
            "allergies": ["peanuts", "shellfish"],
            "disliked_ingredients": ["olives"],
            "favorite_ingredients": ["tomatoes", "basil"]
        }
        user = UserCreate(**user_data)
        assert user.allergies == ["peanuts", "shellfish"]
        assert user.disliked_ingredients == ["olives"]
        assert user.favorite_ingredients == ["tomatoes", "basil"]

    def test_user_create_ingredient_lists_whitespace_handling(self):
        """Test that ingredient lists strip whitespace and filter empty strings."""
        from src.schemas.auth import UserCreate

        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123!",
            "allergies": ["  peanuts  ", "", "shellfish"]
        }
        user = UserCreate(**user_data)
        assert user.allergies == ["peanuts", "shellfish"]

    def test_user_create_password_validation_complexity(self):
        """Test password complexity validation."""
        from src.schemas.auth import UserCreate

        base_data = {
            "name": "Test User",
            "email": "test@example.com"
        }

        # Valid password
        user = UserCreate(**base_data, password="ValidPass123!")
        assert user.password == "ValidPass123!"

        # Too short
        with pytest.raises(ValueError, match="at least 8 characters"):
            UserCreate(**base_data, password="Short1!")

        # No uppercase
        with pytest.raises(ValueError, match="at least one uppercase letter"):
            UserCreate(**base_data, password="lowercase123!")

        # No lowercase
        with pytest.raises(ValueError, match="at least one lowercase letter"):
            UserCreate(**base_data, password="UPPERCASE123!")

        # No digit
        with pytest.raises(ValueError, match="at least one digit"):
            UserCreate(**base_data, password="NoDigitsHere!")

        # No special character
        with pytest.raises(ValueError, match="at least one special character"):
            UserCreate(**base_data, password="NoSpecial123")

    def test_user_create_password_validation_bcrypt_limit(self):
        """Test that password exceeding bcrypt 72-byte limit is rejected."""
        from src.schemas.auth import UserCreate

        # Create a password that exceeds 72 bytes
        long_password = "A1!" + "a" * 100  # Will exceed 72 bytes
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": long_password
        }
        with pytest.raises(ValueError, match="72 bytes"):
            UserCreate(**user_data)


class TestUserUpdateSchemaIntegration:
    """Integration tests for UserUpdate schema validation using consolidated validators."""

    def test_valid_user_update_single_field(self):
        """Test updating a single field."""
        from src.schemas.auth import UserUpdate

        update_data = {"name": "Updated Name"}
        update = UserUpdate(**update_data)
        assert update.name == "Updated Name"
        assert update.dietary_profile is None
        assert update.allergies is None

    def test_valid_user_update_multiple_fields(self):
        """Test updating multiple fields."""
        from src.schemas.auth import UserUpdate

        update_data = {
            "name": "Updated Name",
            "dietary_profile": ["vegan"],
            "allergies": ["nuts"],
            "disliked_ingredients": ["onions"],
            "favorite_ingredients": ["garlic"]
        }
        update = UserUpdate(**update_data)
        assert update.name == "Updated Name"
        assert update.dietary_profile == ["vegan"]
        assert update.allergies == ["nuts"]
        assert update.disliked_ingredients == ["onions"]
        assert update.favorite_ingredients == ["garlic"]

    def test_user_update_name_validation_strips_whitespace(self):
        """Test that name validator strips whitespace in updates."""
        from src.schemas.auth import UserUpdate

        update_data = {"name": "  Updated Name  "}
        update = UserUpdate(**update_data)
        assert update.name == "Updated Name"

    def test_user_update_name_validation_rejects_empty(self):
        """Test that empty name is rejected in updates."""
        from src.schemas.auth import UserUpdate

        update_data = {"name": "   "}
        with pytest.raises(ValueError, match="Name cannot be empty"):
            UserUpdate(**update_data)

    def test_user_update_dietary_profile_validation(self):
        """Test dietary profile validation in updates."""
        from src.schemas.auth import UserUpdate

        # Valid profiles
        update_data = {"dietary_profile": ["keto", "low_carb"]}
        update = UserUpdate(**update_data)
        assert update.dietary_profile == ["keto", "low_carb"]

        # Invalid profile
        update_data = {"dietary_profile": ["invalid-diet"]}
        with pytest.raises(ValueError, match="Invalid dietary profile: invalid-diet"):
            UserUpdate(**update_data)

    def test_user_update_dietary_profile_whitespace_handling(self):
        """Test that dietary profile handles whitespace in updates."""
        from src.schemas.auth import UserUpdate

        update_data = {"dietary_profile": ["  vegan  ", "", "vegetarian"]}
        update = UserUpdate(**update_data)
        assert update.dietary_profile == ["vegan", "vegetarian"]

    def test_user_update_ingredient_lists_validation(self):
        """Test that ingredient lists are validated in updates."""
        from src.schemas.auth import UserUpdate

        update_data = {
            "allergies": ["soy", "wheat"],
            "disliked_ingredients": ["cilantro"],
            "favorite_ingredients": ["cheese", "bacon"]
        }
        update = UserUpdate(**update_data)
        assert update.allergies == ["soy", "wheat"]
        assert update.disliked_ingredients == ["cilantro"]
        assert update.favorite_ingredients == ["cheese", "bacon"]

    def test_user_update_ingredient_lists_whitespace_handling(self):
        """Test ingredient lists whitespace handling in updates."""
        from src.schemas.auth import UserUpdate

        update_data = {"allergies": ["  soy  ", "", "  wheat  "]}
        update = UserUpdate(**update_data)
        assert update.allergies == ["soy", "wheat"]

    def test_user_update_protected_fields_rejected_email(self):
        """Test that protected field 'email' cannot be updated."""
        from src.schemas.auth import UserUpdate

        update_data = {"email": "newemail@example.com"}
        with pytest.raises(ValueError, match="Cannot modify protected fields: email"):
            UserUpdate(**update_data)

    def test_user_update_protected_fields_rejected_role(self):
        """Test that protected field 'role' cannot be updated."""
        from src.schemas.auth import UserUpdate

        update_data = {"role": "coordinator"}
        with pytest.raises(ValueError, match="Cannot modify protected fields: role"):
            UserUpdate(**update_data)

    def test_user_update_protected_fields_rejected_both(self):
        """Test that both protected fields are rejected together."""
        from src.schemas.auth import UserUpdate

        update_data = {"email": "newemail@example.com", "role": "coordinator"}
        with pytest.raises(ValueError, match="Cannot modify protected fields"):
            UserUpdate(**update_data)

    def test_user_update_unknown_fields_ignored(self):
        """Test that unknown fields are silently ignored due to extra='ignore'."""
        from src.schemas.auth import UserUpdate

        update_data = {
            "name": "Updated Name",
            "unknown_field": "should be ignored",
            "another_unknown": 123
        }
        update = UserUpdate(**update_data)
        assert update.name == "Updated Name"
        # Unknown fields should be ignored, not raise an error

    def test_user_update_empty_update(self):
        """Test that empty update (no fields) is valid."""
        from src.schemas.auth import UserUpdate

        update_data = {}
        update = UserUpdate(**update_data)
        assert update.name is None
        assert update.dietary_profile is None

    def test_user_update_partial_updates_preserve_none(self):
        """Test that unset fields remain None in partial updates."""
        from src.schemas.auth import UserUpdate

        update_data = {"name": "Only Name Updated"}
        update = UserUpdate(**update_data)
        assert update.name == "Only Name Updated"
        assert update.dietary_profile is None
        assert update.allergies is None
        assert update.disliked_ingredients is None
        assert update.favorite_ingredients is None
