"""
The week's shopping list: what the accepted dinners of a week need, worked out
as one line per ingredient so it can be reviewed before anything is put on the
grocery list.

Accepting a dinner does not touch the grocery list. Ingredients reach it in
two ways: the user adds an item by hand, or imports this list and approves it
line by line.

For each line this module answers three questions:
- how much does the week need (the same ingredient across dinners is one line),
- what is already in the pantry,
- what is already on the grocery list,
and from those, how much approving the line would add.

No unit conversion is attempted. The same ingredient in two different units is
two lines, and a pantry item in another unit is shown but not subtracted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from src.db.models.grocery_list import GroceryListItem
from src.db.models.inventory_item import InventoryItem
from src.db.models.meal_plan import MealPlanEntry, MealPlanStatus, MealType
from src.db.models.recipe import Recipe
from src.db.models.user import User
from src.exceptions import ValidationError
from src.services import grocery_service
from src.services.import_service import UNPARSEABLE_QUANTITY_SENTINEL, is_unparseable_quantity
from src.services.ingredient_keys import keys_for

logger = logging.getLogger(__name__)

# Spellings of the same unit. Recipes write units out; the pantry abbreviates.
_UNIT_ALIASES: dict[str, str] = {
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp", "tbsps": "tbsp",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "tsps": "tsp",
    "ounce": "oz", "ounces": "oz", "oz": "oz",
    "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb",
    "gram": "g", "grams": "g", "g": "g",
    "kilogram": "kg", "kilograms": "kg", "kg": "kg",
    "milliliter": "ml", "milliliters": "ml", "ml": "ml",
    "liter": "l", "liters": "l", "l": "l",
    "cup": "cup", "cups": "cup",
    "clove": "clove", "cloves": "clove",
    "": "count", "unit": "count", "units": "count", "count": "count", "each": "count",
    "whole": "count", "piece": "count", "pieces": "count",
}


def normalize_unit(unit: Optional[str]) -> str:
    """One spelling per unit, so "2 tablespoons" and "1 tbsp" add up."""
    text = (unit or "").strip().lower()
    if text in _UNIT_ALIASES:
        return _UNIT_ALIASES[text]
    # An unknown unit: fold a plain plural so "sprigs" meets "sprig".
    return text[:-1] if text.endswith("s") and len(text) > 3 else text


def ingredient_identity(name: Optional[str]) -> str:
    """
    What makes two ingredient lines the same ingredient.

    The vocabulary key when the name resolves to exactly one ("yellow onion"
    and "onion" are both `onion`); otherwise the name itself, lower-cased.
    """
    keys = keys_for(name)
    if len(keys) == 1:
        return next(iter(keys))
    return " ".join((name or "").lower().split())


@dataclass
class Need:
    """One dinner's share of a line."""

    entry_id: UUID
    recipe_id: UUID
    recipe_name: str
    day: date
    quantity: float


@dataclass
class ShoppingLine:
    key: str
    name: str
    unit: str
    # True when the recipes give no amount ("salt, to taste").
    to_taste: bool
    quantity: float
    needs: list[Need] = field(default_factory=list)
    # The pantry's matching stock, when there is any.
    pantry_quantity: Optional[float] = None
    pantry_unit: Optional[str] = None
    # True when the pantry's unit is this line's, so it was subtracted.
    pantry_counted: bool = False
    # Amount already on the grocery list for these dinners.
    listed_quantity: float = 0.0
    # True when an item for this ingredient is on the list by other means.
    listed_otherwise: bool = False
    # What approving the line would put on the list.
    add_quantity: float = 0.0
    # Whether the line starts checked.
    suggested: bool = False


def _week_dinners(db: Session, week_start: date) -> list[MealPlanEntry]:
    return (
        db.query(MealPlanEntry)
        .options(selectinload(MealPlanEntry.recipe_rel).selectinload(Recipe.ingredients))
        .filter(MealPlanEntry.date >= week_start)
        .filter(MealPlanEntry.date <= week_start + timedelta(days=6))
        .filter(MealPlanEntry.meal_type == MealType.dinner.value)
        .filter(MealPlanEntry.status == MealPlanStatus.approved.value)
        .order_by(MealPlanEntry.date)
        .all()
    )


