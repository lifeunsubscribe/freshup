"""
Service layer for receipt processing operations.

Provides business logic for receipt submission, confirmation, and inventory
item creation from parsed receipt data.
"""

import json
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.db.models.processing_task import ProcessingTask, TaskStatus, TaskType
from src.db.models.inventory_item import InventoryItem, Category, UnitType, StorageLocation
from src.schemas.receipt import ReceiptInventoryCandidate, ReceiptParseResult, ReceiptTaskStatusResponse, ReceiptLineItem
from src.schemas.inventory import InventoryItemCreate
from src.services.task_service import get_task_by_id
from src.services.inventory_service import create_inventory_items_bulk
from src.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


# Category mapping dictionary: maps LLM category guesses to Category enum values
# Supports common variations and aliases for fuzzy matching
CATEGORY_MAPPING = {
    # Produce variations
    "produce": Category.produce,
    "fruit": Category.produce,
    "fruits": Category.produce,
    "vegetable": Category.produce,
    "vegetables": Category.produce,
    "veggies": Category.produce,
    "fresh produce": Category.produce,

    # Protein variations
    "protein": Category.protein,
    "meat": Category.protein,
    "meats": Category.protein,
    "poultry": Category.protein,
    "seafood": Category.protein,
    "fish": Category.protein,
    "chicken": Category.protein,
    "beef": Category.protein,
    "pork": Category.protein,

    # Dairy variations
    "dairy": Category.dairy,
    "milk": Category.dairy,
    "cheese": Category.dairy,
    "yogurt": Category.dairy,
    "cream": Category.dairy,
    "butter": Category.dairy,

    # Grain variations
    "grain": Category.grain,
    "grains": Category.grain,
    "bread": Category.grain,
    "pasta": Category.grain,
    "rice": Category.grain,
    "cereal": Category.grain,

    # Pantry staple variations
    "pantry_staple": Category.pantry_staple,
    "pantry staple": Category.pantry_staple,
    "staple": Category.pantry_staple,
    "staples": Category.pantry_staple,

    # Frozen variations
    "frozen": Category.frozen,
    "frozen food": Category.frozen,
    "frozen foods": Category.frozen,

    # Snack variations
    "snack": Category.snack,
    "snacks": Category.snack,
    "chips": Category.snack,

    # Condiment variations
    "condiment": Category.condiment,
    "condiments": Category.condiment,
    "sauce": Category.condiment,
    "sauces": Category.condiment,
    "dressing": Category.condiment,

    # Beverage variations
    "beverage": Category.beverage,
    "beverages": Category.beverage,
    "drink": Category.beverage,
    "drinks": Category.beverage,
    "soda": Category.beverage,
    "juice": Category.beverage,
    "water": Category.beverage,

    # Spice variations
    "spice": Category.spice,
    "spices": Category.spice,
    "seasoning": Category.spice,
    "seasonings": Category.spice,
    "herb": Category.spice,
    "herbs": Category.spice,

    # Baking variations
    "baking": Category.baking,
    "flour": Category.baking,
    "sugar": Category.baking,
    "baking supplies": Category.baking,

    # Oil/vinegar variations
    "oil_vinegar": Category.oil_vinegar,
    "oil": Category.oil_vinegar,
    "oils": Category.oil_vinegar,
    "vinegar": Category.oil_vinegar,
    "oil & vinegar": Category.oil_vinegar,

    # Canned variations
    "canned": Category.canned,
    "canned goods": Category.canned,
    "canned food": Category.canned,

    # Other
    "other": Category.other,
    "misc": Category.other,
    "miscellaneous": Category.other,
}


def map_category_guess_to_enum(category_guess: str | None) -> Category:
    """
    Map LLM category guess string to Category enum value.

    Performs case-insensitive matching against known category variations.
    Defaults to Category.other if null or unrecognized.

    Args:
        category_guess: LLM's category guess string (nullable)

    Returns:
        Matched Category enum value, or Category.other if no match
    """
    if not category_guess:
        return Category.other

    # Normalize: lowercase and strip whitespace
    normalized = category_guess.lower().strip()

    # Lookup in mapping dictionary
    return CATEGORY_MAPPING.get(normalized, Category.other)


def infer_storage_location(category: Category) -> StorageLocation:
    """
    Infer storage location based on item category.

    Mapping rules:
    - produce, dairy → fridge
    - frozen → freezer
    - all others → pantry (including protein, which defaults to pantry
      since we can't distinguish fresh vs shelf-stable without context)

    Args:
        category: Item category enum value

    Returns:
        Inferred StorageLocation enum value
    """
    if category in {Category.produce, Category.dairy}:
        return StorageLocation.fridge
    elif category == Category.frozen:
        return StorageLocation.freezer
    else:
        return StorageLocation.pantry


