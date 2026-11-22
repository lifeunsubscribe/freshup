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
from src.services import grocery_service
from src.services import recipe_service
from src.services.plan_week import week_days, week_start_of
from src.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Week selection
# ---------------------------------------------------------------------------


@dataclass
class WeekChoice:
    """A single day's recommended dinner entry, chosen by select_week."""

    item: "RankedItem"  # type: ignore[name-defined]  # from recommendation_service
    day: Optional[date] = None  # the day it was chosen for


def _item_keys(item, card_overlap: dict) -> frozenset:
    from src.services.taste_service import card_keys, recipe_keys
    if item.kind == "card":
        return frozenset(card_keys(item.card, card_overlap.get(item.card.id, set())))
    return frozenset(recipe_keys(item.recipe))


def _cuisine_keys(item, card_overlap: dict) -> frozenset:
    return frozenset(k for k in _item_keys(item, card_overlap) if k.startswith("cuisine:"))


def _ingredient_keys(item, card_overlap: dict) -> frozenset:
    return frozenset(k for k in _item_keys(item, card_overlap) if k.startswith("ingredient:"))


def _item_total_time(item) -> Optional[int]:
    if item.kind == "card":
        return item.card.prep_time_minutes  # stored as total time by enrich
    recipe = item.recipe
    p = getattr(recipe, 'prep_time_minutes', 0) or 0
    c = getattr(recipe, 'cook_time_minutes', 0) or 0
    total = p + c
    return total if total > 0 else None


def _item_source(item) -> str:
    if item.kind == "card":
        return item.card.source_type
    return getattr(item.recipe, 'source_type', 'manual') or 'manual'


def _pick_for_slot(
    unplaced: list,
    card_overlap: dict,
    prev_cuisine: frozenset,
    ing_counts: dict,
    explore_placed: int,
    is_weeknight: bool,
    source_counts: dict,
    multi_source: bool,
    slots_left: int,
) -> Optional[object]:
    """
    Return the first candidate from `unplaced` that satisfies the selection rules.

    Rules applied in five relaxation passes:
    1. All five rules (strict).
    2. Same but relax the second-source enforcement.
    3. Same but also relax the weeknight time constraint.
    4. Skip only the explore limit (allow at most 1 explore item).
    5. Take anything, but still refuse a second explore item when one is placed.
    Returns None only when unplaced is empty or all remaining are blocked explores.
    """
    dominant = max(source_counts, key=lambda s: source_counts[s]) if source_counts else None
    second_count = sum(v for s, v in source_counts.items() if s != dominant) if dominant else 0
    # Enforce second-source when we're running out of slots to meet the minimum.
    need_second = multi_source and second_count < 2 and slots_left <= (2 - second_count)

    has_fast = any(
        _item_total_time(c) is None or _item_total_time(c) <= 40
        for c in unplaced
    ) if is_weeknight else False

    def _reject(c, enforce_weeknight: bool, enforce_second: bool) -> bool:
        if c.reason == "explore" and explore_placed >= 1:
            return True
        if _cuisine_keys(c, card_overlap) & prev_cuisine:
            return True
        c_ing = _ingredient_keys(c, card_overlap)
        if any(ing_counts.get(k, 0) >= 2 for k in c_ing):
            return True
        if enforce_weeknight and has_fast:
            t = _item_total_time(c)
            if t is not None and t > 40:
                return True
        if enforce_second and dominant and _item_source(c) == dominant:
            return True
        return False

    # Pass 1: all constraints
    for c in unplaced:
        if not _reject(c, enforce_weeknight=is_weeknight, enforce_second=need_second):
            return c

    # Pass 2: relax second-source
    if need_second:
        for c in unplaced:
            if not _reject(c, enforce_weeknight=is_weeknight, enforce_second=False):
                return c

    # Pass 3: relax weeknight time constraint too
    for c in unplaced:
        if not _reject(c, enforce_weeknight=False, enforce_second=False):
            return c

    # Pass 4: relax all except explore (never place more than one explore item)
    for c in unplaced:
        if c.reason == "explore" and explore_placed >= 1:
            continue
        return c

    # Pass 5: take anything except a second explore item
    for c in unplaced:
        if c.reason == "explore" and explore_placed >= 1:
            continue
        return c
    return None


