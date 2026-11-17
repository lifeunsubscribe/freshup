"""
Pydantic schemas for the recommendations endpoint.

RecommendedItem is the shape returned by GET /recommendations.  Each item
is either a catalog card or an imported recipe that has no linked card, with
a score and a reason explaining why it was included.
"""

from typing import Literal, Optional
from pydantic import BaseModel

from src.schemas.catalog import CardResponse
from src.schemas.recipe import RecipeListResponse


class RecommendedItem(BaseModel):
    kind: Literal["card", "recipe"]
    card: Optional[CardResponse] = None
    recipe: Optional[RecipeListResponse] = None
    score: float
    reason: Literal["taste", "popular", "explore"]
