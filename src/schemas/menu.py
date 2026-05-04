"""
Pydantic schemas for Menu and MenuRecipe API requests/responses.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# Filter rule schemas
class FilterRule(BaseModel):
    """Individual filter rule for recipe matching."""
    field: str = Field(..., description="Field to filter on: tags, source_type, cook_time_minutes")
    operator: str = Field(..., description="Operator: contains, not_contains, eq, in, <=, >=")
    value: str | int | list[str] = Field(..., description="Value to match against")


class FilterRules(BaseModel):
    """Collection of filter rules with match logic."""
    match_logic: str = Field("all", description="Match logic: 'all' (AND) or 'any' (OR)")
    rules: list[FilterRule] = Field(default_factory=list)


# Menu schemas
class MenuCreate(BaseModel):
    """Schema for creating a new menu."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    filter_rules: Optional[FilterRules] = None
    is_auto_generated: bool = False
    cover_image: Optional[str] = Field(None, max_length=2048)
    sort_order: int = 0


class MenuUpdate(BaseModel):
    """Schema for updating an existing menu."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    filter_rules: Optional[FilterRules] = None
    sort_order: Optional[int] = None


class MenuResponse(BaseModel):
    """Schema for menu response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    filter_rules: Optional[dict]
    is_auto_generated: bool
    cover_image: Optional[str]
    sort_order: int
    created_at: datetime
    updated_at: datetime


class MenuListResponse(BaseModel):
    """Schema for list of menus."""
    menus: list[MenuResponse]
    total: int


# MenuRecipe schemas
class MenuRecipeCreate(BaseModel):
    """Schema for adding a recipe to a menu."""
    recipe_id: UUID
    sort_order: int = 0


class MenuRecipeResponse(BaseModel):
    """Schema for menu recipe response."""
    model_config = ConfigDict(from_attributes=True)

    menu_id: UUID
    recipe_id: UUID
    sort_order: int
    manually_added: bool
    manually_removed: bool
    added_at: datetime


# Pagination response for menu recipes
class MenuRecipesResponse(BaseModel):
    """Schema for paginated menu recipes response."""
    model_config = ConfigDict(from_attributes=True)

    recipes: list  # List of Recipe model objects - FastAPI will serialize them
    total: int

