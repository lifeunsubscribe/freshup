"""
Pydantic schemas for authentication endpoints.

Defines request/response models for user registration and login.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from src.db.models.user import UserRole


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


class TokenResponse(BaseModel):
    """Response schema for JWT token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
