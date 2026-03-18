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
from src.db.models.user import User, UserRole
from src.services.auth_service import decode_token, TokenError


# Bearer token scheme for extracting Authorization header
security = HTTPBearer(auto_error=False)


def _decode_token_and_get_user(token: str, db: Session) -> Optional[User]:
    """
    Private helper to decode JWT token and retrieve user from database.

    This function contains the shared logic between get_current_user and
    get_current_user_optional. It fails gracefully by returning None on any error.

    Args:
        token: JWT token string to decode
        db: Database session for user lookup

    Returns:
        User object if token is valid and user exists, None otherwise
    """
    try:
        # Decode and validate the JWT token
        payload = decode_token(token)
        user_id_str: Optional[str] = payload.get("sub")

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

    # Query database for user and return (None if not found)
    return db.query(User).filter(User.id == user_id).first()


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

    # Use shared helper to decode token and retrieve user
    user = _decode_token_and_get_user(token, db)

    if user is None:
        # Token is invalid, expired, or user doesn't exist in database
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

    # Use shared helper to decode token and retrieve user (returns None on failure)
    return _decode_token_and_get_user(token, db)


def require_coordinator(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    FastAPI dependency that requires the authenticated user to have coordinator role.

    This dependency is used by coordinator-only endpoints to enforce role-based
    authorization. It chains with get_current_user, so authentication is verified
    first, then role authorization is checked. Returns 403 if authenticated user
    is not a coordinator.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)

    Returns:
        User object if user is a coordinator

    Raises:
        HTTPException(403): If authenticated user does not have coordinator role

    Example:
        @app.post("/meal-plans/approve")
        def approve_meal_plan(
            plan_id: UUID,
            coordinator: User = Depends(require_coordinator)
        ):
            # Only coordinators can access this endpoint
            return approve_plan(plan_id, coordinator)

        # Can also be combined with route dependencies:
        @app.post("/admin/settings", dependencies=[Depends(require_coordinator)])
        def update_settings(settings: Settings):
            # Coordinator check happens before handler is called
            return update(settings)
    """
    # Check if user has coordinator role
    if current_user.role != UserRole.coordinator.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Coordinator role required.",
        )

    return current_user
