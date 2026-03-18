"""
Pydantic schemas for authentication endpoints.

Defines request/response models for user registration and login.
"""

from uuid import UUID
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from src.db.models.user import UserRole, DietaryProfile


class UserCreate(BaseModel):
    """Request schema for user registration."""

    name: str = Field(..., min_length=1, max_length=255, description="User's display name")
    email: EmailStr = Field(..., description="User's email address (must be unique)")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    dietary_profile: Optional[list[str]] = Field(default=None, description="Dietary preferences")
    allergies: Optional[list[str]] = Field(default=None, description="Food allergies")
    role: Optional[str] = Field(default=None, description="User role (coordinator or member)")

    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        """Ensure password meets minimum length requirement."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure name is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Ensure role is a valid UserRole enum value."""
        if v is not None:
            valid_roles = [role.value for role in UserRole]
            if v not in valid_roles:
                raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for case-insensitive comparison."""
        return v.lower()


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for case-insensitive comparison."""
        return v.lower()


class UserResponse(BaseModel):
    """Response schema for user data (excludes password)."""

    id: UUID
    name: str
    email: str
    role: str
    dietary_profile: list
    allergies: list
    disliked_ingredients: list
    favorite_ingredients: list

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Request schema for updating user profile via PUT /auth/me."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="User's display name")
    dietary_profile: Optional[list[str]] = Field(default=None, description="Dietary preferences")
    allergies: Optional[list[str]] = Field(default=None, description="Food allergies")
    disliked_ingredients: Optional[list[str]] = Field(default=None, description="Disliked ingredients (stored as JSON array)")
    favorite_ingredients: Optional[list[str]] = Field(default=None, description="Favorite ingredients (stored as JSON array)")

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty or whitespace only if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Name cannot be empty')
        return v.strip() if v else None

    @field_validator('dietary_profile')
    @classmethod
    def validate_dietary_profile(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Ensure dietary_profile contains valid DietaryProfile enum values and strip whitespace."""
        if v is not None:
            # Strip whitespace from each item
            v = [item.strip() for item in v if item.strip()]
            valid_profiles = [profile.value for profile in DietaryProfile]
            for profile in v:
                if profile not in valid_profiles:
                    raise ValueError(f'Invalid dietary profile: {profile}. Must be one of: {", ".join(valid_profiles)}')
        return v

    @field_validator('allergies', 'disliked_ingredients', 'favorite_ingredients')
    @classmethod
    def strip_whitespace_from_list_items(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Strip whitespace from list items to ensure data consistency."""
        if v is not None:
            # Strip whitespace from each item and filter out empty strings
            v = [item.strip() for item in v if item.strip()]
        return v

    @model_validator(mode='before')
    @classmethod
    def reject_protected_fields(cls, data: Any) -> Any:
        """
        Explicitly reject attempts to modify protected fields.

        Protected fields (email, role) can only be modified through dedicated
        administrative endpoints, not through the user profile update endpoint.
        This provides defense-in-depth and clear error messages for API consumers.
        """
        if isinstance(data, dict):
            protected_fields = {'email', 'role'}
            submitted_protected = protected_fields.intersection(data.keys())
            if submitted_protected:
                raise ValueError(
                    f"Cannot modify protected fields: {', '.join(sorted(submitted_protected))}. "
                    f"These fields cannot be updated through this endpoint."
                )
        return data


class UserListResponse(BaseModel):
    """Response schema for user list (excludes email and password for privacy)."""

    id: UUID
    name: str
    role: str
    dietary_profile: list
    allergies: list
    disliked_ingredients: list
    favorite_ingredients: list

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response schema for JWT token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
