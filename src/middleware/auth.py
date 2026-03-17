"""
Authentication middleware for FreshUp.

FastAPI dependencies for extracting and validating JWT tokens from request headers.
Used by protected endpoints to identify the current user.
"""

from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.services.auth_service import decode_token, TokenError


# Bearer token scheme for extracting Authorization header
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates JWT from Authorization header.

    This dependency is used by protected endpoints to authenticate requests and
    retrieve the current user. It fails closed: any authentication error returns 401.

    Args:
        credentials: Bearer token from Authorization header (injected by HTTPBearer)
        db: Database session (injected by get_db)

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException(401): If Authorization header is missing, token is invalid/expired,
                           or user is not found in database

    Example:
        @app.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": str(current_user.id)}
    """
    # Check if Authorization header is present
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Decode and validate the JWT token
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")

        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Convert string user ID to UUID
        try:
            user_id = UUID(user_id_str)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except TokenError:
        # TokenExpiredError or TokenInvalidError from decode_token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query database for user
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        # User ID in token is valid but user doesn't exist in database
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    FastAPI dependency that extracts and validates JWT, but returns None on failure.

    This dependency is used by endpoints that enhance behavior when authenticated
    but don't require authentication. For example, a public feed that shows
    personalized content if the user is logged in.

    Args:
        credentials: Bearer token from Authorization header (injected by HTTPBearer)
        db: Database session (injected by get_db)

    Returns:
        User object if authenticated, None otherwise

    Example:
        @app.get("/feed")
        def feed(current_user: Optional[User] = Depends(get_current_user_optional)):
            if current_user:
                return {"message": f"Hello, {current_user.name}"}
            return {"message": "Hello, guest"}
    """
    # If no credentials provided, return None (not authenticated)
    if credentials is None:
        return None

    token = credentials.credentials

    try:
        # Decode and validate the JWT token
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")

        if user_id_str is None:
            return None

        # Convert string user ID to UUID
        try:
            user_id = UUID(user_id_str)
        except (ValueError, AttributeError):
            return None

    except TokenError:
        # TokenExpiredError or TokenInvalidError from decode_token
        return None

    # Query database for user
    user = db.query(User).filter(User.id == user_id).first()

    # Return user if found, None otherwise
    return user
