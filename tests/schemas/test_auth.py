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

    def test_password_exactly_72_bytes_valid(self):
        """Test that password with exactly 72 bytes (bcrypt limit) is accepted if it meets all requirements."""
        # Create a password with exactly 72 bytes that meets all complexity requirements
        # Using ASCII characters: 1 byte per character
        password = "A1!" + "a" * 68 + "!"  # 72 chars = 72 bytes: uppercase, digit, special chars, lowercase
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 72

    def test_password_exceeds_72_bytes_rejected(self):
        """Test that password with 73+ bytes is rejected (bcrypt limit)."""
        # Create a password with 73 bytes that meets all complexity requirements except max byte length
        password = "A1!" + "a" * 69 + "!"  # 73 chars = 73 bytes: uppercase, digit, special chars, lowercase
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "72 bytes" in errors[0]["msg"]

    def test_password_with_2byte_utf8_chars_within_72_bytes_valid(self):
        """Test that password with 2-byte UTF-8 characters is accepted if total is within 72 bytes."""
        # 'é' is 2 bytes in UTF-8 (C3 A9)
        # Password: "Passé123!" = 5 ASCII (5 bytes) + 1 two-byte char (2 bytes) + 4 ASCII (4 bytes) = 11 bytes total
        password = "Passé123!"
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 11

    def test_password_with_2byte_utf8_chars_at_72_bytes_valid(self):
        """Test that password with 2-byte UTF-8 characters at exactly 72 bytes is accepted."""
        # 'é' is 2 bytes in UTF-8
        # Build a password: "A1!" (3 bytes) + "é" * 23 (46 bytes) + "a" * 23 (23 bytes) = 72 bytes
        password = "A1!" + "é" * 23 + "a" * 23
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 72

    def test_password_with_2byte_utf8_chars_exceeds_72_bytes_rejected(self):
        """Test that password with 2-byte UTF-8 characters exceeding 72 bytes is rejected."""
        # 'é' is 2 bytes in UTF-8
        # Build a password: "A1!" (3 bytes) + "é" * 24 (48 bytes) + "a" * 23 (23 bytes) = 74 bytes
        password = "A1!" + "é" * 24 + "a" * 23
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "72 bytes" in errors[0]["msg"]
        assert "74 bytes" in errors[0]["msg"]  # Should show actual byte count

    def test_password_with_3byte_utf8_chars_within_72_bytes_valid(self):
        """Test that password with 3-byte UTF-8 characters is accepted if total is within 72 bytes."""
        # '你' (Chinese character) is 3 bytes in UTF-8 (E4 BD A0)
        # Password: "Pass你123!" = 4 ASCII (4 bytes) + 1 three-byte char (3 bytes) + 4 ASCII (4 bytes) = 11 bytes
        password = "Pass你123!"
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 11

    def test_password_with_3byte_utf8_chars_at_72_bytes_valid(self):
        """Test that password with 3-byte UTF-8 characters at exactly 72 bytes is accepted."""
        # '你' is 3 bytes in UTF-8
        # Build a password: "A1!" (3 bytes) + "你" * 15 (45 bytes) + "a" * 24 (24 bytes) = 72 bytes
        password = "A1!" + "你" * 15 + "a" * 24
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 72

    def test_password_with_3byte_utf8_chars_exceeds_72_bytes_rejected(self):
        """Test that password with 3-byte UTF-8 characters exceeding 72 bytes is rejected."""
        # '你' is 3 bytes in UTF-8
        # Build a password: "A1!" (3 bytes) + "你" * 16 (48 bytes) + "a" * 24 (24 bytes) = 75 bytes
        password = "A1!" + "你" * 16 + "a" * 24
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "72 bytes" in errors[0]["msg"]
        assert "75 bytes" in errors[0]["msg"]  # Should show actual byte count

    def test_password_with_4byte_utf8_chars_within_72_bytes_valid(self):
        """Test that password with 4-byte UTF-8 characters (emoji) is accepted if total is within 72 bytes."""
        # '😀' (emoji) is 4 bytes in UTF-8 (F0 9F 98 80)
        # Password: "Pass😀123!" = 4 ASCII (4 bytes) + 1 four-byte char (4 bytes) + 4 ASCII (4 bytes) = 12 bytes
        password = "Pass😀123!"
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 12

    def test_password_with_4byte_utf8_chars_at_72_bytes_valid(self):
        """Test that password with 4-byte UTF-8 characters (emoji) at exactly 72 bytes is accepted."""
        # '😀' is 4 bytes in UTF-8
        # Build a password: "A1!" (3 bytes) + "😀" * 11 (44 bytes) + "a" * 25 (25 bytes) = 72 bytes
        password = "A1!" + "😀" * 11 + "a" * 25
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 72

    def test_password_with_4byte_utf8_chars_exceeds_72_bytes_rejected(self):
        """Test that password with 4-byte UTF-8 characters (emoji) exceeding 72 bytes is rejected."""
        # '😀' is 4 bytes in UTF-8
        # Build a password: "A1!" (3 bytes) + "😀" * 12 (48 bytes) + "a" * 25 (25 bytes) = 76 bytes
        password = "A1!" + "😀" * 12 + "a" * 25
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "72 bytes" in errors[0]["msg"]
        assert "76 bytes" in errors[0]["msg"]  # Should show actual byte count

    def test_password_with_mixed_multibyte_chars_at_72_bytes_valid(self):
        """Test password with mixed multi-byte UTF-8 characters at exactly 72 bytes is accepted."""
        # Mix of 2-byte (é), 3-byte (你), and 4-byte (😀) characters
        # "A1!" (3 bytes) + "é" * 10 (20 bytes) + "你" * 10 (30 bytes) + "😀" * 4 (16 bytes) + "a" (1 byte) + "!" (1 byte) + "b" (1 byte) = 72 bytes
        password = "A1!" + "é" * 10 + "你" * 10 + "😀" * 4 + "ab!"
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        user = UserCreate(**user_data)
        assert user.password == password
        assert len(user.password.encode('utf-8')) == 72

    def test_password_with_mixed_multibyte_chars_exceeds_72_bytes_rejected(self):
        """Test password with mixed multi-byte UTF-8 characters exceeding 72 bytes is rejected."""
        # Mix of 2-byte (é), 3-byte (你), and 4-byte (😀) characters
        # "A1!" (3 bytes) + "é" * 10 (20 bytes) + "你" * 10 (30 bytes) + "😀" * 5 (20 bytes) = 73 bytes
        password = "A1!" + "é" * 10 + "你" * 10 + "😀" * 5
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "password": password,
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert "72 bytes" in errors[0]["msg"]
        assert "73 bytes" in errors[0]["msg"]  # Should show actual byte count

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
