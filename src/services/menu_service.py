"""
Menu service - CRUD operations and auto-generation logic for user menus.

Provides manual menu management and auto-generated menu creation from behavioral patterns.
"""

import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.db.models.menu import Menu, MenuRecipe
from src.db.models.recipe import Recipe
from src.db.models.user_recipe import UserRecipeRelation
from src.services.feed_service import get_user_tag_patterns
from src.schemas.menu import FilterRules

logger = logging.getLogger(__name__)


def get_user_menus(user_id: UUID, db: Session) -> list[Menu]:
    """
    Get all menus for a user, ordered by sort_order.

    Args:
        user_id: User ID to get menus for
        db: Database session

    Returns:
        List of Menu objects ordered by sort_order
    """
    menus = (
        db.query(Menu)
        .filter(Menu.user_id == user_id)
        .order_by(Menu.sort_order.asc(), Menu.created_at.desc())
        .all()
    )
    logger.info(f"Retrieved {len(menus)} menus for user {user_id}")
    return menus


def get_menu_by_id(menu_id: UUID, user_id: UUID, db: Session) -> Menu | None:
    """
    Get a specific menu by ID, ensuring it belongs to the user.

    Args:
        menu_id: Menu ID to retrieve
        user_id: User ID for ownership verification
        db: Database session

    Returns:
        Menu object if found and owned by user, None otherwise
    """
    menu = (
        db.query(Menu)
        .filter(Menu.id == menu_id, Menu.user_id == user_id)
        .first()
    )
    return menu


def create_menu(
    user_id: UUID,
    name: str,
    db: Session,
    description: str | None = None,
    filter_rules: dict | None = None,
    is_auto_generated: bool = False,
    cover_image: str | None = None,
    sort_order: int = 0,
) -> Menu:
    """
    Create a new menu for a user.

    Args:
        user_id: User ID who owns the menu
        name: Menu name
        db: Database session
        description: Optional menu description
        filter_rules: Optional filter rules for auto-population
        is_auto_generated: Whether this menu was auto-generated
        cover_image: Optional cover image URL
        sort_order: Sort order for menu display

    Returns:
        Created Menu object

    Raises:
        IntegrityError: If database constraint is violated
    """
    menu = Menu(
        user_id=user_id,
        name=name,
        description=description,
        filter_rules=filter_rules,
        is_auto_generated=is_auto_generated,
        cover_image=cover_image,
        sort_order=sort_order,
    )

    db.add(menu)
    db.commit()
    db.refresh(menu)

    logger.info(f"Created menu {menu.id} for user {user_id} (auto_generated={is_auto_generated})")
    return menu


def update_menu(
    menu: Menu,
    db: Session,
    name: str | None = None,
    description: str | None = None,
    filter_rules: dict | None = None,
    sort_order: int | None = None,
) -> Menu:
    """
    Update an existing menu.

    Args:
        menu: Menu object to update
        db: Database session
        name: Optional new name
        description: Optional new description
        filter_rules: Optional new filter rules
        sort_order: Optional new sort order

    Returns:
        Updated Menu object
    """
    if name is not None:
        menu.name = name
    if description is not None:
        menu.description = description
    if filter_rules is not None:
        menu.filter_rules = filter_rules
    if sort_order is not None:
        menu.sort_order = sort_order

    db.commit()
    db.refresh(menu)

    logger.info(f"Updated menu {menu.id}")
    return menu


def delete_menu(menu: Menu, db: Session) -> None:
    """
    Delete a menu and all its MenuRecipe entries (cascade).

    Args:
        menu: Menu object to delete
        db: Database session
    """
    menu_id = menu.id
    db.delete(menu)
    db.commit()
    logger.info(f"Deleted menu {menu_id}")


