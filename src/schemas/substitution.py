"""
Pydantic schemas for SubstitutionPreference endpoints.

Defines request/response models for creating, updating, and retrieving
user-defined ingredient substitution preferences.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from src.db.models.substitution import SubstitutionContext


class ReplacementItem(BaseModel):
    """Schema for a single replacement item in the ranked list."""

    ingredient: str = Field(..., min_length=1, max_length=100, description="Replacement ingredient name")
    rank: int = Field(..., ge=1, description="Rank/priority (1 = highest priority)")

    @field_validator('ingredient')
    @classmethod
    def validate_ingredient_name(cls, v: str) -> str:
        """Ensure ingredient name is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Ingredient name cannot be empty')
        return v.strip()


class SubstitutionPreferenceCreate(BaseModel):
    """Request schema for creating a new substitution preference."""

    original_ingredient: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The ingredient to be replaced"
    )
    replacements: list[ReplacementItem] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Ranked list of replacement ingredients"
    )
    context: Optional[str] = Field(
        default=SubstitutionContext.any.value,
        description="Usage context for this substitution"
    )

    @field_validator('original_ingredient')
    @classmethod
    def validate_original_ingredient(cls, v: str) -> str:
        """Ensure original ingredient is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Original ingredient cannot be empty')
        return v.strip()

    @field_validator('context')
    @classmethod
    def validate_context(cls, v: Optional[str]) -> str:
        """Ensure context is a valid SubstitutionContext enum value."""
        if v is None:
            return SubstitutionContext.any.value

        valid_contexts = [ctx.value for ctx in SubstitutionContext]
        if v not in valid_contexts:
            raise ValueError(
                f'Context must be one of: {", ".join(valid_contexts)}. Got: {v}'
            )
        return v

    @field_validator('replacements')
    @classmethod
    def validate_replacements_unique_ranks(cls, v: list[ReplacementItem]) -> list[ReplacementItem]:
        """Ensure replacement ranks are unique within the list."""
        ranks = [item.rank for item in v]
        if len(ranks) != len(set(ranks)):
            raise ValueError('Replacement ranks must be unique')
        return v


class SubstitutionPreferenceUpdate(BaseModel):
    """Request schema for updating a substitution preference."""

    replacements: Optional[list[ReplacementItem]] = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="Updated ranked list of replacement ingredients"
    )
    context: Optional[str] = Field(
        default=None,
        description="Updated usage context"
    )

    @field_validator('context')
    @classmethod
    def validate_context(cls, v: Optional[str]) -> Optional[str]:
        """Ensure context is a valid SubstitutionContext enum value if provided."""
        if v is None:
            return None

        valid_contexts = [ctx.value for ctx in SubstitutionContext]
        if v not in valid_contexts:
            raise ValueError(
                f'Context must be one of: {", ".join(valid_contexts)}. Got: {v}'
            )
        return v

    @field_validator('replacements')
    @classmethod
    def validate_replacements_unique_ranks(cls, v: Optional[list[ReplacementItem]]) -> Optional[list[ReplacementItem]]:
        """Ensure replacement ranks are unique within the list if provided."""
        if v is None:
            return None

        ranks = [item.rank for item in v]
        if len(ranks) != len(set(ranks)):
            raise ValueError('Replacement ranks must be unique')
        return v


class SubstitutionPreferenceResponse(BaseModel):
    """Response schema for substitution preference data."""

    id: UUID
    user_id: UUID
    original_ingredient: str
    replacements: list[dict]  # List of {"ingredient": str, "rank": int}
    context: Optional[str]

    class Config:
        from_attributes = True
