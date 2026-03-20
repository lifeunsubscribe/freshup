# Pydantic schemas for request/response validation
# Organized by domain to match routers structure

from src.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
)
from src.schemas.recipe import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeListResponse,
    RecipeIngredientCreate,
    RecipeIngredientResponse,
)

__all__ = [
    "InventoryItemCreate",
    "InventoryItemUpdate",
    "InventoryItemResponse",
    "InventoryItemListResponse",
    "RecipeCreate",
    "RecipeUpdate",
    "RecipeResponse",
    "RecipeListResponse",
    "RecipeIngredientCreate",
    "RecipeIngredientResponse",
]
