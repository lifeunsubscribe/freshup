"""
Meal plan service for FreshUp.

Provides business logic for auto-draft meal plan generation, weekly plan
retrieval, and entry confirmation with grocery list propagation.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from datetime import date, timedelta
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError

from src.db.models.user import User
from src.db.models.meal_plan import MealPlanEntry, MealPlanStatus, MealType
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.source_catalog import SourceRecipeCard
from src.services import grocery_service
from src.services import recipe_service
from src.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------

@dataclass
class WeekChoice:
    """One slot in the weekly draft: either a card or a recipe."""
    day_offset: int
    kind: str               # "recipe" or "card"
    card: Optional[SourceRecipeCard]
    recipe: Optional[Recipe]
    source: str


def _item_source(item) -> str:
    if item.kind == "card":
        return item.card.source_type
    return getattr(item.recipe, "source_type", "manual")


def _item_prep_time(item) -> Optional[int]:
    """Total prep+cook minutes for an item; None when unknown."""
    if item.kind == "recipe":
        prep = item.recipe.prep_time_minutes or 0
        cook = item.recipe.cook_time_minutes or 0
        total = prep + cook
        return total if (prep or cook) else None
    return item.card.prep_time_minutes


def _cuisine_keys_for(item) -> frozenset:
    from src.services.taste_service import recipe_keys, card_keys
    if item.kind == "recipe":
        keys = recipe_keys(item.recipe)
    else:
        keys = card_keys(item.card, set())
    return frozenset(k for k in keys if k.startswith("cuisine:"))


def _ingredient_keys_for(item) -> frozenset:
    from src.services.taste_service import recipe_keys, card_keys
    if item.kind == "recipe":
        keys = recipe_keys(item.recipe)
    else:
        keys = card_keys(item.card, set())
    return frozenset(k for k in keys if k.startswith("ingredient:"))


def _other_allergy_blocks(item, other_users: list) -> bool:
    """True if any household member (other than the requesting user) has an allergy to this item."""
    from src.services.allergy import stated_allergies, allergy_hit
    for u in other_users:
        allergies = stated_allergies(u)
        if not allergies:
            continue
        if item.kind == "recipe":
            from src.services.taste_service import recipe_keys
            keys = recipe_keys(item.recipe)
            ing_keys = {k[len("ingredient:"):] for k in keys if k.startswith("ingredient:")}
            names = [getattr(ing, "ingredient_name", None) for ing in (item.recipe.ingredients or [])]
            if allergy_hit(allergies, ing_keys, names):
                return True
        else:
            card = item.card
            # Unknown ingredients are not safe for allergic users
            if card.ingredient_keys is None:
                return True
            ing_keys = set(card.ingredient_keys)
            if allergy_hit(allergies, ing_keys, [card.name, getattr(card, "headline", None)]):
                return True
    return False


def select_week(user, db: Session, week_start: date) -> list[WeekChoice]:
    """
    Pure selection: returns up to 7 WeekChoices from rank_candidates(limit=40).

    Rules applied in order (candidates breaking a rule are skipped):
    1. Allergies of every household member block; `never` keys of requesting user block
       (the latter is handled by rank_candidates itself).
    2. No cuisine key shared between two consecutive days.
    3. At most 2 dinners per ingredient key across the week.
    4. Mon–Thu (day offsets 0–3): prefer candidates with prep_time ≤ 40 min when any remain.
    5. At most 1 `explore` item (skipped when none qualify).
    6. When 2+ sources have candidates, at least 2 dinners from a second source.

    Fewer than 7 eligible candidates returns a shorter list; caller logs the warning.
    """
    from src.services.recommendation_service import rank_candidates

    ranked = rank_candidates(user, db, limit=40)
    if not ranked:
        return []

    household_users = db.query(User).all()
    other_users = [u for u in household_users if u.id != user.id]

    all_sources = {_item_source(item) for item in ranked}
    multi_source = len(all_sources) >= 2

    choices: list[WeekChoice] = []
    placed_sources: list[str] = []
    ingredient_counts: dict[str, int] = {}
    last_cuisine_keys: frozenset = frozenset()
    explore_used = False

    unplaced = list(ranked)

    for day_offset in range(7):
        if not unplaced:
            break

        is_weeknight = day_offset <= 3
        remaining_slots = 7 - len(choices)

        # Two-source enforcement: if we're running out of slots and haven't
        # placed 2 from a second source yet, force non-primary picks.
        force_second_source = False
        if multi_source and placed_sources:
            primary = placed_sources[0]
            sec_count = sum(1 for s in placed_sources if s != primary)
            needed = 2 - sec_count
            if needed > 0 and remaining_slots <= needed:
                if any(_item_source(c) != primary for c in unplaced):
                    force_second_source = True

        def _ok(item, enforce_source: bool) -> bool:
            if item.reason == "explore" and explore_used:
                return False
            if _other_allergy_blocks(item, other_users):
                return False
            if _cuisine_keys_for(item) & last_cuisine_keys:
                return False
            ikeys = _ingredient_keys_for(item)
            for k in ikeys:
                if ingredient_counts.get(k, 0) >= 2:
                    return False
            if enforce_source and placed_sources:
                if _item_source(item) == placed_sources[0]:
                    return False
            return True

        candidates = [c for c in unplaced if _ok(c, force_second_source)]

        if not candidates and force_second_source:
            # Relax the source constraint rather than leaving the slot empty
            candidates = [c for c in unplaced if _ok(c, False)]

        if not candidates:
            # No candidate passes all rules for this day; skip this slot so the
            # rest of the week is still evaluated (last_cuisine_keys unchanged:
            # the placed sequence still determines what "consecutive" means).
            continue

        if is_weeknight:
            fast = [c for c in candidates if (pt := _item_prep_time(c)) is None or pt <= 40]
            if fast:
                candidates = fast

        pick = candidates[0]

        if pick.reason == "explore":
            explore_used = True

        ikeys = _ingredient_keys_for(pick)
        for k in ikeys:
            ingredient_counts[k] = ingredient_counts.get(k, 0) + 1
        last_cuisine_keys = _cuisine_keys_for(pick)
        placed_sources.append(_item_source(pick))
        unplaced.remove(pick)

        choices.append(WeekChoice(
            day_offset=day_offset,
            kind=pick.kind,
            card=pick.card,
            recipe=pick.recipe,
            source=_item_source(pick),
        ))

    return choices


def generate_draft_meal_plan(
    week_start: date,
    user_id: UUID,
    db: Session
) -> list[MealPlanEntry]:
    """
    Generate a draft meal plan for up to 7 dinner slots starting from week_start.

    Selects from rank_candidates(limit=40) using select_week() which applies
    variety, weeknight, explore-cap, two-source, and household-allergy rules.
    Card entries point at an unimported catalog card; recipe entries use an
    already-imported recipe.  Fewer than 7 eligible candidates fills what it can.

    Args:
        week_start: Start date of the week (must be Monday)
        user_id: User ID generating the plan
        db: Database session

    Returns:
        List of created MealPlanEntry objects (may be fewer than 7)

    Raises:
        ValidationError: If user not found or database error occurs

    Note:
        Single-household mode: entries are shared across all household members.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValidationError(f"User {user_id} not found")

    week_end = week_start + timedelta(days=6)
    existing_drafts = (
        db.query(MealPlanEntry)
        .filter(MealPlanEntry.date >= week_start)
        .filter(MealPlanEntry.date <= week_end)
        .filter(MealPlanEntry.status == MealPlanStatus.draft.value)
        .count()
    )
    if existing_drafts > 0:
        raise ValidationError(
            f"Draft entries already exist for week starting {week_start}. "
            f"Delete or confirm existing drafts before generating new ones."
        )

    choices = select_week(user, db, week_start)

    if len(choices) < 7:
        logger.warning(
            "Only %d eligible candidates for draft week starting %s; "
            "filling %d slot(s) instead of 7.",
            len(choices), week_start, len(choices),
        )

    entries = []
    for choice in choices:
        entry_date = week_start + timedelta(days=choice.day_offset)
        if choice.kind == "recipe":
            entry = MealPlanEntry(
                date=entry_date,
                meal_type=MealType.dinner.value,
                recipe_id=choice.recipe.id,
                planned_servings=choice.recipe.base_servings,
                status=MealPlanStatus.draft.value,
            )
        else:
            entry = MealPlanEntry(
                date=entry_date,
                meal_type=MealType.dinner.value,
                catalog_card_id=choice.card.id,
                planned_servings=2,  # cards have no base_servings until imported
                status=MealPlanStatus.draft.value,
            )
        db.add(entry)
        entries.append(entry)

    try:
        db.commit()
        for entry in entries:
            db.refresh(entry)
        logger.info(
            "Generated draft meal plan for week starting %s: %d entries created",
            week_start, len(entries),
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
    if not current_user or not current_user.id:
        raise ValidationError("Invalid user session")

    # TODO(multi-household): Add household authorization check here

    # Load entry with catalog card relationship so we can import on demand
    entry = (
        db.query(MealPlanEntry)
        .options(
            selectinload(MealPlanEntry.recipe_rel)
            .selectinload(Recipe.ingredients),
            selectinload(MealPlanEntry.catalog_card_rel),
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

    # Card entry: import the recipe on confirm
    imported_recipe: Optional[Recipe] = None
    if entry.catalog_card_id is not None and entry.recipe_id is None:
        from src.services.catalog_service import open_card
        try:
            result = open_card(db, entry.catalog_card_id)
            if result is None:
                raise ValidationError("Could not bring this recipe in. Try again.")
            imported_recipe = result.recipe
            entry.recipe_id = imported_recipe.id
            entry.planned_servings = imported_recipe.base_servings
        except (ValueError, ValidationError):
            raise ValidationError("Could not bring this recipe in. Try again.")

    # After potential import, we must have a recipe
    if not entry.recipe_id:
        raise ValidationError(
            "Cannot confirm entry without a recipe. "
            "Entry must have a recipe to propagate ingredients to grocery list."
        )

    # Reload the recipe with ingredients if we just did an import, otherwise use relationship
    if imported_recipe is not None:
        recipe = (
            db.query(Recipe)
            .options(selectinload(Recipe.ingredients))
            .filter(Recipe.id == imported_recipe.id)
            .first()
        ) or imported_recipe
    else:
        recipe = entry.recipe_rel
        if recipe is None:
            raise ValidationError(
                "Cannot confirm entry without a recipe. "
                "Entry must have a recipe to propagate ingredients to grocery list."
            )

    entry.status = MealPlanStatus.approved.value

    grocery_items_added = 0

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


def opt_out_entry(
    entry_id: UUID,
    current_user: User,
    db: Session,
) -> MealPlanEntry:
    """
    Remove the calling user from a meal plan entry's opt-in list.

    Idempotent: calling this when the user is already absent returns the
    unchanged entry without error.  The entry itself is never deleted —
    an empty opt-in list just means no one is currently opted in; the
    household can decide what to do about it.

    Serving recomputation rule:
        planned_servings = len(remaining_opt_ins)   when that count > 0
        planned_servings unchanged                  when the list empties

    Args:
        entry_id: ID of the entry to opt out of.
        current_user: The authenticated user opting out.
        db: Database session.

    Returns:
        The updated MealPlanEntry with user_opt_ins loaded.

    Raises:
        NotFoundError: If the entry doesn't exist.

    Note:
        Single-household mode: any authenticated user can opt out of any
        entry.  When multi-household support is added a household membership
        check should be inserted before the opt-out logic.
    """
    # TODO(multi-household): verify entry.household_id == current_user.household_id
    # before allowing the opt-out.

    # Load the entry with its current opt-in list
    entry = (
        db.query(MealPlanEntry)
        .options(selectinload(MealPlanEntry.user_opt_ins))
        .filter(MealPlanEntry.id == entry_id)
        .first()
    )

    if not entry:
        raise NotFoundError(f"Meal plan entry {entry_id} not found")

    # Remove the caller from opt-ins only if they are currently present.
    # This makes the operation idempotent: a user who was never opted in
    # (or who already opted out) gets a 200 with the unchanged entry.
    opted_in_ids = {u.id for u in entry.user_opt_ins}
    if current_user.id in opted_in_ids:
        entry.user_opt_ins = [u for u in entry.user_opt_ins if u.id != current_user.id]

        # Recompute planned_servings from the remaining opt-in count.
        # If nobody is left we leave planned_servings alone so the household
        # retains the original serving target for future reference.
        remaining = len(entry.user_opt_ins)
        if remaining > 0:
            entry.planned_servings = remaining

    try:
        db.commit()
        db.refresh(entry)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during opt-out for entry {entry_id}: {e}")
        raise ValidationError("Failed to opt out of meal plan entry")

    # Reload with fresh opt-ins so the response serialiser can access the list
    entry_with_opts = (
        db.query(MealPlanEntry)
        .options(selectinload(MealPlanEntry.user_opt_ins))
        .filter(MealPlanEntry.id == entry.id)
        .one()
    )

    logger.info(
        f"User {current_user.id} opted out of meal plan entry {entry_id}; "
        f"remaining opt-ins: {len(entry_with_opts.user_opt_ins)}"
    )
    return entry_with_opts


def create_entry(
    request_date: date,
    meal_type: str,
    recipe_id: UUID,
    planned_servings: int | None,
    notes: str | None,
    current_user: User,
    db: Session,
) -> MealPlanEntry:
    """
    Create a single draft meal plan entry for a given date and meal slot.

    Places a recipe into the household meal plan for the specified date and
    meal type. Multiple entries for the same date/meal slot are permitted
    (e.g. two different dinners for different household members).

    Side effects:
    - Appends the calling user to the entry's user_opt_ins association.
    - Calls trigger_persistence so browse-cache recipes survive the cleanup job.

    Args:
        request_date: Calendar date for the meal.
        meal_type: One of 'breakfast', 'lunch', 'dinner', 'snack'.
        recipe_id: ID of the recipe to plan.
        planned_servings: Serving count; defaults to recipe.base_servings when None.
        notes: Optional free-text annotation.
        current_user: The authenticated user making the request.
        db: Database session.

    Returns:
        The newly created MealPlanEntry with user_opt_ins loaded.

    Raises:
        NotFoundError: If the recipe does not exist.
        ValidationError: If planned_servings is not positive.
    """
    # Look up the recipe — 404 if it doesn't exist
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise NotFoundError(f"Recipe {recipe_id} not found")

    # Apply the serving default before any validation so the error message
    # correctly reflects what was used.
    servings = planned_servings if planned_servings is not None else recipe.base_servings

    # Guard: base_servings should always be >= 1, but validate defensively.
    # Also handles None (recipe.base_servings not set) to avoid TypeError.
    if servings is None or servings < 1:
        raise ValidationError("planned_servings must be greater than 0")

    # Build the entry; status is always draft for user-created entries
    entry = MealPlanEntry(
        date=request_date,
        meal_type=meal_type,
        recipe_id=recipe.id,
        planned_servings=servings,
        status=MealPlanStatus.draft.value,
        notes=notes,
    )
    db.add(entry)

    # Flush to assign entry.id before manipulating the association table
    db.flush()

    # Opt the calling user in — they requested this meal
    entry.user_opt_ins.append(current_user)

    # Persist the recipe so the cleanup job won't delete a planned recipe.
    # trigger_persistence is idempotent but only commits when the recipe was
    # not already persisted; we therefore always commit explicitly below to
    # ensure the entry and opt-in rows flushed above are durably saved.
    try:
        recipe_service.trigger_persistence(recipe, db)
        db.commit()
        db.refresh(entry)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error while persisting recipe {recipe_id}: {e}")
        raise ValidationError("Failed to create meal plan entry")

    # Re-load with opt-ins so the schema serialiser can access the relationship
    db.refresh(entry)
    entry_with_opts = (
        db.query(MealPlanEntry)
        .options(selectinload(MealPlanEntry.user_opt_ins))
        .filter(MealPlanEntry.id == entry.id)
        .one()
    )

    logger.info(
        f"Created meal plan entry for user {current_user.id}: "
        f"recipe={recipe_id}, date={request_date}, meal_type={meal_type}"
    )
    return entry_with_opts
