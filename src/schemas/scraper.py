"""
Pydantic schemas for recipe scraping.

Defines data models for scraped recipe data from external sources.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


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

    @field_validator('prep_time_minutes', 'cook_time_minutes', 'total_time_minutes')
    @classmethod
    def validate_non_negative_time(cls, v: Optional[int]) -> Optional[int]:
        """Ensure time fields are non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v

    @field_validator('servings')
    @classmethod
    def validate_positive_servings(cls, v: Optional[int]) -> Optional[int]:
        """
        Ensure servings is positive if provided (at least 1).

        Zero servings is semantically invalid and could cause division-by-zero
        errors in downstream calculations (e.g., scaling recipes per-serving).
        """
        if v is not None and v <= 0:
            raise ValueError("servings must be positive (at least 1)")
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from title if provided."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class ImportUrlRequest(BaseModel):
    """Request schema for single URL import."""
    url: str = Field(..., description="Recipe URL to import", min_length=1, max_length=2048)


class ImportBatchRequest(BaseModel):
    """Request schema for batch URL import."""
    urls: list[str] = Field(..., description="List of recipe URLs to import (each URL max 2048 chars)", min_length=1, max_length=500)

    @field_validator('urls')
    @classmethod
    def validate_url_lengths(cls, v: list[str]) -> list[str]:
        """Ensure each URL doesn't exceed maximum length."""
        for url in v:
            if len(url) > 2048:
                raise ValueError("Each URL must not exceed 2048 characters")
        return v


class DiscoverAndImportRequest(BaseModel):
    """Request schema for discover-and-import operation."""
    max_recipes: Optional[int] = Field(default=50, description="Maximum number of recipes to import", ge=1, le=1000)


class DiscoveryResponse(BaseModel):
    """Response schema for URL discovery."""
    source: str = Field(..., description="Source name (hellofresh or kitchen_sanctuary)")
    urls: list[str] = Field(..., description="Discovered recipe URLs")
    count: int = Field(..., description="Number of URLs discovered")


class SourceStats(BaseModel):
    """Statistics for a single source type."""
    source_type: str = Field(..., description="Source type identifier")
    count: int = Field(..., description="Number of recipes from this source")


class StatusResponse(BaseModel):
    """Response schema for scraper status endpoint."""
    stats: list[SourceStats] = Field(..., description="Recipe counts by source type")
