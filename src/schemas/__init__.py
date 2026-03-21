# Pydantic schemas for request/response validation
# Organized by domain to match routers structure

from src.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
)
from src.schemas.grocery import (
    GroceryItemCreate,
    GroceryItemUpdate,
    GroceryItemResponse,
    StoreGroupedItems,
    StoreGroupedGroceryResponse,
    BulkPurchaseRequest,
    BulkPurchaseResponse,
)

__all__ = [
    "InventoryItemCreate",
    "InventoryItemUpdate",
    "InventoryItemResponse",
    "InventoryItemListResponse",
    "GroceryItemCreate",
    "GroceryItemUpdate",
    "GroceryItemResponse",
    "StoreGroupedItems",
    "StoreGroupedGroceryResponse",
    "BulkPurchaseRequest",
    "BulkPurchaseResponse",
]
