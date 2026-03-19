"""
Pydantic schemas for SubstitutionPreference endpoints.

Defines request/response models for creating, updating, and retrieving
user-defined ingredient substitution preferences.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.substitution import SubstitutionContext
from src.schemas.validators import validate_ingredient_name, validate_enum_value


class ReplacementItem(BaseModel):
    """Schema for a single replacement item in the ranked list."""

    ingredient: str = Field(..., min_length=1, max_length=100, description="Replacement ingredient name")
    rank: int = Field(..., ge=1, description="Rank/priority (1 = highest priority)")

    @field_validator('ingredient')
    @classmethod
    def validate_ingredient_field(cls, v: str) -> str:
        """
        Validate ingredient name with Unicode support.

        Ensures ingredient name is not empty, normalizes Unicode (NFC),
        and blocks dangerous control/format characters.
        """
        return validate_ingredient_name('Ingredient name', v)


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
        """
        Validate original ingredient name with Unicode support.

        Ensures ingredient name is not empty, normalizes Unicode (NFC),
        and blocks dangerous control/format characters.
        """
        return validate_ingredient_name('Original ingredient', v)

    @field_validator('context')
    @classmethod
    def validate_context_field(cls, v: Optional[str]) -> str:
        """Ensure context is a valid SubstitutionContext enum value."""
        if v is None:
            return SubstitutionContext.any.value

        result = validate_enum_value('Context', v, SubstitutionContext, allow_none=False)
        # validate_enum_value handles Optional, but we've already handled None case above
        return result  # type: ignore

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

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    original_ingredient: str
    replacements: list[dict]  # List of {"ingredient": str, "rank": int}
    context: Optional[str]
