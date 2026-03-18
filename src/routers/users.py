"""
User management endpoints for FreshUp.

Provides endpoints for listing household members. Used by the iPad "who are you?"
selector and meal plan opt-in flows.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.schemas.auth import UserListResponse
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListResponse])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all household members.

    Returns a list of all users in the household with their basic profile information.
    Used by the iPad "who are you?" selector and meal plan opt-in flows.
    Any authenticated user can view the household roster.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        list[UserListResponse]: List of all users with id, name, role, dietary_profile,
                                allergies, disliked_ingredients, favorite_ingredients
                                (excludes email and hashed_password for privacy)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    users = db.query(User).all()
    return users