def _sources(item: GroceryListItem) -> list[dict]:
    return [s for s in (item.plan_sources or []) if isinstance(s, dict)]


def week_shopping_lines(db: Session, week_start: date) -> tuple[list[ShoppingLine], int]:
    """
    The week's lines, and how many accepted dinners they come from.

    Lines are ordered by name. Optional ingredients are left out.
    """
    dinners = [e for e in _week_dinners(db, week_start) if e.recipe_rel is not None]

    lines: dict[str, ShoppingLine] = {}
    for entry in dinners:
        recipe = entry.recipe_rel
        for ingredient in recipe.ingredients:
            if ingredient.is_optional:
                continue
            to_taste = is_unparseable_quantity(ingredient.quantity)
            unit = normalize_unit(ingredient.unit)
            key = f"{ingredient_identity(ingredient.ingredient_name)}|{'to-taste' if to_taste else unit}"
            line = lines.get(key)
            if line is None:
                line = lines[key] = ShoppingLine(
                    key=key,
                    name=ingredient.ingredient_name.strip(),
                    unit=unit,
                    to_taste=to_taste,
                    quantity=0.0,
                )
            share = 0.0 if to_taste else float(ingredient.quantity)
            # The same recipe can list an ingredient twice (sauce and garnish).
            existing = next((n for n in line.needs if n.entry_id == entry.id), None)
            if existing is not None:
                existing.quantity += share
            else:
                line.needs.append(Need(
                    entry_id=entry.id,
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    day=entry.date,
                    quantity=share,
                ))
            line.quantity += share

    if lines:
        _apply_pantry(db, lines)
        _apply_grocery_list(db, lines)
        for line in lines.values():
            _decide(line)

    ordered = sorted(lines.values(), key=lambda line: (line.name.lower(), line.unit))
    return ordered, len(dinners)


def _apply_pantry(db: Session, lines: dict[str, ShoppingLine]) -> None:
    by_identity: dict[str, list[ShoppingLine]] = {}
    for line in lines.values():
        by_identity.setdefault(line.key.split("|", 1)[0], []).append(line)

    stock = db.query(InventoryItem).filter(InventoryItem.quantity > 0).all()
    for item in stock:
        matches = by_identity.get(ingredient_identity(item.name))
        if not matches:
            continue
        unit = normalize_unit(item.unit)
        for line in matches:
            if not line.to_taste and unit == line.unit:
                if not line.pantry_counted:
                    # Stock in the line's own unit is what gets subtracted; it
                    # replaces any other-unit stock noted so far.
                    line.pantry_quantity, line.pantry_unit, line.pantry_counted = 0.0, unit, True
                line.pantry_quantity += float(item.quantity)
            elif not line.pantry_counted:
                # Another unit: shown to the user, never subtracted.
                if line.pantry_quantity is None:
                    line.pantry_quantity, line.pantry_unit = 0.0, unit
                if unit == line.pantry_unit:
                    line.pantry_quantity += float(item.quantity)


def _apply_grocery_list(db: Session, lines: dict[str, ShoppingLine]) -> None:
    # Items imported for these dinners count whether bought yet or not: either
    # way they are taken care of. Other items count only while unbought.
    for item in db.query(GroceryListItem).all():
        sources = _sources(item)
        if sources:
            for source in sources:
                line = lines.get(source.get("line"))
                if line is not None and any(str(n.entry_id) == source.get("entry_id") for n in line.needs):
                    line.listed_quantity += float(source.get("quantity") or 0.0)
                    if line.to_taste:
                        line.listed_otherwise = True
            continue
        if item.purchased:
            continue
        identity = ingredient_identity(item.item_name)
        for line in lines.values():
            if line.key.split("|", 1)[0] == identity:
                line.listed_otherwise = True