def map_receipt_to_inventory(parse_result: ReceiptParseResult) -> list[ReceiptInventoryCandidate]:
    """
    Transform receipt parse result into inventory candidate items.

    Maps each receipt line item to a ReceiptInventoryCandidate with:
    - Normalized category (maps LLM guess to Category enum)
    - Inferred storage location (based on category)
    - Default quantity (1.0 if null)
    - Default unit (count)
    - Price from total_price (nullable)

    This is a pure transformation function with no database writes.
    Users will review and confirm candidates before inventory creation.

    Args:
        parse_result: Parsed receipt data with store name, date, and line items

    Returns:
        List of inventory candidates ready for user confirmation

    Example:
        >>> parse_result = ReceiptParseResult(
        ...     store_name="Costco",
        ...     receipt_date=date(2026, 4, 4),
        ...     line_items=[
        ...         ReceiptLineItem(
        ...             item_name="Organic Bananas",
        ...             quantity=3.0,
        ...             total_price=2.99,
        ...             category_guess="produce"
        ...         )
        ...     ]
        ... )
        >>> candidates = map_receipt_to_inventory(parse_result)
        >>> candidates[0].category
        'produce'
        >>> candidates[0].storage_location
        'fridge'
    """
    candidates = []

    for line_item in parse_result.line_items:
        # Map category guess to enum (defaults to 'other' if null/unrecognized)
        category = map_category_guess_to_enum(line_item.category_guess)

        # Infer storage location from category
        storage_location = infer_storage_location(category)

        # Use quantity from line item, default to 1.0 if null
        quantity = line_item.quantity if line_item.quantity is not None else 1.0

        # Default unit to 'count' (most receipts don't specify units)
        unit = UnitType.count

        # Use total_price as price (nullable, deferred per scope boundary)
        price = line_item.total_price

        # Create candidate
        candidate = ReceiptInventoryCandidate(
            name=line_item.item_name,
            quantity=quantity,
            unit=unit.value,
            category=category.value,
            storage_location=storage_location.value,
            price=price,
        )

        candidates.append(candidate)

    logger.debug(
        f"Mapped {len(candidates)} receipt line items to inventory candidates "
        f"from store '{parse_result.store_name}'"
    )

    return candidates


def submit_receipt(
    receipt_text: str,
    user_id: UUID,
    db: Session,
    store_name: Optional[str] = None,
) -> ProcessingTask:
    """
    Submit receipt text for async LLM parsing.

    Creates a ProcessingTask with task_type='receipt_parse' and stores
    the receipt text and optional store name as JSON in input_reference.
    The background task worker will pick up and process this task.

    Args:
        receipt_text: Receipt text content (digital copy-paste or OCR output)
        user_id: ID of the authenticated user submitting the receipt
        db: Database session
        store_name: Optional store name for store-specific parsing hints

    Returns:
        ProcessingTask: Created task with status='pending'

    Raises:
        ValidationError: If database integrity constraint is violated
        RuntimeError: If database error occurs during task creation
    """
    # Create JSON input_reference matching task worker expectations
    # (see task_worker.py lines 68-83 for JSON format parsing)
    input_data = {
        "receipt_text": receipt_text,
        "store_name": store_name
    }
    input_reference = json.dumps(input_data)

    # Create ProcessingTask
    task = ProcessingTask(
        user_id=user_id,
        task_type=TaskType.receipt_parse.value,
        status=TaskStatus.pending.value,
        input_reference=input_reference,
    )

    db.add(task)

    try:
        db.commit()
        db.refresh(task)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during receipt submission for user {user_id}")
        logger.debug(f"Integrity error occurred during receipt submission: {e}")
        raise ValidationError("Receipt submission failed due to data integrity violation")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during receipt submission for user {user_id}")
        logger.debug(f"Database error occurred during receipt submission: {e}")
        raise RuntimeError("An error occurred while submitting the receipt") from e

    # Sanitize store_name for logging to prevent log injection
    safe_store_name = store_name.replace('\n', ' ').replace('\r', ' ') if store_name else None
    logger.info(
        f"Receipt submitted for processing: user_id={user_id}, "
        f"task_id={task.id}, store_name={safe_store_name}"
    )

    return task