# A dinner planned or suggested within this many weeks either side of the week
# being drafted is not suggested again, so consecutive weeks differ.
_VARIETY_WEEKS = 3


def _planned_nearby(db: Session, week_start: date) -> tuple[set[UUID], set[UUID]]:
    """Card ids and recipe ids on plan entries in the weeks around `week_start`."""
    rows = (
        db.query(MealPlanEntry.catalog_card_id, MealPlanEntry.recipe_id)
        .filter(MealPlanEntry.date >= week_start - timedelta(weeks=_VARIETY_WEEKS))
        .filter(MealPlanEntry.date < week_start + timedelta(weeks=_VARIETY_WEEKS + 1))
        .all()
    )
    card_ids = {card_id for card_id, _ in rows if card_id is not None}
    recipe_ids = {recipe_id for _, recipe_id in rows if recipe_id is not None}
    return card_ids, recipe_ids


def _ranked_key(item) -> tuple[str, UUID]:
    return (item.kind, item.card.id if item.kind == "card" else item.recipe.id)


def select_week(
    user, db: Session, week_start: date, days: Optional[list[date]] = None
) -> list[WeekChoice]:
    """
    Pure selection: returns one WeekChoice per day, for the seven days of the
    week or for just the `days` given (the days of that week still to fill).

    Calls rank_candidates(limit=40), filters for all household members'
    allergies, then fills seven slots applying the variety and weeknight
    rules.  Never raises; logs a warning when fewer than 7 slots can be
    filled.

    Rules applied (in priority order, skipping candidates that break a rule):
    - No cuisine key on two consecutive days; at most 2 dinners per
      ingredient key across the week.
    - Monday to Thursday take candidates ≤40 min total when any remain.
    - Exactly one explore item when one exists.
    - When ≥2 sources have candidates, at least 2 dinners from a second source.
    - Allergies of every household member block; `never` keys of the requesting
      user block (rank_candidates handles the requesting user; this function
      additionally filters for every other member).
    - Nothing already on the plan within `_VARIETY_WEEKS` weeks either side is
      suggested again, unless too few other candidates remain to fill the week.
    - These are dinner slots: candidates the meal-type classification marks as
      breakfast, dessert, snack, side or appetizer are used only when the
      dinners run out.
    """
    from src.services.recommendation_service import rank_candidates, suits_dinner
    from src.services.taste_service import card_keys, is_blocked, is_card_blocked
    from src.services.card_tags import overlap_tags

    nearby_cards, nearby_recipes = _planned_nearby(db, week_start)
    candidates = rank_candidates(
        user, db, limit=40,
        exclude_card_ids=nearby_cards, exclude_recipe_ids=nearby_recipes,
    )
    if len(candidates) < 7 and (nearby_cards or nearby_recipes):
        # A small pool: repeats are better than empty days. They go last, so
        # they are used only for the slots nothing fresh can fill.
        fresh = {_ranked_key(c) for c in candidates}
        candidates += [
            c for c in rank_candidates(user, db, limit=40) if _ranked_key(c) not in fresh
        ]
    if not candidates:
        logger.warning("select_week: no candidates from rank_candidates for week %s", week_start)
        return []

    # Compute overlap keys for all card candidates (needed for allergy check).
    card_ids = [c.card.id for c in candidates if c.kind == "card" and c.card is not None]
    card_overlap: dict = overlap_tags(db, card_ids) if card_ids else {}

    # Filter for every other household member's allergies.
    # rank_candidates already filtered for the requesting user (allergies + never).
    # Other members: check both allergies and never-preferences (conservative,
    # prevents recommending something the household collectively dislikes).
    other_members = db.query(User).filter(User.id != user.id).all()

    def _blocked_by_household(c) -> bool:
        for member in other_members:
            if c.kind == "card":
                keys = card_keys(c.card, card_overlap.get(c.card.id, set()))
                if is_card_blocked(c.card, keys, member):
                    return True
            else:
                if is_blocked(c.recipe, member):
                    return True
        return False

    eligible = [c for c in candidates if not _blocked_by_household(c)]
    dinners = [c for c in eligible if suits_dinner(c, card_overlap)]
    not_dinners = [c for c in eligible if not suits_dinner(c, card_overlap)]
    multi_source = len({_item_source(c) for c in dinners}) >= 2

    week: list[WeekChoice] = []
    unplaced = dinners
    prev_cuisine: frozenset = frozenset()
    ing_counts: dict = {}
    explore_placed = 0
    source_counts: dict = {}

    if days is None:
        days = week_days(week_start)

    for position, day in enumerate(days):
        if not unplaced:
            # Out of dinners: fall back to the rest rather than leave days empty.
            unplaced, not_dinners = not_dinners, []
        if not unplaced:
            break
        # By the calendar, not by position: the week starts on Sunday.
        is_weeknight = day.weekday() <= 3  # Mon=0 ... Thu=3

        pick = _pick_for_slot(
            unplaced, card_overlap, prev_cuisine, ing_counts, explore_placed,
            is_weeknight, source_counts, multi_source, slots_left=len(days) - position,
        )
        if pick is None:
            break

        week.append(WeekChoice(item=pick, day=day))
        unplaced.remove(pick)

        prev_cuisine = _cuisine_keys(pick, card_overlap)
        for k in _ingredient_keys(pick, card_overlap):
            ing_counts[k] = ing_counts.get(k, 0) + 1
        if pick.reason == "explore":
            explore_placed += 1
        src = _item_source(pick)
        source_counts[src] = source_counts.get(src, 0) + 1

    if len(week) < 7:
        logger.warning(
            "select_week: only %d/%d eligible candidates for week starting %s",
            len(week), 7, week_start,
        )

    return week


