"""
Pydantic schema for recommendation endpoint responses.
"""

from typing import Literal, Optional

from pydantic import BaseModel

from src.schemas.catalog import CardResponse
from src.schemas.recipe import RecipeListResponse


class RecommendedItem(BaseModel):
    """One item in the recommendations list."""

    kind: Literal["card", "recipe"]
    card: Optional[CardResponse] = None
    recipe: Optional[RecipeListResponse] = None
    score: float
    reason: Literal["taste", "popular", "explore"]
