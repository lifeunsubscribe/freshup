"""
Unit tests for authentication service password hashing utilities.

Tests cover:
- Happy path: hash and verify correct password
- Negative cases: verify incorrect password returns False
- Edge cases: empty string, unicode passwords, very long passwords
- Hash format validation
- Input validation
- Exception handling for malformed hashes
"""

import pytest
from src.services.auth_service import hash_password, verify_password


class TestHashPassword:
    """Tests for the hash_password function."""

    def test_hash_password_returns_bcrypt_format(self):
        """Test that hash_password returns a valid bcrypt hash format."""
        password = "test_password_123"
        hashed = hash_password(password)

        # Bcrypt hashes should start with $2b$ (bcrypt prefix)
        assert hashed.startswith("$2b$12$"), "Hash should start with $2b$12$"
        # Bcrypt hashes should be 60 characters long
        assert len(hashed) == 60, "Bcrypt hash should be 60 characters"

    def test_hash_password_creates_unique_hashes(self):
        """Test that same password generates different hashes (due to salt)."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2, "Same password should create different hashes"

    def test_hash_password_with_unicode_characters(self):
        """Test that passwords with unicode characters are handled correctly."""
        unicode_password = "pässwörd_日本語_🔒"
        hashed = hash_password(unicode_password)

        assert hashed.startswith("$2b$12$")
        assert verify_password(unicode_password, hashed)

    def test_hash_password_with_special_characters(self):
        """Test passwords with special characters."""
        special_password = "p@ssw0rd!#$%^&*()"
        hashed = hash_password(special_password)

        assert hashed.startswith("$2b$12$")
        assert verify_password(special_password, hashed)

    def test_hash_password_rejects_none(self):
        """Test that hash_password raises ValueError for None input."""
        with pytest.raises(ValueError, match="Password cannot be None"):
            hash_password(None)

    def test_hash_password_rejects_empty_string(self):
        """Test that hash_password raises ValueError for empty string."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")

    def test_hash_password_rejects_whitespace_only(self):
        """Test that hash_password raises ValueError for whitespace-only string."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("   ")

    def test_hash_password_rejects_too_long(self):
        """Test that hash_password raises ValueError for passwords > 72 bytes."""
        # Create a password longer than 72 characters
        long_password = "a" * 73
        with pytest.raises(ValueError, match="Password exceeds maximum length"):
            hash_password(long_password)

    def test_hash_password_accepts_max_length(self):
        """Test that hash_password accepts passwords at the 72-byte limit."""
        max_length_password = "a" * 72
        hashed = hash_password(max_length_password)

        assert hashed.startswith("$2b$12$")
        assert verify_password(max_length_password, hashed)


class TestVerifyPassword:
    """Tests for the verify_password function."""

    def test_verify_password_correct_password(self):
        """Test that verify_password returns True for correct password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect_password(self):
        """Test that verify_password returns False for incorrect password."""
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(correct_password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "Password123"
        hashed = hash_password(password)

        assert verify_password("password123", hashed) is False
        assert verify_password("PASSWORD123", hashed) is False

    def test_verify_password_with_unicode(self):
        """Test verification with unicode passwords."""
        password = "pässwörd_日本語"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("pässwörd_日本", hashed) is False

    def test_verify_password_returns_false_for_none_password(self):
        """Test that verify_password returns False for None password."""
        hashed = hash_password("valid_password")
        assert verify_password(None, hashed) is False

    def test_verify_password_returns_false_for_none_hash(self):
        """Test that verify_password returns False for None hash."""
        assert verify_password("password", None) is False

    def test_verify_password_returns_false_for_empty_password(self):
        """Test that verify_password returns False for empty password."""
        hashed = hash_password("valid_password")
        assert verify_password("", hashed) is False

    def test_verify_password_returns_false_for_empty_hash(self):
        """Test that verify_password returns False for empty hash."""
        assert verify_password("password", "") is False

    def test_verify_password_returns_false_for_whitespace_password(self):
        """Test that verify_password returns False for whitespace-only password."""
        hashed = hash_password("valid_password")
        assert verify_password("   ", hashed) is False

    def test_verify_password_returns_false_for_whitespace_hash(self):
        """Test that verify_password returns False for whitespace-only hash."""
        assert verify_password("password", "   ") is False

    def test_verify_password_handles_malformed_hash(self):
        """Test that verify_password returns False for malformed hash (fail closed)."""
        malformed_hashes = [
            "not_a_bcrypt_hash",
            "$2b$invalid",
            "short",
            "$2a$12$invalid_format",
            "random_string_12345678901234567890123456789012345678901234",
        ]

        for malformed in malformed_hashes:
            assert verify_password("password", malformed) is False, \
                f"Should return False for malformed hash: {malformed}"

    def test_verify_password_with_correct_long_password(self):
        """Test verification with passwords at the maximum length."""
        long_password = "a" * 72
        hashed = hash_password(long_password)

        assert verify_password(long_password, hashed) is True
        assert verify_password("a" * 71, hashed) is False


class TestPasswordHashingIntegration:
    """Integration tests for the password hashing workflow."""

    def test_full_password_lifecycle(self):
        """Test complete password creation and verification workflow."""
        original_password = "user_password_123"

        # Hash the password
        hashed = hash_password(original_password)

        # Verify correct password
        assert verify_password(original_password, hashed) is True

        # Verify incorrect password
        assert verify_password("wrong_password", hashed) is False

    def test_multiple_users_same_password(self):
        """Test that same password for different users creates different hashes."""
        password = "common_password"

        # Simulate two users with same password
        user1_hash = hash_password(password)
        user2_hash = hash_password(password)

        # Hashes should be different (different salts)
        assert user1_hash != user2_hash

        # But both should verify correctly
        assert verify_password(password, user1_hash) is True
        assert verify_password(password, user2_hash) is True

    def test_timing_safe_comparison(self):
        """Test that verify_password uses timing-safe comparison (via bcrypt)."""
        # This is more of a documentation test - bcrypt.checkpw is timing-safe
        password = "password123"
        hashed = hash_password(password)

        # All these should take similar time (bcrypt handles this internally)
        assert verify_password("p", hashed) is False
        assert verify_password("password12", hashed) is False
        assert verify_password("password123x", hashed) is False
        assert verify_password(password, hashed) is True
