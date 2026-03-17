"""
Authentication service for FreshUp.

Provides JWT token creation and validation for stateless authentication
across household devices (phones, iPad terminal).
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from src.config import get_settings


# Custom exceptions for better error handling
class TokenError(Exception):
    """Base exception for token-related errors."""
    pass


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""
    pass


class TokenInvalidError(TokenError):
    """Raised when a token is invalid or malformed."""
    pass


# Password hashing context (from Phase 1C - password hashing utilities)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Raises:
        ValueError: If password is None, empty, or exceeds bcrypt's 72-byte limit
    """
    if password is None:
        raise ValueError("Password cannot be None")
    if not password or not password.strip():
        raise ValueError("Password cannot be empty")
    if len(password.encode('utf-8')) > 72:
        raise ValueError("Password exceeds maximum length (72 bytes)")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Fails closed: returns False for any invalid input or malformed hashes.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    if plain_password is None or hashed_password is None:
        return False
    if not plain_password or not plain_password.strip():
        return False
    if not hashed_password or not hashed_password.strip():
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


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

    # Get current time for consistent timestamp across exp and iat
    now = datetime.now(timezone.utc)

    # Set expiration time
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    # Add standard JWT claims
    to_encode.update({
        "exp": expire,  # Expiration time
        "iat": now  # Issued at time
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
    Uses custom exceptions to distinguish between different failure modes.

    Args:
        token: JWT token string to decode

    Returns:
        Dictionary containing the token payload (claims)

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid, malformed, or signature verification fails

    Example:
        >>> payload = decode_token("eyJhbGc...")
        >>> user_id = payload["sub"]  # Extract user ID from token
    """
    settings = get_settings()

    try:
        # Decode and validate token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except JWTError as e:
        raise TokenInvalidError("Token is invalid or malformed") from e
