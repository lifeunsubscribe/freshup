"""
Pydantic schemas for recipe scraping.

Defines data models for scraped recipe data from external sources.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, HttpUrl


class ScrapedRecipeData(BaseModel):
    """
    Schema for scraped recipe data.

    This model represents normalized recipe data extracted from external sources
    using the recipe-scrapers library. All fields except source_url and source_type
    are optional since different sites may not provide all information.
    """

    # Required fields
    source_url: str = Field(..., description="Original URL of the scraped recipe")
    source_type: str = Field(..., description="Auto-detected source type (hellofresh_web, kitchen_sanctuary, url_import)")

    # Optional recipe metadata
    title: Optional[str] = Field(default=None, description="Recipe title/name")
    image_url: Optional[str] = Field(default=None, description="Main recipe image URL")

    # Timing and servings
    prep_time_minutes: Optional[int] = Field(default=None, description="Preparation time in minutes")
    cook_time_minutes: Optional[int] = Field(default=None, description="Cooking time in minutes")
    total_time_minutes: Optional[int] = Field(default=None, description="Total time in minutes")
    servings: Optional[int] = Field(default=None, description="Number of servings (yields)")

    # Recipe content (raw strings)
    ingredients: list[str] = Field(default_factory=list, description="List of ingredient strings (raw, unparsed)")
    instructions: list[str] = Field(default_factory=list, description="List of instruction/step strings")

    # Additional metadata
    tags: list[str] = Field(default_factory=list, description="Recipe tags/categories")
    nutrients: Optional[dict] = Field(default=None, description="Nutritional information (raw dictionary)")

    # Site attribution
    author: Optional[str] = Field(default=None, description="Recipe author name")
    site_name: Optional[str] = Field(default=None, description="Name of the source website")

    @field_validator('prep_time_minutes', 'cook_time_minutes', 'total_time_minutes', 'servings')
    @classmethod
    def validate_non_negative(cls, v: Optional[int]) -> Optional[int]:
        """Ensure time and serving fields are non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from title if provided."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None
