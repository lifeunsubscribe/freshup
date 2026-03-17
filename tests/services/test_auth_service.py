"""
Unit tests for authentication service.

Tests cover:
- Password hashing: hash and verify, edge cases, input validation
- JWT: create_access_token, decode_token, expiration, invalid tokens
"""

import pytest
from datetime import timedelta
from src.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    TokenExpiredError,
    TokenInvalidError,
)


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

    def test_hash_password_rejects_unicode_exceeding_byte_limit(self):
        """Test that passwords with unicode that exceed 72 bytes are rejected.

        This tests the critical edge case where character count != byte count.
        For example, emoji and multibyte unicode characters can cause a password
        with <72 characters to exceed the 72-byte bcrypt limit.
        """
        # Use 4-byte emoji characters: each 🔒 is 4 bytes in UTF-8
        # 18 emoji × 4 bytes = 72 bytes (at the limit)
        at_limit_password = "🔒" * 18  # Exactly 72 bytes
        hashed = hash_password(at_limit_password)
        assert hashed.startswith("$2b$12$")
        assert verify_password(at_limit_password, hashed)

        # 19 emoji × 4 bytes = 76 bytes (exceeds limit)
        over_limit_password = "🔒" * 19  # 76 bytes, only 19 characters
        with pytest.raises(ValueError, match="Password exceeds maximum length"):
            hash_password(over_limit_password)


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


class TestCreateAccessToken:
    """Tests for the create_access_token function."""

    def test_create_access_token_returns_string(self):
        """Token should be a non-empty string."""
        token = create_access_token({"sub": "user-123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_is_valid_jwt(self):
        """Token should be decodable and contain the original claims."""
        payload = create_access_token({"sub": "user-abc"})
        decoded = decode_token(payload)
        assert decoded["sub"] == "user-abc"

    def test_create_access_token_includes_exp_and_iat(self):
        """Token payload must include exp and iat claims."""
        token = create_access_token({"sub": "user-123"})
        decoded = decode_token(token)
        assert "exp" in decoded
        assert "iat" in decoded

    def test_create_access_token_custom_expiry(self):
        """Custom expires_delta should be respected."""
        token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(minutes=5))
        decoded = decode_token(token)
        # exp - iat should be ~300 seconds (5 minutes)
        delta = decoded["exp"] - decoded["iat"]
        assert 290 <= delta <= 310

    def test_create_access_token_different_tokens_per_call(self):
        """Two tokens created from the same data should differ (iat differs)."""
        import time
        token1 = create_access_token({"sub": "user-123"})
        time.sleep(1)
        token2 = create_access_token({"sub": "user-123"})
        assert token1 != token2

    def test_create_access_token_does_not_mutate_input(self):
        """The data dict passed in should not be modified."""
        data = {"sub": "user-123"}
        original = dict(data)
        create_access_token(data)
        assert data == original


class TestDecodeToken:
    """Tests for the decode_token function."""

    def test_decode_token_returns_payload(self):
        """Should return the claims dict for a valid token."""
        token = create_access_token({"sub": "user-xyz"})
        payload = decode_token(token)
        assert payload["sub"] == "user-xyz"

    def test_decode_token_raises_token_expired_error(self):
        """Should raise TokenExpiredError for an expired token."""
        token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenExpiredError):
            decode_token(token)

    def test_decode_token_raises_token_invalid_for_garbage(self):
        """Should raise TokenInvalidError for a non-token string."""
        with pytest.raises(TokenInvalidError):
            decode_token("this.is.not.a.jwt")

    def test_decode_token_raises_token_invalid_for_wrong_signature(self):
        """Should raise TokenInvalidError if the signature doesn't verify."""
        token = create_access_token({"sub": "user-123"})
        # Tamper with the signature (last segment)
        parts = token.split(".")
        parts[-1] = parts[-1][:-4] + "XXXX"
        tampered = ".".join(parts)
        with pytest.raises(TokenInvalidError):
            decode_token(tampered)

    def test_decode_token_raises_token_invalid_for_empty_string(self):
        """Should raise TokenInvalidError for an empty string."""
        with pytest.raises(TokenInvalidError):
            decode_token("")
