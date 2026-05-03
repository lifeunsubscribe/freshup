"""
Pydantic schemas for feed endpoints.

Defines response models for personalized recipe feed.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class RecipeCardSchema(BaseModel):
    """Recipe data returned in feed sections."""

    id: UUID = Field(..., description="Recipe ID")
    name: str = Field(..., description="Recipe name")
    source_type: str = Field(..., description="Source type")
    source_image: Optional[str] = Field(None, description="Recipe image URL")
    prep_time_minutes: Optional[int] = Field(None, description="Prep time in minutes")
    cook_time_minutes: Optional[int] = Field(None, description="Cook time in minutes")
    base_servings: int = Field(..., description="Number of servings")
    tags: list[str] = Field(default_factory=list, description="Recipe tags")
    times_cooked: int = Field(..., description="Number of times cooked")

    model_config = {"from_attributes": True}


class FeedSectionSchema(BaseModel):
    """Generic feed section with title and recipes."""

    title: str = Field(..., description="Section title")
    recipes: list[RecipeCardSchema] = Field(..., description="Recipe cards in this section")


class FeedRowSchema(BaseModel):
    """Feed row with title, recipes, and optional browse URL for expansion."""

    title: str = Field(..., description="Row title (ends with period per design system)")
    recipes: list[RecipeCardSchema] = Field(..., description="Recipe cards in this row")
    browse_url: Optional[str] = Field(None, description="URL for 'See all' expansion")


class HomeFeedResponseSchema(BaseModel):
    """Response schema for GET /feed/home endpoint."""

    make_now: FeedSectionSchema = Field(..., description="Make This Right Now section")
    on_repeat: FeedSectionSchema = Field(..., description="On Repeat section")
    personalized_rows: list[FeedRowSchema] = Field(
        default_factory=list,
        description="Personalized rows based on user patterns (3-4 max)"
    )
    source_rows: list[FeedRowSchema] = Field(
        default_factory=list,
        description="Source-specific rows (2 max, requires >=5 saves)"
    )
    fallback_rows: list[FeedRowSchema] = Field(
        default_factory=list,
        description="Fallback rows for cold start or variety"
    )


class BrowseFeedResponseSchema(BaseModel):
    """Response schema for GET /feed/browse endpoint."""

    sections: list[FeedRowSchema] = Field(..., description="All carousel sections for browse page")
