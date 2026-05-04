"""
Meal plan service for FreshUp.

Provides business logic for auto-draft meal plan generation, weekly plan
retrieval, and entry confirmation with grocery list propagation.
"""

import logging
from uuid import UUID
from datetime import date, timedelta
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError

from src.db.models.user import User
from src.db.models.meal_plan import MealPlanEntry, MealPlanStatus, MealType
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.services import feed_service
from src.services import grocery_service
from src.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def generate_draft_meal_plan(
    week_start: date,
    user_id: UUID,
    db: Session
) -> list[MealPlanEntry]:
    """
    Generate a draft meal plan for 7 dinner slots starting from week_start.

    Uses feed service query patterns for recipe selection:
    1. Expiring inventory first (get_make_now_recipes)
    2. Familiar recipes next (get_on_repeat_recipes)
    3. Popular/new recipes as fallback

    Args:
        week_start: Start date of the week (should be Monday)
        user_id: User ID generating the plan (used for recipe personalization)
        db: Database session

    Returns:
        List of created MealPlanEntry objects

    Raises:
        ValidationError: If draft generation fails or user not found

    Note:
        This system currently operates in single-household mode where all meal plan
        entries are shared across all household members. The created entries are not
        associated with a specific user - they belong to the household collectively.
        Future multi-household support will require adding household_id to both User
        and MealPlanEntry models.
    """
    # Verify user exists and is authenticated
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValidationError(f"User {user_id} not found")
    # Get recipe recommendations using feed service patterns
    # Priority 1: Recipes user can make now (expiring inventory)
    make_now_recipes = feed_service.get_make_now_recipes(user_id, db, limit=3)

    # Priority 2: Recipes user repeatedly engages with (familiar)
    on_repeat_recipes = feed_service.get_on_repeat_recipes(user_id, db, limit=4)

    # Priority 3: Popular recipes as fallback
    popular_recipes = feed_service.get_popular_recipes(db, limit=10)

    # Combine recipe pools, avoiding duplicates
    # Order matters: make_now → on_repeat → popular preserves priority
    # A recipe that appears in multiple pools will use its first (highest priority) position
    recipe_pool = []
    seen_ids = set()

    for recipe in make_now_recipes + on_repeat_recipes + popular_recipes:
        if recipe.id not in seen_ids:
            recipe_pool.append(recipe)
            seen_ids.add(recipe.id)

    if len(recipe_pool) < 7:
        logger.warning(
            f"Only {len(recipe_pool)} recipes available for draft generation. "
            f"Need 7 for full week."
        )
        raise ValidationError(
            f"Insufficient recipes to generate full week plan. "
            f"Found {len(recipe_pool)}, need 7."
        )

    # Create 7 dinner entries for the week
    entries = []
    for day_offset in range(7):
        entry_date = week_start + timedelta(days=day_offset)
        recipe = recipe_pool[day_offset]

        entry = MealPlanEntry(
            date=entry_date,
            meal_type=MealType.dinner.value,
            recipe_id=recipe.id,
            planned_servings=recipe.base_servings,
            status=MealPlanStatus.draft.value,
        )
        db.add(entry)
        entries.append(entry)

    try:
        db.commit()
        # Refresh to load relationships
        for entry in entries:
            db.refresh(entry)
        logger.info(
            f"Generated draft meal plan for week starting {week_start}: "
            f"{len(entries)} entries created"
        )
        return entries
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during draft generation: {e}")
        raise ValidationError("Failed to generate draft meal plan")