def _decide(line: ShoppingLine) -> None:
    """Work out what approving the line adds, and whether it starts checked."""
    if line.to_taste:
        line.add_quantity = 0.0
        # Seasoning you are told to add to taste: offered only when nothing says you have it.
        line.suggested = line.pantry_quantity is None and not line.listed_otherwise
        return

    remaining = line.quantity - line.listed_quantity
    if line.pantry_counted:
        remaining -= line.pantry_quantity or 0.0
    line.add_quantity = round(max(remaining, 0.0), 3)

    if line.add_quantity <= 0 or line.listed_otherwise:
        line.suggested = False
    elif line.pantry_quantity is not None and not line.pantry_counted:
        # The pantry has some, in a unit that cannot be compared: the user decides.
        line.suggested = False
    else:
        line.suggested = True


@dataclass
class AddResult:
    added: int = 0
    # Lines that could not be added, by name.
    skipped: list[str] = field(default_factory=list)


def add_lines_to_grocery_list(
    db: Session, week_start: date, keys: list[str], current_user: User
) -> AddResult:
    """
    Put the chosen lines on the grocery list, one item per line.

    Each item records which dinners it is for and how much each needs, so
    removing a dinner later takes its share off again.
    """
    lines, _ = week_shopping_lines(db, week_start)
    by_key = {line.key: line for line in lines}
    result = AddResult()

    for key in dict.fromkeys(keys):
        line = by_key.get(key)
        if line is None:
            continue
        if line.to_taste:
            # Recorded with the same marker quantity the recipes use.
            quantity = UNPARSEABLE_QUANTITY_SENTINEL
        else:
            quantity = line.add_quantity
            if quantity <= 0:
                continue

        # Dinners share the added amount in proportion to what each needs.
        scale = (quantity / line.quantity) if (line.quantity and not line.to_taste) else 1.0
        sources = [
            {
                "line": line.key,
                "entry_id": str(need.entry_id),
                "recipe_id": str(need.recipe_id),
                "recipe_name": need.recipe_name,
                "date": need.day.isoformat(),
                "quantity": round(need.quantity * scale, 3),
            }
            for need in line.needs
        ]
        only = line.needs[0] if len(line.needs) == 1 else None
        try:
            grocery_service.create_item(
                item_name=line.name,
                quantity=quantity,
                unit=line.unit,
                source="meal_plan",
                current_user=current_user,
                db=db,
                linked_recipe=only.recipe_id if only else None,
                linked_meal_plan_entry=only.entry_id if only else None,
                plan_sources=sources,
            )
            result.added += 1
        except ValidationError as exc:
            logger.warning("week shopping: could not add %r: %s", line.name, exc)
            result.skipped.append(line.name)

    return result


def release_entry(db: Session, entry_id: UUID) -> int:
    """
    Take a dinner's share off the grocery list (the dinner is being removed).

    An unbought item that was only for this dinner is deleted. One that other
    dinners also need shrinks by this dinner's share. Bought items stay and
    lose the link. Returns how many items were deleted. The caller commits.
    """
    removed = 0
    wanted = str(entry_id)
    for item in db.query(GroceryListItem).all():
        sources = _sources(item)
        mine = [s for s in sources if s.get("entry_id") == wanted]
        directly_linked = item.linked_meal_plan_entry == entry_id
        if not mine and not directly_linked:
            continue

        rest = [s for s in sources if s.get("entry_id") != wanted]
        if directly_linked:
            item.linked_meal_plan_entry = None
        if item.purchased:
            item.plan_sources = rest or None
            continue
        if not rest:
            db.delete(item)
            removed += 1
            continue

        item.quantity = round(max(item.quantity - sum(float(s.get("quantity") or 0.0) for s in mine), 0.0), 3)
        item.plan_sources = rest
        if len(rest) == 1:
            item.linked_meal_plan_entry = UUID(rest[0]["entry_id"])
            item.linked_recipe = UUID(rest[0]["recipe_id"])
        else:
            item.linked_recipe = None
    return removed
