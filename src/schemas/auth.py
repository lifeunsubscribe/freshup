"""
Pydantic schemas for authentication endpoints.

Defines request/response models for user registration and login.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, Any
import re
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict
from src.db.models.user import UserRole, DietaryProfile
from src.schemas.validators import (
    validate_string_list,
    validate_name_not_empty,
    validate_enum_value,
    normalize_email,
    validate_dietary_profile
)
from src.services.ingredient_keys import INGREDIENTS
from src.services.recipe_themes import VALUE_LABELS

TASTE_LEVELS = frozenset({"love", "like", "less", "never"})
# Valid taste_preferences key prefixes with their allowed value sets
_VALID_INGREDIENT_KEYS = frozenset(INGREDIENTS.keys())
_VALID_CUISINE_KEYS = frozenset(VALUE_LABELS["cuisine"].keys())


class UserCreate(BaseModel):
    """Request schema for user registration."""

    name: str = Field(..., min_length=1, max_length=255, description="User's display name")
    email: EmailStr = Field(..., description="User's email address (must be unique)")
    password: str = Field(..., description="Password (minimum 8 characters, maximum 72 bytes for bcrypt compatibility)")
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
        - Be at most 72 bytes (bcrypt's maximum) when encoded as UTF-8
        - Contain at least one uppercase letter (A-Z)
        - Contain at least one lowercase letter (a-z)
        - Contain at least one digit (0-9)
        - Contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
        """
        errors = []

        # Check minimum length (in characters for user-friendliness)
        if len(v) < 8:
            errors.append('at least 8 characters')

        # Check maximum length (in bytes for bcrypt compatibility)
        # bcrypt has a 72-byte limit for passwords
        password_bytes = len(v.encode('utf-8'))
        if password_bytes > 72:
            errors.append('at most 72 bytes (currently {} bytes)'.format(password_bytes))

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
    def validate_name(cls, v: str) -> str:
        """Ensure name is not empty or whitespace only."""
        result = validate_name_not_empty(v)
        # validate_name_not_empty handles None, but name is required so this won't be None
        return result  # type: ignore

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Ensure role is a valid UserRole enum value."""
        return validate_enum_value('Role', v, UserRole, allow_none=True)

    @field_validator('email')
    @classmethod
    def normalize_email_field(cls, v: str) -> str:
        """Normalize email to lowercase for case-insensitive comparison."""
        return normalize_email(v)

    @field_validator('dietary_profile')
    @classmethod
    def validate_dietary_profile_field(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Ensure dietary_profile contains valid DietaryProfile enum values and strip whitespace."""
        valid_profiles = [profile.value for profile in DietaryProfile]
        return validate_dietary_profile(v, valid_profiles)

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
    def normalize_email_field(cls, v: str) -> str:
        """Normalize email to lowercase for case-insensitive comparison."""
        return normalize_email(v)


class UserResponse(BaseModel):
    """Response schema for user data (excludes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
    dietary_profile: list[str]
    allergies: list[str]
    disliked_ingredients: list[str]
    favorite_ingredients: list[str]
    taste_preferences: dict[str, str]
    onboarded_at: Optional[datetime]


class UserUpdate(BaseModel):
    """Request schema for updating user profile via PUT /auth/me."""

    # Silently ignore unknown fields for forward compatibility and robustness
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="User's display name")
    dietary_profile: Optional[list[str]] = Field(default=None, description="Dietary preferences")
    allergies: Optional[list[str]] = Field(default=None, description="Food allergies")
    disliked_ingredients: Optional[list[str]] = Field(default=None, description="Disliked ingredients (stored as JSON array)")
    favorite_ingredients: Optional[list[str]] = Field(default=None, description="Favorite ingredients (stored as JSON array)")
    taste_preferences: Optional[dict[str, str]] = Field(default=None, description="Graded taste map; keys: ingredient:<key> or cuisine:<value>; values: love|like|less|never")
    onboarded: Optional[bool] = Field(default=None, description="Set to true to mark onboarding complete (sets onboarded_at once)")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty or whitespace only if provided."""
        return validate_name_not_empty(v)

    @field_validator('dietary_profile')
    @classmethod
    def validate_dietary_profile_field(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Ensure dietary_profile contains valid DietaryProfile enum values and strip whitespace."""
        valid_profiles = [profile.value for profile in DietaryProfile]
        return validate_dietary_profile(v, valid_profiles)

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

    @field_validator('taste_preferences')
    @classmethod
    def validate_taste_preferences(cls, v: Optional[dict[str, str]]) -> Optional[dict[str, str]]:
        """Keys must be ingredient:<known key> or cuisine:<known value>; values one of love|like|less|never."""
        if v is None:
            return v
        for pref_key, level in v.items():
            if level not in TASTE_LEVELS:
                raise ValueError(
                    f"Invalid taste level '{level}' for key '{pref_key}'. "
                    f"Must be one of: {', '.join(sorted(TASTE_LEVELS))}"
                )
            if pref_key.startswith("ingredient:"):
                ingredient_key = pref_key[len("ingredient:"):]
                if ingredient_key not in _VALID_INGREDIENT_KEYS:
                    raise ValueError(
                        f"Unknown ingredient key '{ingredient_key}' in '{pref_key}'. "
                        f"Key must be a known ingredient from the ingredient vocabulary."
                    )
            elif pref_key.startswith("cuisine:"):
                cuisine_key = pref_key[len("cuisine:"):]
                if cuisine_key not in _VALID_CUISINE_KEYS:
                    raise ValueError(
                        f"Unknown cuisine key '{cuisine_key}' in '{pref_key}'. "
                        f"Key must be a known cuisine value."
                    )
            else:
                raise ValueError(
                    f"Invalid taste_preferences key '{pref_key}'. "
                    f"Keys must start with 'ingredient:' or 'cuisine:'."
                )
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

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    role: str
    dietary_profile: list[str]
    allergies: list[str]
    disliked_ingredients: list[str]
    favorite_ingredients: list[str]


class SwitchUserRequest(BaseModel):
    """Request schema for switching user sessions on shared devices."""

    user_id: UUID = Field(..., description="Target user ID to switch to")


class PasswordChangeRequest(BaseModel):
    """Request schema for password change."""

    old_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., description="New password (minimum 8 characters, maximum 72 bytes for bcrypt compatibility)")

    @field_validator('new_password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """
        Ensure new password meets complexity requirements.

        Password must:
        - Be at least 8 characters long
        - Be at most 72 bytes (bcrypt's maximum) when encoded as UTF-8
        - Contain at least one uppercase letter (A-Z)
        - Contain at least one lowercase letter (a-z)
        - Contain at least one digit (0-9)
        - Contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
        """
        errors = []

        # Check minimum length (in characters for user-friendliness)
        if len(v) < 8:
            errors.append('at least 8 characters')

        # Check maximum length (in bytes for bcrypt compatibility)
        # bcrypt has a 72-byte limit for passwords
        password_bytes = len(v.encode('utf-8'))
        if password_bytes > 72:
            errors.append('at most 72 bytes (currently {} bytes)'.format(password_bytes))

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

    @model_validator(mode='after')
    def validate_passwords_different(self) -> 'PasswordChangeRequest':
        """
        Ensure new password is different from old password.

        Prevents meaningless password "changes" where the user sets
        the same password they already have.
        """
        if self.old_password == self.new_password:
            raise ValueError('New password must be different from current password')
        return self


class TokenResponse(BaseModel):
    """Response schema for JWT token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