def get_week_plan(
    week_start: date,
    user_id: UUID,
    db: Session
) -> tuple[list[MealPlanEntry], list[MealPlanEntry]]:
    """
    Get meal plan entries for a specific week, separated by status.

    Returns household meal plan entries with user opt-in information.

    Args:
        week_start: Start date of the week
        user_id: User ID requesting the plan (currently for validation only;
                 reserved for future household filtering when multi-household
                 support is added)
        db: Database session

    Returns:
        Tuple of (confirmed_entries, draft_entries)

    Raises:
        ValidationError: If user not found

    Note:
        This system currently operates in single-household mode. All authenticated
        users in the household can view all meal plan entries. When multi-household
        support is added, this function will filter entries by household_id.
    """
    # Verify user exists and is authenticated
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValidationError(f"User {user_id} not found")
    week_end = week_start + timedelta(days=6)

    # Query all entries for the week with user opt-ins loaded
    all_entries = (
        db.query(MealPlanEntry)
        .options(selectinload(MealPlanEntry.user_opt_ins))
        .filter(MealPlanEntry.date >= week_start)
        .filter(MealPlanEntry.date <= week_end)
        .order_by(MealPlanEntry.date, MealPlanEntry.meal_type)
        .all()
    )

    # Separate by status
    confirmed_entries = [
        e for e in all_entries
        if e.status == MealPlanStatus.approved.value
    ]
    draft_entries = [
        e for e in all_entries
        if e.status == MealPlanStatus.draft.value
    ]

    logger.info(
        f"Retrieved week plan for {week_start}: "
        f"{len(confirmed_entries)} confirmed, {len(draft_entries)} draft"
    )

    return confirmed_entries, draft_entries


def confirm_entry(
    entry_id: UUID,
    current_user: User,
    db: Session
) -> tuple[MealPlanEntry, int]:
    """
    Confirm a draft meal plan entry and propagate ingredients to grocery list.

    Transitions entry from draft → approved and creates grocery list items
    for the recipe's ingredients.

    Args:
        entry_id: ID of the entry to confirm
        current_user: User confirming the entry
        db: Database session

    Returns:
        Tuple of (updated_entry, grocery_items_added)

    Raises:
        NotFoundError: If entry doesn't exist
        ValidationError: If entry is not in draft status or has no recipe

    Note:
        This system currently operates in single-household mode. Any authenticated
        household member can confirm any meal plan entry, as all entries are shared
        household resources. When multi-household support is added, this function
        will verify the entry belongs to the user's household before allowing
        confirmation.
    """
    # Verify current_user is valid (basic validation)
    if not current_user or not current_user.id:
        raise ValidationError("Invalid user session")
    # Load entry with recipe and ingredients
    entry = (
        db.query(MealPlanEntry)
        .options(
            selectinload(MealPlanEntry.recipe_rel)
            .selectinload(Recipe.ingredients)
        )
        .filter(MealPlanEntry.id == entry_id)
        .first()
    )

    if not entry:
        raise NotFoundError(f"Meal plan entry {entry_id} not found")

    if entry.status != MealPlanStatus.draft.value:
        raise ValidationError(
            f"Cannot confirm entry with status '{entry.status}'. "
            f"Only draft entries can be confirmed."
        )

    if not entry.recipe_id or not entry.recipe_rel:
        raise ValidationError(
            "Cannot confirm entry without a recipe. "
            "Entry must have a recipe to propagate ingredients to grocery list."
        )

    # Update status to approved
    entry.status = MealPlanStatus.approved.value

    # Propagate recipe ingredients to grocery list
    # Each required (non-optional) ingredient becomes a grocery item with source="meal_plan"
    grocery_items_added = 0
    recipe = entry.recipe_rel

    for ingredient in recipe.ingredients:
        # Skip optional ingredients - they don't automatically go to grocery list
        if ingredient.is_optional:
            continue

        try:
            # Create grocery list item for each required ingredient
            # Note: This creates items even if they're already in inventory
            # Future enhancement: check inventory first to avoid duplicates
            grocery_service.create_item(
                item_name=ingredient.ingredient_name,
                quantity=ingredient.quantity,
                unit=ingredient.unit,
                source="meal_plan",  # Tags items as coming from meal plan confirmation
                current_user=current_user,
                db=db,
            )
            grocery_items_added += 1
        except ValidationError as e:
            # Log but continue if a specific ingredient fails validation
            # This prevents one bad ingredient from blocking the entire confirmation
            # Common failure: ingredient unit not compatible with inventory UnitType enum
            logger.warning(
                f"Failed to add ingredient '{ingredient.ingredient_name}' "
                f"to grocery list: {e}"
            )

    try:
        db.commit()
        db.refresh(entry)
        logger.info(
            f"Confirmed meal plan entry {entry_id}: "
            f"added {grocery_items_added} items to grocery list"
        )
        return entry, grocery_items_added
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during entry confirmation: {e}")
        raise ValidationError("Failed to confirm meal plan entry")
