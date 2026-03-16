"""
Authentication service for password hashing and verification.

This module provides secure password hashing using bcrypt.
All password storage should use these utilities to ensure consistent,
secure credential management across the application.
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Uses 12 rounds (OWASP recommended balance of security/performance).

    Args:
        password: The plaintext password to hash

    Returns:
        A bcrypt hash string suitable for database storage

    Raises:
        ValueError: If password is None, empty, or exceeds maximum length

    Example:
        >>> hashed = hash_password("my_secure_password")
        >>> print(hashed[:7])  # bcrypt hashes start with $2b$
        $2b$12$
    """
    # Validate input
    if password is None:
        raise ValueError("Password cannot be None")
    if not password or not password.strip():
        raise ValueError("Password cannot be empty")

    # Encode password to bytes and validate byte length
    # bcrypt truncates at 72 bytes, so we must check byte length, not character count
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError("Password exceeds maximum length of 72 bytes")

    # Generate hash with 12 rounds
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.

    This function uses timing-safe comparison to prevent timing attacks.
    Fails closed: returns False for any invalid input or malformed hashes.

    Args:
        password: The plaintext password to verify
        hashed: The bcrypt hash to verify against

    Returns:
        True if the password matches the hash, False otherwise

    Example:
        >>> hashed = hash_password("correct_password")
        >>> verify_password("correct_password", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    # Validate input - fail closed on any invalid input
    if password is None or hashed is None:
        return False
    if not password or not password.strip():
        return False
    if not hashed or not hashed.strip():
        return False

    try:
        # Encode both password and hash to bytes for bcrypt
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, AttributeError, TypeError):
        # Malformed hash or encoding error - fail closed
        return False
