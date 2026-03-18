"""
Pydantic schemas for authentication endpoints.

Defines request/response models for user registration and login.
"""

from uuid import UUID
from typing import Optional, Any
import re
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict
from src.db.models.user import UserRole, DietaryProfile


# Validation constants for ingredient/allergy lists
MAX_LIST_ITEM_LENGTH = 100
MAX_LIST_SIZE = 100
# Allow ASCII letters, numbers, spaces, and common punctuation used in food names
ALLOWED_CHARS_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-\'\(\),./]+$')


def validate_string_list(
    field_name: str,
    values: Optional[list[str]],
    max_item_length: int = MAX_LIST_ITEM_LENGTH,
    max_list_size: int = MAX_LIST_SIZE,
) -> Optional[list[str]]:
    """
    Validate a list of strings for ingredient/allergy fields.

    Ensures items meet length constraints and contain only allowed characters.
    Strips whitespace and filters out empty strings.

    Args:
        field_name: Name of the field being validated (for error messages)
        values: List of strings to validate
        max_item_length: Maximum allowed length per item
        max_list_size: Maximum number of items in the list

    Returns:
        Validated and cleaned list of strings, or None if input was None

    Raises:
        ValueError: If validation fails
    """
    if values is None:
        return None

    # Strip whitespace and filter empty strings
    cleaned = [item.strip() for item in values if item.strip()]

    # Check list size
    if len(cleaned) > max_list_size:
        raise ValueError(f'{field_name} cannot contain more than {max_list_size} items')

    # Validate each item
    for item in cleaned:
        # Check item length
        if len(item) > max_item_length:
            raise ValueError(
                f'{field_name} items cannot exceed {max_item_length} characters. '
                f'Item "{item[:20]}..." is {len(item)} characters long'
            )

        # Check allowed characters
        if not ALLOWED_CHARS_PATTERN.match(item):
            raise ValueError(
                f'{field_name} items can only contain letters, numbers, spaces, '
                f'and common punctuation (- \' ( ) , . /). Invalid item: "{item}"'
            )

    return cleaned


class UserCreate(BaseModel):
    """Request schema for user registration."""

    name: str = Field(..., min_length=1, max_length=255, description="User's display name")
    email: EmailStr = Field(..., description="User's email address (must be unique)")
    password: str = Field(..., description="Password (minimum 8 characters, maximum 128 characters)")
    dietary_profile: Optional[list[str]] = Field(default=None, description="Dietary preferences")
    allergies: Optional[list[str]] = Field(default=None, description="Food allergies")
    disliked_ingredients: Optional[list[str]] = Field(default=None, description="Disliked ingredients (stored as JSON array)")
    favorite_ingredients: Optional[list[str]] = Field(default=None, description="Favorite ingredients (stored as JSON array)")
    role: Optional[str] = Field(default=None, description="User role (coordinator or member)")

    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """
        Ensure password meets complexity requirements.

        Password must:
        - Be at least 8 characters long
        - Be at most 128 characters long
        - Contain at least one uppercase letter (A-Z)
        - Contain at least one lowercase letter (a-z)
        - Contain at least one digit (0-9)
        - Contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
        """
        errors = []

        # Check minimum length
        if len(v) < 8:
            errors.append('at least 8 characters')

        # Check maximum length
        if len(v) > 128:
            errors.append('at most 128 characters')

        # Check for uppercase letter
        if not any(c.isupper() for c in v):
            errors.append('at least one uppercase letter')

        # Check for lowercase letter
        if not any(c.islower() for c in v):
            errors.append('at least one lowercase letter')

        # Check for digit
        if not any(c.isdigit() for c in v):
            errors.append('at least one digit')

        # Check for special character
        special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?')
        if not any(c in special_chars for c in v):
            errors.append('at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)')

        if errors:
            raise ValueError(f"Password must contain {', '.join(errors)}")

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
    def validate_ingredient_lists(cls, v: Optional[list[str]], info) -> Optional[list[str]]:
        """
        Validate ingredient/allergy lists for length and character constraints.

        Ensures data quality by enforcing maximum item length, maximum list size,
        and allowed character constraints.
        """
        field_name = info.field_name
        return validate_string_list(field_name, v)



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
    dietary_profile: list[str]
    allergies: list[str]
    disliked_ingredients: list[str]
    favorite_ingredients: list[str]

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Request schema for updating user profile via PUT /auth/me."""

    # Silently ignore unknown fields for forward compatibility and robustness
    model_config = ConfigDict(extra="ignore")

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
    def validate_ingredient_lists(cls, v: Optional[list[str]], info) -> Optional[list[str]]:
        """
        Validate ingredient/allergy lists for length and character constraints.

        Ensures data quality by enforcing maximum item length, maximum list size,
        and allowed character constraints.
        """
        field_name = info.field_name
        return validate_string_list(field_name, v)

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
    dietary_profile: list[str]
    allergies: list[str]
    disliked_ingredients: list[str]
    favorite_ingredients: list[str]

    class Config:
        from_attributes = True


class SwitchUserRequest(BaseModel):
    """Request schema for switching user sessions on shared devices."""

    user_id: UUID = Field(..., description="Target user ID to switch to")


class TokenResponse(BaseModel):
    """Response schema for JWT token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
