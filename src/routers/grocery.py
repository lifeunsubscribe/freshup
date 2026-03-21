"""
Grocery list CRUD endpoints for FreshUp.

Provides endpoints for users to manage their household grocery list,
including adding items, checking off purchases, and optionally creating
inventory items from purchased groceries.

Key design: Shared/global reads (any authenticated user can read any item),
owner-restricted writes (only added_by user can update/delete).

Per ADR, any authenticated user can purchase/unpurchase any item —
this is a household coordination action, not owner-restricted.

Logging Policy:
    User-provided item names are NOT logged as they may contain sensitive
    health information (e.g., prescription names, dietary restrictions).
    Logs include operational metadata (user_id, item_id, timestamps) for
    debugging while protecting user privacy per OWASP recommendations.
"""

import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models.user import User
from src.schemas.grocery import (
    GroceryItemCreate,
    GroceryItemUpdate,
    GroceryItemResponse,
    BulkPurchaseRequest,
    BulkPurchaseResponse,
    StoreGroupedGroceryResponse,
)
from src.middleware.auth import get_current_user
from src.services import grocery_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grocery", tags=["grocery"])


@router.post("", response_model=GroceryItemResponse, status_code=status.HTTP_201_CREATED)
def create_grocery_item(
    item_data: GroceryItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new grocery list item for the household.

    The added_by field is automatically set to the current user's ID,
    ignoring any value provided in the request body.

    Args:
        item_data: Grocery item data (item_name, quantity, unit, source, etc.)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Created grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If data integrity violation occurs
        HTTPException(422): If validation fails (invalid unit, source, etc.)
    """
    return grocery_service.create_item(
        item_name=item_data.item_name,
        quantity=item_data.quantity,
        unit=item_data.unit,
        source=item_data.source,
        current_user=current_user,
        db=db,
        target_store=item_data.target_store,
    )


@router.get("", response_model=list[GroceryItemResponse])
def list_grocery_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    purchased: Optional[bool] = Query(default=None, description="Filter by purchased status (default: false - unpurchased only)"),
    search: Optional[str] = Query(default=None, min_length=2, max_length=255, description="Search items by name (case-insensitive partial match)"),
):
    """
    List grocery items with filtering and pagination.

    Returns ALL grocery items (shared/global reads), ordered by most recently
    added first. Supports pagination via limit and offset query parameters.
    Supports filtering by purchased status and name search.

    Default behavior: Returns only unpurchased items (purchased=false).
    Use purchased=true to see all items including purchased ones.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session
        limit: Maximum number of items to return (1-100, default 50)
        offset: Number of items to skip (default 0)
        purchased: Filter by purchased status (None = unpurchased only, True = all purchased, False = unpurchased)
        search: Search items by name (case-insensitive partial match)

    Returns:
        list[GroceryItemResponse]: List of grocery items matching filters

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    return grocery_service.list_items(
        db=db,
        limit=limit,
        offset=offset,
        purchased=purchased,
        search=search,
    )


@router.get("/by-store", response_model=StoreGroupedGroceryResponse)
def get_grocery_items_by_store(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_purchased: bool = Query(default=False, description="Include purchased items (default: false - unpurchased only)"),
):
    """
    Get grocery items grouped by target store for per-store shopping lists.

    Returns ALL grocery items (shared/global reads) organized by their target
    store. Items without a target_store appear in the "unassigned" array.
    Empty stores (stores with no grocery items) are not included.

    Default behavior: Returns only unpurchased items (include_purchased=false).
    Use include_purchased=true to see all items including purchased ones.

    Args:
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session
        include_purchased: Include purchased items (default: false)

    Returns:
        StoreGroupedGroceryResponse: Items grouped by store with unassigned items

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    return grocery_service.get_items_by_store(
        db=db,
        include_purchased=include_purchased,
    )


@router.get("/{item_id}", response_model=GroceryItemResponse)
def get_grocery_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single grocery item by ID.

    Retrieves a specific grocery item. Any authenticated user can read any item
    (shared/global reads). Returns 404 if the item doesn't exist.

    Args:
        item_id: UUID of the grocery item to retrieve
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Requested grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist
    """
    return grocery_service.get_item_by_id(item_id=item_id, db=db)


@router.put("/{item_id}", response_model=GroceryItemResponse)
def update_grocery_item(
    item_id: UUID,
    update_data: GroceryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a grocery item with partial data.

    Allows partial updates - only provided fields will be updated. Returns 404
    if the item doesn't exist or is not owned by the current user (owner-restricted writes).

    Args:
        item_id: UUID of the grocery item to update
        update_data: Fields to update (all optional)
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Updated grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not owned by current user
        HTTPException(422): If validation fails (invalid unit, etc.)
    """
    update_dict = update_data.model_dump(exclude_unset=True)
    return grocery_service.update_item(
        item_id=item_id,
        current_user=current_user,
        db=db,
        **update_dict,
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grocery_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a grocery item.

    Removes the specified grocery item. Returns 404 if the item doesn't exist
    or is not owned by the current user (owner-restricted writes).

    Args:
        item_id: UUID of the grocery item to delete
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist or is not owned by current user
    """
    grocery_service.delete_item(item_id=item_id, current_user=current_user, db=db)
    return None


@router.put("/{item_id}/purchase", response_model=GroceryItemResponse)
def purchase_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a grocery item as purchased.

    Sets purchased=True, purchased_by=current_user, purchased_date=now.
    Any authenticated user can purchase any item (household coordination).

    Args:
        item_id: UUID of the grocery item to mark as purchased
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Updated grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist
        HTTPException(500): If database error occurs
    """
    return grocery_service.mark_purchased(item_id, current_user, db)


@router.put("/{item_id}/unpurchase", response_model=GroceryItemResponse)
def unpurchase_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reverse a grocery item purchase (mark as unpurchased).

    Sets purchased=False, purchased_by=None, purchased_date=None.
    Any authenticated user can unpurchase any item (household coordination).

    Args:
        item_id: UUID of the grocery item to mark as unpurchased
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        GroceryItemResponse: Updated grocery item

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If item doesn't exist
        HTTPException(500): If database error occurs
    """
    return grocery_service.mark_unpurchased(item_id, current_user, db)


@router.post("/bulk-purchase", response_model=BulkPurchaseResponse)
def bulk_purchase_items(
    request_data: BulkPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark multiple grocery items as purchased in a single atomic transaction.

    Optionally creates inventory items from purchased groceries when
    create_inventory_item=True. If any item_id is not found, the entire
    transaction is rolled back (all-or-nothing semantics).

    When create_inventory_item=True, storage_location and category are REQUIRED
    (enforced by schema validation - returns 422 if missing).

    Inventory items created with:
    - name = grocery item_name
    - quantity = grocery quantity
    - unit = grocery unit
    - storage_location = request storage_location
    - category = request category
    - added_by = current_user

    Args:
        request_data: Bulk purchase request with item IDs and optional inventory creation params
        current_user: Authenticated user (injected by get_current_user dependency)
        db: Database session

    Returns:
        BulkPurchaseResponse: List of updated grocery items and count of inventory items created

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(404): If any item_id is not found (entire batch fails)
        HTTPException(422): If create_inventory_item=True but storage_location or category missing
        HTTPException(500): If database error occurs
    """
    updated_items, inventory_count = grocery_service.bulk_purchase(
        item_ids=request_data.item_ids,
        current_user=current_user,
        db=db,
        create_inventory_item=request_data.create_inventory_item,
        storage_location=request_data.storage_location,
        category=request_data.category,
    )

    return BulkPurchaseResponse(
        items=updated_items,
        inventory_items_created=inventory_count
    )