def generate_draft_meal_plan(
    week_start: date,
    user_id: UUID,
    db: Session,
    from_date: Optional[date] = None,
) -> list[MealPlanEntry]:
    """
    Suggest a dinner for every day of the week that has none.

    An empty week gets up to seven; a week that already holds dinners, accepted
    or suggested, gets suggestions only for its free days.  Delegates candidate
    selection to select_week(), which applies ranking-based selection with
    variety, weeknight, and two-source rules.  Fewer eligible candidates than
    free days fills what it can and logs a warning.

    Args:
        week_start: First day of the week (a Sunday)
        from_date: When given, days before it are left alone
        user_id: User ID generating the plan (used for personalization)
        db: Database session

    Returns:
        List of created MealPlanEntry objects (may be fewer than 7)

    Raises:
        ValidationError: If user not found or every day already has a dinner

    Note:
        Single-household mode: entries belong to the household collectively.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValidationError(f"User {user_id} not found")

    week_end = week_start + timedelta(days=6)
    taken = {
        entry_date
        for (entry_date,) in db.query(MealPlanEntry.date)
        .filter(MealPlanEntry.date >= week_start)
        .filter(MealPlanEntry.date <= week_end)
        .filter(MealPlanEntry.meal_type == MealType.dinner.value)
        .all()
    }
    free_days = [
        day for day in week_days(week_start)
        if day not in taken and (from_date is None or day >= from_date)
    ]
    if not free_days:
        raise ValidationError(
            f"Every day left in the week starting {week_start} already has a dinner. "
            f"Swap a suggestion to change one."
        )

    choices = select_week(user, db, week_start, days=free_days)

    entries = []
    for choice in choices:
        entry_date = choice.day
        item = choice.item

        if item.kind == "recipe":
            entry = MealPlanEntry(
                date=entry_date,
                meal_type=MealType.dinner.value,
                recipe_id=item.recipe.id,
                planned_servings=item.recipe.base_servings,
                status=MealPlanStatus.draft.value,
            )
        else:
            # Card entry: recipe is not yet imported; planned_servings=2 until confirmed.
            entry = MealPlanEntry(
                date=entry_date,
                meal_type=MealType.dinner.value,
                catalog_card_id=item.card.id,
                planned_servings=2,
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
        logger.error("Database error during draft generation: %s", e)
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
        .options(
            selectinload(MealPlanEntry.user_opt_ins),
            selectinload(MealPlanEntry.recipe_rel),
            selectinload(MealPlanEntry.catalog_card_rel),
        )
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

    # TODO(multi-household): Add household authorization check here
    # When household_id is added to User and MealPlanEntry models, verify that:
    # 1. entry.household_id == current_user.household_id
    # 2. Raise NotFoundError (not 403) if household mismatch to prevent info leakage
    # This prevents users from confirming meal plan entries belonging to other households.

    # Load entry with recipe, ingredients, and catalog card relationship.
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

    # Card entry: import the recipe on demand before confirming.
    if entry.recipe_id is None and entry.catalog_card_id is not None:
        from src.services.catalog_service import open_card
        try:
            result = open_card(db, entry.catalog_card_id)
        except (ValueError, Exception) as exc:
            logger.warning("open_card failed for card %s: %s", entry.catalog_card_id, exc)
            raise ValidationError("Could not bring this recipe in. Try again.")
        if result is None:
            raise ValidationError("Could not bring this recipe in. Try again.")
        # Link the imported recipe to the entry.
        entry.recipe_id = result.recipe.id
        entry.recipe_rel = result.recipe
        entry.planned_servings = result.recipe.base_servings

    if not entry.recipe_id or not entry.recipe_rel:
        raise ValidationError(
            "Cannot confirm entry without a recipe. "
            "Entry must have a recipe to propagate ingredients to grocery list."
        )

    # Update status to approved
    entry.status = MealPlanStatus.approved.value

    # Propagate recipe ingredients to grocery list.
    # Each required (non-optional) ingredient becomes a grocery item with source="meal_plan".
    grocery_items_added = 0
    recipe = entry.recipe_rel

    # Reload ingredients if not yet loaded (card entries import the recipe in-flight).
    if not recipe.ingredients:
        db.refresh(recipe)

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
                # The list shows which recipe each item is for, and removing
                # the meal takes its unpurchased items off the list again.
                linked_recipe=recipe.id,
                linked_meal_plan_entry=entry.id,
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
        .options(
            selectinload(MealPlanEntry.user_opt_ins),
            selectinload(MealPlanEntry.recipe_rel),
            selectinload(MealPlanEntry.catalog_card_rel),
        )
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
        .options(
            selectinload(MealPlanEntry.user_opt_ins),
            selectinload(MealPlanEntry.recipe_rel),
            selectinload(MealPlanEntry.catalog_card_rel),
        )
        .filter(MealPlanEntry.id == entry.id)
        .one()
    )

    logger.info(
        f"User {current_user.id} opted out of meal plan entry {entry_id}; "
        f"remaining opt-ins: {len(entry_with_opts.user_opt_ins)}"
    )
    return entry_with_opts


def swap_entry(
    entry_id: UUID,
    user_id: UUID,
    db: Session,
    also_exclude_card_ids: frozenset = frozenset(),
    also_exclude_recipe_ids: frozenset = frozenset(),
) -> MealPlanEntry:
    """
    Replace a suggested (draft) dinner with the next best candidate for that day.

    Applies the same weeknight and household-allergy rules used by select_week,
    but operates on a single slot.  Tracks previously offered items in
    entry.user_variations["swap_history"] so repeated swaps on the same day
    never re-surface an item already shown.

    Args:
        entry_id: ID of the draft entry to swap.
        user_id: ID of the requesting user.
        db: Database session.

    Returns:
        The updated MealPlanEntry with relationships loaded.

    Raises:
        NotFoundError: If the entry does not exist.
        ValidationError: If the entry is not in draft status, or no suitable
                         candidate can be found.
    """
    from src.services.recommendation_service import rank_candidates, suits_dinner
    from src.services.taste_service import is_blocked, is_card_blocked, card_keys
    from src.services.card_tags import overlap_tags

    entry = (
        db.query(MealPlanEntry)
        .options(
            selectinload(MealPlanEntry.recipe_rel),
            selectinload(MealPlanEntry.catalog_card_rel),
        )
        .filter(MealPlanEntry.id == entry_id)
        .first()
    )
    if not entry:
        raise NotFoundError(f"Meal plan entry {entry_id} not found")

    if entry.status != MealPlanStatus.draft.value:
        raise ValidationError(
            f"Cannot swap entry with status '{entry.status}'. "
            f"Only draft entries can be swapped."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValidationError(f"User {user_id} not found")

    # Determine week bounds from the entry's date
    week_start = week_start_of(entry.date)
    week_end = week_start + timedelta(days=6)

    # Exclude every item already placed in this week (other entries)
    week_entries = (
        db.query(MealPlanEntry)
        .filter(
            MealPlanEntry.date >= week_start,
            MealPlanEntry.date <= week_end,
            MealPlanEntry.id != entry_id,
        )
        .all()
    )
    exclude_card_ids: set = set()
    exclude_recipe_ids: set = set()
    for e in week_entries:
        if e.catalog_card_id:
            exclude_card_ids.add(e.catalog_card_id)
        if e.recipe_id:
            exclude_recipe_ids.add(e.recipe_id)

    # Also exclude what this slot is currently showing (we're replacing it)
    if entry.catalog_card_id:
        exclude_card_ids.add(entry.catalog_card_id)
    if entry.recipe_id:
        exclude_recipe_ids.add(entry.recipe_id)

    # Whatever else the caller rules out (a remix rules out the week as it was)
    exclude_card_ids |= set(also_exclude_card_ids)
    exclude_recipe_ids |= set(also_exclude_recipe_ids)

    # Exclude items already offered to the user for this slot in prior swaps
    variations = entry.user_variations or {}
    swap_history = variations.get("swap_history", {})
    for cid in swap_history.get("offered_card_ids", []):
        exclude_card_ids.add(UUID(cid) if isinstance(cid, str) else cid)
    for rid in swap_history.get("offered_recipe_ids", []):
        exclude_recipe_ids.add(UUID(rid) if isinstance(rid, str) else rid)

    candidates = rank_candidates(
        user, db, limit=40,
        exclude_card_ids=exclude_card_ids,
        exclude_recipe_ids=exclude_recipe_ids,
    )
    if not candidates:
        raise ValidationError("No alternative candidates available for this entry.")

    # Filter for every household member's allergies
    other_members = db.query(User).filter(User.id != user.id).all()
    card_ids = [c.card.id for c in candidates if c.kind == "card" and c.card is not None]
    card_overlap = overlap_tags(db, card_ids) if card_ids else {}

    def _household_blocked(c) -> bool:
        for member in other_members:
            if c.kind == "card":
                keys = card_keys(c.card, card_overlap.get(c.card.id, set()))
                if is_card_blocked(c.card, keys, member):
                    return True
            else:
                if is_blocked(c.recipe, member):
                    return True
        return False

    eligible = [c for c in candidates if not _household_blocked(c)]
    if not eligible:
        raise ValidationError("No alternative candidates available for this entry after allergy filtering.")
    if entry.meal_type == MealType.dinner.value:
        # A dinner slot takes a dinner while one is left.
        eligible = [c for c in eligible if suits_dinner(c, card_overlap)] or eligible

    # Apply weeknight time rule (Mon–Thu: prefer ≤40 min candidates)
    is_weeknight = entry.date.weekday() <= 3

    pick = _pick_for_slot(
        eligible,
        card_overlap,
        prev_cuisine=frozenset(),
        ing_counts={},
        explore_placed=0,
        is_weeknight=is_weeknight,
        source_counts={},
        multi_source=False,
        slots_left=1,
    )
    if pick is None:
        raise ValidationError("No alternative candidates available for this entry.")

    # Record what this slot was showing before the swap, so it is not offered again
    new_history: dict = {
        "offered_card_ids": list(swap_history.get("offered_card_ids", [])),
        "offered_recipe_ids": list(swap_history.get("offered_recipe_ids", [])),
    }
    if entry.catalog_card_id:
        new_history["offered_card_ids"].append(str(entry.catalog_card_id))
    if entry.recipe_id:
        new_history["offered_recipe_ids"].append(str(entry.recipe_id))

    # Replace the entry's item
    if pick.kind == "card":
        entry.catalog_card_id = pick.card.id
        entry.recipe_id = None
        entry.planned_servings = 2  # default until confirmed
    else:
        entry.recipe_id = pick.recipe.id
        entry.catalog_card_id = None
        entry.planned_servings = pick.recipe.base_servings

    # Assign a new dict so SQLAlchemy detects the JSON column mutation
    entry.user_variations = {**variations, "swap_history": new_history}

    try:
        db.commit()
        db.refresh(entry)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during swap for entry {entry_id}: {e}")
        raise ValidationError("Failed to swap meal plan entry")

    # Reload with relationships for the response serialiser
    swapped = (
        db.query(MealPlanEntry)
        .options(
            selectinload(MealPlanEntry.recipe_rel),
            selectinload(MealPlanEntry.catalog_card_rel),
            selectinload(MealPlanEntry.user_opt_ins),
        )
        .filter(MealPlanEntry.id == entry_id)
        .one()
    )

    logger.info(
        "Swapped meal plan entry %s for user %s: now shows %s %s",
        entry_id, user_id,
        pick.kind,
        pick.card.id if pick.kind == "card" else pick.recipe.id,
    )
    return swapped


def _create_card_entry(
    request_date: date,
    meal_type: str,
    catalog_card_id: UUID,
    planned_servings: int | None,
    notes: str | None,
    current_user: User,
    db: Session,
) -> MealPlanEntry:
    """A draft entry pointing at a catalog card; see create_entry."""
    from src.db.models.source_catalog import SourceRecipeCard

    card = db.query(SourceRecipeCard).filter(SourceRecipeCard.id == catalog_card_id).first()
    if not card:
        raise NotFoundError(f"Catalog card {catalog_card_id} not found")

    # A card already imported is planned as its recipe, so the entry opens and
    # confirms without another fetch. Servings are unknown until then: 2, as
    # for a suggested card.
    servings = planned_servings if planned_servings is not None else 2
    if servings < 1:
        raise ValidationError("planned_servings must be greater than 0")

    entry = MealPlanEntry(
        date=request_date,
        meal_type=meal_type,
        catalog_card_id=card.id,
        recipe_id=card.recipe_id,
        planned_servings=servings,
        status=MealPlanStatus.draft.value,
        notes=notes,
    )
    db.add(entry)
    db.flush()
    entry.user_opt_ins.append(current_user)
    try:
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error while planning card {catalog_card_id}: {e}")
        raise ValidationError("Failed to create meal plan entry")
    db.refresh(entry)
    return entry


def create_entry(
    request_date: date,
    meal_type: str,
    recipe_id: UUID | None,
    planned_servings: int | None,
    notes: str | None,
    current_user: User,
    db: Session,
    catalog_card_id: UUID | None = None,
) -> MealPlanEntry:
    """
    Create a single draft meal plan entry for a given date and meal slot.

    Places a recipe into the household meal plan for the specified date and
    meal type, or a catalog card that has not been imported yet (its recipe is
    imported when the entry is confirmed, exactly as for a suggested card).
    Multiple entries for the same date/meal slot are permitted
    (e.g. two different dinners for different household members).

    Side effects:
    - Appends the calling user to the entry's user_opt_ins association.
    - Calls trigger_persistence so browse-cache recipes survive the cleanup job.

    Args:
        request_date: Calendar date for the meal.
        meal_type: One of 'breakfast', 'lunch', 'dinner', 'snack'.
        recipe_id: ID of the recipe to plan, or None when a card is given.
        catalog_card_id: ID of the catalog card to plan, or None when a recipe is given.
        planned_servings: Serving count; defaults to recipe.base_servings when None.
        notes: Optional free-text annotation.
        current_user: The authenticated user making the request.
        db: Database session.

    Returns:
        The newly created MealPlanEntry with user_opt_ins loaded.

    Raises:
        NotFoundError: If the recipe or the card does not exist.
        ValidationError: If planned_servings is not positive.
    """
    if catalog_card_id is not None:
        return _create_card_entry(
            request_date, meal_type, catalog_card_id, planned_servings, notes, current_user, db
        )

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
        .options(
            selectinload(MealPlanEntry.user_opt_ins),
            selectinload(MealPlanEntry.recipe_rel),
            selectinload(MealPlanEntry.catalog_card_rel),
        )
        .filter(MealPlanEntry.id == entry.id)
        .one()
    )

    logger.info(
        f"Created meal plan entry for user {current_user.id}: "
        f"recipe={recipe_id}, date={request_date}, meal_type={meal_type}"
    )
    return entry_with_opts


def remove_entry(entry_id: UUID, db: Session) -> int:
    """
    Take a dinner off the plan, suggested or accepted.

    The grocery list follows the plan: items that were added for this meal and
    are not yet purchased come off the list.  Purchased ones stay (the food is
    in the house) and simply lose their link to the meal.

    Returns the number of grocery items removed.

    Raises:
        NotFoundError: If the entry does not exist.
    """
    from src.db.models.grocery_list import GroceryListItem

    entry = db.query(MealPlanEntry).filter(MealPlanEntry.id == entry_id).first()
    if not entry:
        raise NotFoundError(f"Meal plan entry {entry_id} not found")

    linked = (
        db.query(GroceryListItem)
        .filter(GroceryListItem.linked_meal_plan_entry == entry_id)
        .all()
    )
    removed = 0
    for item in linked:
        if item.purchased:
            item.linked_meal_plan_entry = None
        else:
            db.delete(item)
            removed += 1

    try:
        # Flush the grocery changes first: the items point at the entry.
        db.flush()
        entry.user_opt_ins.clear()
        db.delete(entry)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error while removing meal plan entry {entry_id}: {e}")
        raise ValidationError("Failed to remove the meal from the plan")

    logger.info(f"Removed meal plan entry {entry_id}: {removed} grocery items came off the list")
    return removed


def remix_week(
    week_start: date,
    user_id: UUID,
    db: Session,
    from_date: Optional[date] = None,
) -> int:
    """
    Replace every suggested (draft) dinner of the week with a different one.

    Accepted dinners are left alone, and with from_date so are suggestions on
    days before it.  Each suggestion is swapped as swap_entry does it (same
    rules, and nothing a slot has already shown comes back), with one addition:
    nothing the week held before the remix, and nothing on the weeks around it,
    is brought in, so a remix is new dinners and not the same ones on other
    days.  A slot with nothing fresh to offer keeps what it has.

    Returns the number of suggestions that changed.
    """
    week_end = week_start + timedelta(days=6)
    draft_ids = [
        entry_id
        for (entry_id, entry_date) in db.query(MealPlanEntry.id, MealPlanEntry.date)
        .filter(MealPlanEntry.date >= week_start)
        .filter(MealPlanEntry.date <= week_end)
        .filter(MealPlanEntry.status == MealPlanStatus.draft.value)
        .order_by(MealPlanEntry.date)
        .all()
        if from_date is None or entry_date >= from_date
    ]
    held_cards, held_recipes = _planned_nearby(db, week_start)
    changed = 0
    for entry_id in draft_ids:
        try:
            swap_entry(
                entry_id, user_id, db,
                also_exclude_card_ids=frozenset(held_cards),
                also_exclude_recipe_ids=frozenset(held_recipes),
            )
            changed += 1
        except ValidationError as exc:
            logger.info("remix_week: kept entry %s as it was: %s", entry_id, exc)
    return changed
