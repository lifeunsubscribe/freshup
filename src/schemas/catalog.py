"""
Pydantic schemas for HelloFresh catalog data.

Represents the data surface of a parsed collection page: recipe cards
(summary-level only) and sub-collection pointers. Neither type carries
full recipe details; a card is promoted to a full Recipe only when the
user opens it (import-on-demand).
"""

from typing import Optional
from pydantic import BaseModel, Field


class CollectionChild(BaseModel):
    """A sub-collection linked from a parent collection page."""

    name: str = Field(..., description="Display name of the sub-collection")
    slug: str = Field(..., description="URL slug used to fetch the sub-collection")


class CollectionCard(BaseModel):
    """
    Summary card for one recipe as it appears on a HelloFresh collection page.

    Fields come from __NEXT_DATA__ → ssrPayload.collection.recipes[].
    prep_time_minutes is derived from the ISO 8601 prepTime field; None when
    prepTime is absent or not parseable.
    """

    external_id: str = Field(
        ...,
        min_length=1,
        description="HelloFresh recipe id with any locale suffix stripped (e.g. -en-US)",
    )
    name: str = Field(..., description="Recipe name")
    headline: Optional[str] = Field(default=None, description="Short tagline")
    image_url: str = Field(..., description="Absolute CDN image URL")
    prep_time_minutes: Optional[int] = Field(
        default=None,
        description="Preparation time in minutes; None when absent or unparseable",
    )
    rating: Optional[float] = Field(default=None, description="Aggregate star rating")
    rating_count: Optional[int] = Field(
        default=None, description="Number of ratings behind the aggregate"
    )
    recipe_url: str = Field(..., description="Absolute recipe page URL")


class CollectionPage(BaseModel):
    """Parsed result of a HelloFresh collection page."""

    name: str = Field(..., description="Collection display name")
    slug: str = Field(..., description="Collection URL slug")
    url: str = Field(..., description="Absolute URL this page was fetched from")
    cards: list[CollectionCard] = Field(
        default_factory=list, description="Recipe cards on this page"
    )
    children: list[CollectionChild] = Field(
        default_factory=list, description="Sub-collections linked from this page"
    )
