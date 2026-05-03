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


class HomeFeedResponseSchema(BaseModel):
    """Response schema for GET /feed/home endpoint."""

    make_now: FeedSectionSchema = Field(..., description="Make This Right Now section")
    on_repeat: FeedSectionSchema = Field(..., description="On Repeat section")
