"""
Authentication middleware for FreshUp.

Provides FastAPI dependencies for extracting and validating JWT tokens
from request headers.
"""

from src.middleware.auth import get_current_user, get_current_user_optional

__all__ = ["get_current_user", "get_current_user_optional"]
