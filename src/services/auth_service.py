"""
Authentication service for FreshUp.

Provides JWT token creation and validation for stateless authentication
across household devices (phones, iPad terminal).
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from src.config import get_settings


# Password hashing context (from Phase 1C - password hashing utilities)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token with expiration.

    Generates a signed JWT token for stateless authentication. The token includes:
    - User-provided claims (typically {"sub": user_id})
    - Expiration time (exp) - defaults to 30 days for household convenience
    - Issued-at time (iat) - for token age tracking

    Args:
        data: Dictionary of claims to encode (e.g., {"sub": "user-123"})
        expires_delta: Optional custom expiration time. If None, uses default from config

    Returns:
        Encoded JWT token string

    Example:
        >>> token = create_access_token({"sub": "user-123"})
        >>> # Returns: "eyJhbGc..."
    """
    settings = get_settings()
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    # Add standard JWT claims
    to_encode.update({
        "exp": expire,  # Expiration time
        "iat": datetime.now(timezone.utc)  # Issued at time
    })

    # Encode and sign the token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Validates the token signature and expiration, then returns the payload.
    Automatically raises JWTError for invalid or expired tokens.

    Args:
        token: JWT token string to decode

    Returns:
        Dictionary containing the token payload (claims)

    Raises:
        JWTError: If token is invalid, expired, or signature verification fails

    Example:
        >>> payload = decode_token("eyJhbGc...")
        >>> user_id = payload["sub"]  # Extract user ID from token
    """
    settings = get_settings()

    # Decode and validate token (raises JWTError if invalid/expired)
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm]
    )

    return payload