def get_menu_recipes(menu_id: UUID, db: Session, offset: int = 0, limit: int = 50) -> tuple[list[Recipe], int]:
    """
    Get recipes in a menu with pagination.

    Args:
        menu_id: Menu ID to get recipes for
        db: Database session
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        Tuple of (list of Recipe objects, total count)
    """
    # Get total count
    total = (
        db.query(MenuRecipe)
        .filter(MenuRecipe.menu_id == menu_id)
        .filter(MenuRecipe.manually_removed == False)  # noqa: E712
        .count()
    )

    # Get paginated recipes ordered by sort_order
    menu_recipes = (
        db.query(MenuRecipe)
        .filter(MenuRecipe.menu_id == menu_id)
        .filter(MenuRecipe.manually_removed == False)  # noqa: E712
        .order_by(MenuRecipe.sort_order.asc(), MenuRecipe.added_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    recipe_ids = [mr.recipe_id for mr in menu_recipes]
    recipes = (
        db.query(Recipe)
        .filter(Recipe.id.in_(recipe_ids))
        .all()
    )

    # Maintain sort order from menu_recipes
    recipe_map = {r.id: r for r in recipes}
    sorted_recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]

    return sorted_recipes, total


def add_recipe_to_menu(
    menu: Menu,
    recipe_id: UUID,
    db: Session,
    sort_order: int = 0,
) -> MenuRecipe:
    """
    Add a recipe to a menu.

    If the recipe doesn't match the menu's filter rules, sets manually_added=True.
    If a MenuRecipe entry exists with manually_removed=True, updates it to manually_removed=False.

    Args:
        menu: Menu object to add recipe to
        recipe_id: Recipe ID to add
        db: Database session
        sort_order: Sort order for the recipe in the menu

    Returns:
        MenuRecipe object

    Raises:
        IntegrityError: If unique constraint is violated (duplicate menu_id + recipe_id)
    """
    # Check if MenuRecipe entry already exists
    existing = (
        db.query(MenuRecipe)
        .filter(MenuRecipe.menu_id == menu.id, MenuRecipe.recipe_id == recipe_id)
        .first()
    )

    if existing:
        # If it was manually removed, restore it
        if existing.manually_removed:
            existing.manually_removed = False
            existing.added_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            logger.info(f"Restored recipe {recipe_id} to menu {menu.id}")
            return existing
        # Otherwise it's a duplicate (should be caught by unique constraint)
        raise IntegrityError("Recipe already in menu", None, None)

    # Get the recipe and check if it matches filter rules
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise ValueError(f"Recipe {recipe_id} not found")

    matches_filter = False
    if menu.filter_rules:
        matches_filter = evaluate_filter_rules(recipe, menu.filter_rules, menu.user_id, db)

    # Create MenuRecipe entry
    menu_recipe = MenuRecipe(
        menu_id=menu.id,
        recipe_id=recipe_id,
        sort_order=sort_order,
        manually_added=not matches_filter,  # True if doesn't match filter
        manually_removed=False,
    )

    db.add(menu_recipe)
    db.commit()
    db.refresh(menu_recipe)

    logger.info(f"Added recipe {recipe_id} to menu {menu.id} (manually_added={menu_recipe.manually_added})")
    return menu_recipe


def remove_recipe_from_menu(menu: Menu, recipe_id: UUID, db: Session) -> None:
    """
    Remove a recipe from a menu.

    If the recipe matches the menu's filter rules, sets manually_removed=True instead of deleting.
    Otherwise, deletes the MenuRecipe entry.

    Args:
        menu: Menu object to remove recipe from
        recipe_id: Recipe ID to remove
        db: Database session
    """
    menu_recipe = (
        db.query(MenuRecipe)
        .filter(MenuRecipe.menu_id == menu.id, MenuRecipe.recipe_id == recipe_id)
        .first()
    )

    if not menu_recipe:
        raise ValueError(f"Recipe {recipe_id} not in menu {menu.id}")

    # Get the recipe and check if it matches filter rules
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    matches_filter = False
    if recipe and menu.filter_rules:
        matches_filter = evaluate_filter_rules(recipe, menu.filter_rules, menu.user_id, db)

    if matches_filter:
        # Set manually_removed flag instead of deleting
        menu_recipe.manually_removed = True
        db.commit()
        logger.info(f"Marked recipe {recipe_id} as manually removed from menu {menu.id}")
    else:
        # Delete the entry
        db.delete(menu_recipe)
        db.commit()
        logger.info(f"Removed recipe {recipe_id} from menu {menu.id}")


def evaluate_filter_rules(recipe: Recipe, filter_rules: dict, user_id: UUID, db: Session) -> bool:
    """
    Evaluate if a recipe matches the given filter rules.

    Supports:
    - tags: contains, not_contains
    - source_type: eq, in
    - cook_time_minutes: <=, >=, eq

    Match logic:
    - "all": All rules must match (AND)
    - "any": At least one rule must match (OR)

    Args:
        recipe: Recipe object to evaluate
        filter_rules: Filter rules dict with match_logic and rules
        user_id: User ID (for checking if recipe is saved)
        db: Database session

    Returns:
        True if recipe matches filter rules, False otherwise
    """
    match_logic = filter_rules.get("match_logic", "all")
    rules = filter_rules.get("rules", [])

    if not rules:
        return True  # No rules means everything matches

    results = []

    for rule in rules:
        field = rule.get("field")
        operator = rule.get("operator")
        value = rule.get("value")

        result = _evaluate_single_rule(recipe, field, operator, value)
        results.append(result)

    # Apply match logic
    if match_logic == "all":
        return all(results)  # AND logic
    elif match_logic == "any":
        return any(results)  # OR logic
    else:
        logger.warning(f"Unknown match_logic '{match_logic}', defaulting to 'all'")
        return all(results)


def _evaluate_single_rule(recipe: Recipe, field: str, operator: str, value: any) -> bool:
    """
    Evaluate a single filter rule against a recipe.

    Args:
        recipe: Recipe object to evaluate
        field: Field name (tags, source_type, cook_time_minutes)
        operator: Operator (contains, not_contains, eq, in, <=, >=)
        value: Value to compare against

    Returns:
        True if rule matches, False otherwise
    """
    if field == "tags":
        recipe_tags = recipe.tags or []
        if operator == "contains":
            return value in recipe_tags
        elif operator == "not_contains":
            return value not in recipe_tags
        else:
            logger.warning(f"Unsupported operator '{operator}' for field 'tags'")
            return False

    elif field == "source_type":
        recipe_source = recipe.source_type
        if operator == "eq":
            return recipe_source == value
        elif operator == "in":
            return recipe_source in value
        else:
            logger.warning(f"Unsupported operator '{operator}' for field 'source_type'")
            return False

    elif field == "cook_time_minutes":
        recipe_cook_time = recipe.cook_time_minutes
        if recipe_cook_time is None:
            return False  # Can't match if cook time is not set

        if operator == "<=":
            return recipe_cook_time <= value
        elif operator == ">=":
            return recipe_cook_time >= value
        elif operator == "eq":
            return recipe_cook_time == value
        else:
            logger.warning(f"Unsupported operator '{operator}' for field 'cook_time_minutes'")
            return False

    else:
        logger.warning(f"Unknown field '{field}' in filter rule")
        return False


def generate_menus_from_patterns(
    user_id: UUID,
    db: Session,
    min_saves: int = 3,
    max_menus: int = 4,
) -> list[Menu]:
    """
    Auto-generate menus from user's behavioral patterns.

    Uses tag patterns detected from saved recipes (UserRecipeRelation).
    Creates menus with filter rules and populates them with matching saved recipes.

    Args:
        user_id: User ID to generate menus for
        db: Database session
        min_saves: Minimum number of saves required for pattern detection
        max_menus: Maximum number of menus to generate

    Returns:
        List of generated Menu objects
    """
    # Get user's tag patterns
    tag_patterns = get_user_tag_patterns(user_id, db, min_saves=min_saves)

    if not tag_patterns:
        logger.info(f"No tag patterns found for user {user_id} (min_saves={min_saves})")
        return []

    generated_menus = []

    for tag, count in tag_patterns[:max_menus]:
        # Skip empty tags to prevent creating menus named "."
        if not tag or not tag.strip():
            logger.warning(f"Skipping empty tag pattern for user {user_id}")
            continue

        # Create filter rules for this tag
        filter_rules = {
            "match_logic": "all",
            "rules": [
                {
                    "field": "tags",
                    "operator": "contains",
                    "value": tag
                }
            ]
        }

        # Format tag for display: capitalize first letter, add period
        display_tag = tag.capitalize() if tag else tag
        menu_name = f"{display_tag}."

        # Create auto-generated menu
        menu = create_menu(
            user_id=user_id,
            name=menu_name,
            description=f"Auto-generated from your {tag} saves",
            filter_rules=filter_rules,
            is_auto_generated=True,
            db=db,
        )

        # Populate menu with matching saved recipes
        _populate_menu_from_filter(menu, user_id, db)

        generated_menus.append(menu)

    logger.info(f"Generated {len(generated_menus)} menus for user {user_id}")
    return generated_menus


def _populate_menu_from_filter(menu: Menu, user_id: UUID, db: Session) -> None:
    """
    Populate a menu with recipes matching its filter rules.

    Only includes recipes the user has saved (UserRecipeRelation with is_bookmarked or rating >= 4).
    Respects manual overrides: skips manually_removed, keeps manually_added.

    Args:
        menu: Menu object to populate
        user_id: User ID for filtering saved recipes
        db: Database session
    """
    if not menu.filter_rules:
        logger.warning(f"Menu {menu.id} has no filter rules, skipping population")
        return

    # Get user's saved recipes (bookmarked or liked with rating >= 4)
    saved_relations = (
        db.query(UserRecipeRelation)
        .filter(
            UserRecipeRelation.user_id == user_id,
            (UserRecipeRelation.is_bookmarked == True) |  # noqa: E712
            (UserRecipeRelation.rating >= 4)
        )
        .all()
    )

    saved_recipe_ids = [rel.recipe_id for rel in saved_relations]
    saved_recipes = (
        db.query(Recipe)
        .filter(Recipe.id.in_(saved_recipe_ids))
        .all()
    )

    # Get existing menu recipes (to check for manual overrides)
    existing_menu_recipes = (
        db.query(MenuRecipe)
        .filter(MenuRecipe.menu_id == menu.id)
        .all()
    )

    manually_removed_ids = {
        mr.recipe_id for mr in existing_menu_recipes if mr.manually_removed
    }
    manually_added_ids = {
        mr.recipe_id for mr in existing_menu_recipes if mr.manually_added
    }
    existing_recipe_ids = {mr.recipe_id for mr in existing_menu_recipes}

    # Evaluate filter rules and add matching recipes
    added_count = 0
    for recipe in saved_recipes:
        # Skip if manually removed
        if recipe.id in manually_removed_ids:
            continue

        # Skip if already in menu (including manually added)
        if recipe.id in existing_recipe_ids:
            continue

        # Check if recipe matches filter rules
        if evaluate_filter_rules(recipe, menu.filter_rules, user_id, db):
            menu_recipe = MenuRecipe(
                menu_id=menu.id,
                recipe_id=recipe.id,
                sort_order=0,
                manually_added=False,
                manually_removed=False,
            )
            db.add(menu_recipe)
            added_count += 1

    db.commit()
    logger.info(f"Populated menu {menu.id} with {added_count} recipes")
