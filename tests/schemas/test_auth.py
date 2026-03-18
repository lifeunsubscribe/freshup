"""
Unit tests for authentication schemas.

Tests cover password complexity validation in UserCreate schema.
"""

import pytest
from pydantic import ValidationError
from src.schemas.auth import UserCreate


class TestPasswordComplexityValidation:
    """Tests for password complexity requirements in UserCreate schema."""

    def test_valid_password_with_all_requirements(self):
        """Test that a password meeting all complexity requirements is accepted."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "ValidPass123!",
        }
        user = UserCreate(**user_data)
        assert user.password == "ValidPass123!"

    def test_valid_password_with_various_special_characters(self):
        """Test that passwords with different special characters are accepted."""
        special_chars_passwords = [
            "Password1!",
            "Password1@",
            "Password1#",
            "Password1$",
            "Password1%",
            "Password1^",
            "Password1&",
            "Password1*",
            "Password1(",
            "Password1)",
            "Password1_",
            "Password1+",
            "Password1-",
            "Password1=",
            "Password1[",
            "Password1]",
            "Password1{",
            "Password1}",
            "Password1|",
            "Password1;",
            "Password1:",
            "Password1,",
            "Password1.",
            "Password1<",
            "Password1>",
            "Password1?",
        ]

        for password in special_chars_passwords:
            user_data = {
                "name": "Test User",
                "email": "test@example.com",
                "password": password,
            }
            user = UserCreate(**user_data)
            assert user.password == password

    def test_password_missing_uppercase(self):
        """Test that password without uppercase letter is rejected."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "lowercase123!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "uppercase" in errors[0]["msg"].lower()

    def test_password_missing_lowercase(self):
        """Test that password without lowercase letter is rejected."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "UPPERCASE123!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "lowercase" in errors[0]["msg"].lower()

    def test_password_missing_digit(self):
        """Test that password without digit is rejected."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "NoDigitsHere!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "digit" in errors[0]["msg"].lower()

    def test_password_missing_special_character(self):
        """Test that password without special character is rejected."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "NoSpecialChar123",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "special character" in errors[0]["msg"].lower()

    def test_password_too_short(self):
        """Test that password shorter than 8 characters is rejected."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Short1!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "8 characters" in errors[0]["msg"]

    def test_password_missing_multiple_requirements(self):
        """Test that password missing multiple requirements shows all errors."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "short",  # Missing: length, uppercase, digit, special
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        error_msg = errors[0]["msg"].lower()
        # Should mention multiple missing requirements
        assert "8 characters" in error_msg
        assert "uppercase" in error_msg
        assert "digit" in error_msg
        assert "special character" in error_msg

    def test_password_with_unicode_characters_meets_requirements(self):
        """Test that unicode passwords can meet complexity requirements."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Pässwörd123!",  # Unicode with all requirements
        }
        user = UserCreate(**user_data)
        assert user.password == "Pässwörd123!"

    def test_password_exactly_8_characters_valid(self):
        """Test that password with exactly 8 characters is accepted if it meets all requirements."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Pass123!",  # Exactly 8 characters
        }
        user = UserCreate(**user_data)
        assert user.password == "Pass123!"

    def test_password_exactly_128_characters_valid(self):
        """Test that password with exactly 128 characters is accepted if it meets all requirements."""
        # Create a password with exactly 128 characters that meets all complexity requirements
        password = "A1!" + "a" * 124 + "!"  # 128 chars: uppercase, digit, special chars, lowercase
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password) == 128

    def test_password_with_spaces(self):
        """Test that passwords with spaces are accepted if they meet requirements."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "My Pass123!",  # Contains space
        }
        user = UserCreate(**user_data)
        assert user.password == "My Pass123!"

    def test_password_all_lowercase_rejected(self):
        """Test that all lowercase password is rejected even with other requirements."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "alllowercase123!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert "uppercase" in errors[0]["msg"].lower()

    def test_password_all_uppercase_rejected(self):
        """Test that all uppercase password is rejected even with other requirements."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "ALLUPPERCASE123!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert "lowercase" in errors[0]["msg"].lower()

    def test_password_no_digits_rejected(self):
        """Test that password without any digits is rejected."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "NoDigitsAtAll!",
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert "digit" in errors[0]["msg"].lower()

    def test_password_with_multiple_special_characters(self):
        """Test that password with multiple special characters is accepted."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "P@ssw0rd!#$",
        }
        user = UserCreate(**user_data)
        assert user.password == "P@ssw0rd!#$"

    def test_password_with_numbers_at_end(self):
        """Test that password with numbers at the end is accepted."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password!123",
        }
        user = UserCreate(**user_data)
        assert user.password == "Password!123"

    def test_minimum_valid_password(self):
        """Test the shortest possible valid password."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "Aa1!Aa1!",  # 8 chars, has all requirements
        }
        user = UserCreate(**user_data)
        assert user.password == "Aa1!Aa1!"
