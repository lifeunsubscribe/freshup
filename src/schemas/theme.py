"""Response schemas for GET /themes (see src/services/recipe_themes.py)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ThemeCollection(BaseModel):
    """A catalog collection that belongs to a theme value."""

    source_type: str
    slug: str
    name: str
    card_count: int
    last_fetched_at: Optional[datetime] = None
    contains: list[str] = Field(
        default_factory=list,
        description='"theme:value" keys its cards also appear under (via other collections)',
    )


class ThemeValue(BaseModel):
    """One value of a theme (e.g. Italian) and the whole lists behind it."""

    value: str
    label: str
    library_tag: Optional[str] = Field(None, description="Tag to query the user's recipes for this value")
    library_source_type: Optional[str] = Field(None, description="Source type to query the user's recipes for this value")
    library_count: int = 0
    match_tags: list[str] = Field(default_factory=list, description="Lowercase tags that count as this value")
    match_source_types: list[str] = Field(default_factory=list, description="Source types that count as this value")
    collections: list[ThemeCollection] = Field(default_factory=list)


class Theme(BaseModel):
    key: str
    label: str
    values: list[ThemeValue]