def confirm_receipt_items(
    task_id: UUID,
    candidates: list[ReceiptInventoryCandidate],
    user_id: UUID,
    db: Session
) -> list[InventoryItem]:
    """
    Confirm receipt inventory candidates and create inventory items.

    Validates that the task exists, belongs to the user, and has completed successfully
    before creating inventory items from the confirmed candidates.

    Multi-tenant isolation: Service layer validates task ownership to ensure users
    can only confirm their own receipt parsing tasks (defense-in-depth).

    Args:
        task_id: ID of the receipt parsing task to confirm
        candidates: List of user-reviewed inventory candidates to create
        user_id: ID of the authenticated user
        db: Database session

    Returns:
        List of created InventoryItem objects

    Raises:
        NotFoundError: If task doesn't exist or doesn't belong to user
        ValidationError: If task type is not "receipt_parse" or status is not "completed"
    """
    # Retrieve task with multi-tenant isolation (defense-in-depth)
    task = get_task_by_id(task_id, user_id, db)

    if not task:
        logger.warning(f"Task {task_id} not found for user {user_id}")
        raise NotFoundError("Receipt parsing task not found")

    # Validate task type (defensive programming: ensure service preconditions)
    if task.task_type != TaskType.receipt_parse.value:
        logger.warning(
            f"Attempt to confirm non-receipt task {task_id} "
            f"(task_type: {task.task_type}) by user {user_id}"
        )
        raise ValidationError(f"Cannot confirm receipt: task type is '{task.task_type}', must be 'receipt_parse'")

    # Validate task has completed successfully
    if task.status != TaskStatus.completed.value:
        logger.warning(
            f"Attempt to confirm non-completed task {task_id} "
            f"(status: {task.status}) by user {user_id}"
        )
        raise ValidationError(f"Cannot confirm receipt: task status is '{task.status}', must be 'completed'")

    # Convert candidates to InventoryItemCreate schemas
    items_to_create = [
        InventoryItemCreate(
            name=candidate.name,
            quantity=candidate.quantity,
            unit=candidate.unit,
            category=candidate.category,
            storage_location=candidate.storage_location,
            price=candidate.price,
            added_by=user_id,  # Will be overridden by service layer for security
        )
        for candidate in candidates
    ]

    # Create inventory items atomically
    created_items = create_inventory_items_bulk(items_to_create, user_id, db)

    logger.info(
        f"Confirmed {len(created_items)} items from task {task_id} for user {user_id}"
    )

    return created_items


def get_receipt_task_status(
    task_id: UUID,
    user_id: UUID,
    db: Session
) -> Optional[ReceiptTaskStatusResponse]:
    """
    Get receipt task status with parsed result.

    Retrieves a receipt parsing task and parses the result_reference JSON
    into a ReceiptParseResult when the task status is 'completed'.

    Multi-tenant isolation: Service layer validates task ownership to ensure
    users can only access their own receipt parsing tasks.

    Args:
        task_id: ID of the receipt parsing task
        user_id: ID of the authenticated user
        db: Database session

    Returns:
        ReceiptTaskStatusResponse with parsed result if completed, None if task not found

    Raises:
        ValidationError: If task type is not "receipt_parse"
        RuntimeError: If result_reference JSON parsing fails for completed task
    """
    # Retrieve task with multi-tenant isolation
    task = get_task_by_id(task_id, user_id, db)

    if not task:
        return None

    # Validate task type (defensive programming: ensure service preconditions)
    if task.task_type != TaskType.receipt_parse.value:
        logger.warning(
            f"Attempt to get receipt status for non-receipt task {task_id} "
            f"(task_type: {task.task_type}) by user {user_id}"
        )
        raise ValidationError(f"Cannot retrieve receipt status: task type is '{task.task_type}', must be 'receipt_parse'")

    # Parse result_reference into ReceiptParseResult if completed
    parsed_result = None
    if task.status == TaskStatus.completed.value and task.result_reference:
        try:
            # Parse JSON string into ReceiptParseResult schema
            result_data = json.loads(task.result_reference)
            parsed_result = ReceiptParseResult.model_validate(result_data)
        except (json.JSONDecodeError, ValueError) as e:
            # Log error and fail the request - result_reference should always be valid for completed tasks
            logger.error(
                f"Failed to parse result_reference for task {task_id}: {e}"
            )
            logger.debug(f"Invalid result_reference content: {task.result_reference}")
            raise RuntimeError("Failed to parse receipt result")

    # Build response
    return ReceiptTaskStatusResponse(
        id=task.id,
        task_type=task.task_type,
        status=task.status,
        input_reference=task.input_reference,
        result_reference=task.result_reference,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        processing_started_at=task.processing_started_at,
        completed_at=task.completed_at,
        parsed_result=parsed_result
    )
