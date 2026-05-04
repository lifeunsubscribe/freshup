"""
Feed service - Personalized recipe recommendations.

Provides "Make This Right Now" (inventory-aware) and "On Repeat" (behavioral signals)
query logic for the home feed.

Performance Considerations:
    SQLite JSON columns (Recipe.tags) don't support efficient indexing. Tag-based
    queries require full table scans with in-memory filtering. Current optimizations:

    1. Database indexes on frequently-filtered columns (is_persisted, times_cooked,
       source_type, cook_time_minutes, created_at) - see migration
       23d3423662b9_add_recipe_performance_indexes.py

    2. Query optimization: Pre-order results by times_cooked DESC before filtering,
       allowing early termination when enough matches are found

    3. Selective column fetching: Only load needed columns (e.g., Recipe.id, Recipe.tags)
       instead of full ORM objects where possible

    Future Enhancement:
        Migrating to PostgreSQL would enable JSONB indexing with GIN indexes for
        O(1) tag lookups. Alternatively, a normalized recipe_tags junction table
        would allow proper indexing within SQLite at the cost of schema complexity.
"""

import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.inventory_item import InventoryItem
from src.db.models.user_recipe import UserRecipeRating

logger = logging.getLogger(__name__)


def get_make_now_recipes(user_id: UUID, db: Session, limit: int = 10) -> list[Recipe]:
    """
    Get recipes the user can make right now based on inventory availability.

    Returns persisted recipes where the user has 100% of required (non-optional)
    ingredients available. Results are sorted by freshness priority (ingredients
    expiring soonest) then by times_cooked descending.

    Args:
        user_id: User ID to check inventory for
        db: Database session
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects with 100% ingredient availability

    Note:
        - Only checks required ingredients (is_optional=False)
        - Uses case-insensitive ingredient name matching
        - Freshness priority based on earliest expiration_date in recipe's ingredients
        - TODO: Add fuzzy matching for ingredient names
        - TODO: Add unit conversion between recipe and inventory units
    """
    # Subquery: For each recipe, count total required ingredients
    total_ingredients_subq = (
        db.query(
            RecipeIngredient.recipe_id,
            func.count(distinct(RecipeIngredient.id)).label("total_required")
        )
        .filter(RecipeIngredient.is_optional == False)  # noqa: E712
        .group_by(RecipeIngredient.recipe_id)
        .subquery()
    )

    # Subquery: For each recipe, count matched ingredients in user's inventory
    # Match by case-insensitive ingredient name
    matched_ingredients_subq = (
        db.query(
            RecipeIngredient.recipe_id,
            func.count(distinct(RecipeIngredient.id)).label("matched_count")
        )
        .join(
            InventoryItem,
            func.lower(RecipeIngredient.ingredient_name) == func.lower(InventoryItem.name)
        )
        .filter(RecipeIngredient.is_optional == False)  # noqa: E712
        .filter(InventoryItem.added_by == user_id)
        .filter(InventoryItem.quantity > 0)  # Only count items with available quantity
        .group_by(RecipeIngredient.recipe_id)
        .subquery()
    )

    # Subquery: For each recipe, get earliest expiration date of its ingredients
    # This drives freshness priority sorting
    freshness_subq = (
        db.query(
            RecipeIngredient.recipe_id,
            func.min(InventoryItem.expiration_date).label("earliest_expiration")
        )
        .join(
            InventoryItem,
            func.lower(RecipeIngredient.ingredient_name) == func.lower(InventoryItem.name)
        )
        .filter(InventoryItem.added_by == user_id)
        .filter(InventoryItem.expiration_date.isnot(None))
        .group_by(RecipeIngredient.recipe_id)
        .subquery()
    )

    # Main query: Get recipes with 100% ingredient availability
    query = (
        db.query(Recipe)
        .join(total_ingredients_subq, Recipe.id == total_ingredients_subq.c.recipe_id)
        .outerjoin(matched_ingredients_subq, Recipe.id == matched_ingredients_subq.c.recipe_id)
        .outerjoin(freshness_subq, Recipe.id == freshness_subq.c.recipe_id)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .filter(
            # Only recipes with 100% ingredient availability
            # Handle case where matched_count is NULL (0 matches)
            func.coalesce(matched_ingredients_subq.c.matched_count, 0)
            == total_ingredients_subq.c.total_required
        )
        .order_by(
            # Sort by freshness (earliest expiration first), NULL last
            case(
                (freshness_subq.c.earliest_expiration.is_(None), None),
                else_=freshness_subq.c.earliest_expiration
            ).asc().nullslast(),
            # Then by popularity (times cooked)
            Recipe.times_cooked.desc()
        )
        .limit(limit)
    )

    recipes = query.all()
    logger.info(f"Found {len(recipes)} make-now recipes for user {user_id}")
    return recipes


def get_on_repeat_recipes(user_id: UUID, db: Session, limit: int = 15) -> list[Recipe]:
    """
    Get recipes the user repeatedly engages with based on behavioral signals.

    Weighted scoring from:
    - Viewed-not-cooked (0.25) - TODO: requires UserRecipeView model from #5
    - High-frequency-cooked (0.30) - TODO: requires UserCookEvent model from #4
    - Recently-rated (0.25) - IMPLEMENTED: uses UserRecipeRating.updated_at
    - Genre-affinity (0.20) - TODO: requires cook history analysis

    Args:
        user_id: User ID to get recommendations for
        db: Database session
        limit: Maximum number of recipes to return (default 15)

    Returns:
        List of Recipe objects sorted by engagement score

    Note:
        Current implementation only uses recently-rated signal (0.25 weight).
        Full weighted scoring will be available after dependencies #4 and #5 complete.
        Returns empty list if no rating data exists (cold start case).
    """
    # TODO (#4): Add viewed-not-cooked signal (0.25)
    # Requires UserRecipeView model to track views and correlate with cook events

    # TODO (#4): Add high-frequency-cooked signal (0.30)
    # Requires UserCookEvent model to calculate cook frequency

    # TODO (#4, #5): Add genre-affinity signal (0.20)
    # Requires cook history to analyze preferred tags/genres

    # Current implementation: Recently-rated signal only
    # Uses updated_at from UserRecipeRating as recency indicator
    # Orders by most recent rating first
    query = (
        db.query(Recipe)
        .join(UserRecipeRating, Recipe.id == UserRecipeRating.recipe_id)
        .filter(UserRecipeRating.user_id == user_id)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .order_by(UserRecipeRating.updated_at.desc())
        .limit(limit)
    )

    recipes = query.all()
    logger.info(
        f"Found {len(recipes)} on-repeat recipes for user {user_id} "
        f"(recently-rated signal only, awaiting #4 and #5 for full scoring)"
    )
    return recipes


def get_user_tag_patterns(user_id: UUID, db: Session, min_saves: int = 3) -> list[tuple[str, int]]:
    """
    Detect user's tag patterns based on saved recipe count.

    Analyzes recipes the user has rated/saved to find their preferred tags.
    Returns tags that appear in at least `min_saves` recipes.

    Args:
        user_id: User ID to analyze patterns for
        db: Database session
        min_saves: Minimum number of saved recipes required for a tag to qualify (default 3)

    Returns:
        List of (tag, count) tuples sorted by count descending

    Performance Notes:
        - Only fetches Recipe.id and Recipe.tags columns (not full recipe objects)
        - Reduces memory footprint when user has many saved recipes
        - Still requires in-memory counting due to SQLite JSON limitations
    """
    # Optimization: Only fetch id and tags columns, not full recipe objects
    # This reduces memory usage significantly for users with many saved recipes
    saved_recipes = (
        db.query(Recipe.id, Recipe.tags)
        .join(UserRecipeRating, Recipe.id == UserRecipeRating.recipe_id)
        .filter(UserRecipeRating.user_id == user_id)
        .all()
    )

    # Count tag occurrences across saved recipes
    # This finds which tags appear most frequently in user's saved recipes
    tag_counts = {}
    for recipe_id, tags in saved_recipes:
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Filter by minimum threshold and sort by count descending
    # Only tags with >= min_saves occurrences qualify as patterns
    patterns = [(tag, count) for tag, count in tag_counts.items() if count >= min_saves]
    patterns.sort(key=lambda x: x[1], reverse=True)

    logger.info(
        f"Found {len(patterns)} tag patterns for user {user_id} "
        f"(min_saves={min_saves}, scanned {len(saved_recipes)} saved recipes)"
    )
    return patterns


def get_user_source_patterns(user_id: UUID, db: Session, min_saves: int = 5) -> list[tuple[str, int]]:
    """
    Detect user's source type patterns based on saved recipe count.

    Analyzes recipes the user has rated/saved to find their preferred sources.
    Returns source types that appear in at least `min_saves` recipes.

    Args:
        user_id: User ID to analyze patterns for
        db: Database session
        min_saves: Minimum number of saved recipes required for a source to qualify (default 5)

    Returns:
        List of (source_type, count) tuples sorted by count descending
    """
    # Count source types in user's saved recipes
    source_counts = (
        db.query(Recipe.source_type, func.count(Recipe.id).label("count"))
        .join(UserRecipeRating, Recipe.id == UserRecipeRating.recipe_id)
        .filter(UserRecipeRating.user_id == user_id)
        .group_by(Recipe.source_type)
        .having(func.count(Recipe.id) >= min_saves)
        .order_by(func.count(Recipe.id).desc())
        .all()
    )

    patterns = [(source_type, count) for source_type, count in source_counts]
    logger.info(f"Found {len(patterns)} source patterns for user {user_id} (min_saves={min_saves})")
    return patterns


def _get_saved_recipe_ids(user_id: UUID, db: Session) -> set[UUID]:
    """
    Get IDs of all recipes the user has saved/rated.

    Args:
        user_id: User ID to get saved recipes for
        db: Database session

    Returns:
        Set of recipe IDs the user has rated/saved
    """
    return {
        rating.recipe_id
        for rating in db.query(UserRecipeRating.recipe_id)
        .filter(UserRecipeRating.user_id == user_id)
        .all()
    }


def get_recipes_by_tag(user_id: UUID, db: Session, tag: str, limit: int = 10) -> list[Recipe]:
    """
    Get recipes matching a specific tag, mixing saved and non-saved recipes.

    Returns persisted recipes with the given tag, prioritizing:
    1. Saved recipes (user has rated/saved them)
    2. Non-saved recipes ordered by times_cooked descending

    Args:
        user_id: User ID for determining saved status
        db: Database session
        tag: Tag to filter recipes by
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects with the specified tag

    Performance Notes:
        - SQLite JSON columns don't support efficient indexing
        - We pre-order by times_cooked and use early termination to reduce memory
        - PostgreSQL migration would enable JSONB indexing for O(1) tag lookups
        - Current approach is O(n) but optimized to reduce n via ordering + limits
    """
    # Optimization: Pre-order by times_cooked DESC to get most popular recipes first
    # This allows early termination once we have enough matching results
    # Index ix_recipes_persisted_times_cooked makes this query efficient
    all_recipes = (
        db.query(Recipe)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .order_by(Recipe.times_cooked.desc())
        .all()
    )

    # Get IDs of recipes user has saved (query once, reuse below)
    saved_recipe_ids = _get_saved_recipe_ids(user_id, db)

    # Separate matching recipes into saved and non-saved buckets
    # Early termination: stop when we have enough in each bucket
    saved_matches = []
    non_saved_matches = []

    for recipe in all_recipes:
        if tag in recipe.tags:
            if recipe.id in saved_recipe_ids:
                if len(saved_matches) < limit:
                    saved_matches.append(recipe)
            else:
                if len(non_saved_matches) < limit:
                    non_saved_matches.append(recipe)

            # Early exit: if we have enough in both buckets, stop scanning
            if len(saved_matches) >= limit and len(non_saved_matches) >= limit:
                break

    # Combine: saved first, then non-saved, up to limit
    # Saved recipes already ordered by times_cooked (via query ORDER BY)
    # Non-saved recipes also ordered by times_cooked
    recipes = (saved_matches + non_saved_matches)[:limit]

    logger.info(
        f"Found {len(recipes)} recipes for tag '{tag}' for user {user_id} "
        f"({len(saved_matches)} saved, {len(non_saved_matches)} non-saved scanned)"
    )
    return recipes


def get_recipes_by_source(user_id: UUID, db: Session, source_type: str, limit: int = 10) -> list[Recipe]:
    """
    Get recipes from a specific source type, mixing saved and non-saved recipes.

    Returns persisted recipes from the given source, prioritizing:
    1. Saved recipes (user has rated/saved them)
    2. Non-saved recipes ordered by times_cooked descending

    Args:
        user_id: User ID for determining saved status
        db: Database session
        source_type: Source type to filter recipes by
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects from the specified source
    """
    # Get recipes from this source
    matching_recipes = (
        db.query(Recipe)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .filter(Recipe.source_type == source_type)
        .all()
    )

    # Get IDs of recipes user has saved
    saved_recipe_ids = _get_saved_recipe_ids(user_id, db)

    # Sort: saved recipes first, then by times_cooked
    def sort_key(recipe):
        is_saved = 1 if recipe.id in saved_recipe_ids else 0
        return (-is_saved, -recipe.times_cooked)

    matching_recipes.sort(key=sort_key)
    recipes = matching_recipes[:limit]

    logger.info(f"Found {len(recipes)} recipes from source '{source_type}' for user {user_id}")
    return recipes


def get_popular_recipes(db: Session, limit: int = 10) -> list[Recipe]:
    """
    Get popular recipes sorted by times cooked.

    Fallback row for cold start or variety.

    Args:
        db: Database session
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects sorted by times_cooked descending
    """
    query = (
        db.query(Recipe)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .filter(Recipe.times_cooked > 0)
        .order_by(Recipe.times_cooked.desc())
        .limit(limit)
    )

    recipes = query.all()
    logger.info(f"Found {len(recipes)} popular recipes")
    return recipes


def get_quick_recipes(db: Session, limit: int = 10) -> list[Recipe]:
    """
    Get quick meal recipes (cook time <= 30 minutes).

    Fallback row for cold start or variety.

    Args:
        db: Database session
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects with cook_time_minutes <= 30
    """
    query = (
        db.query(Recipe)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .filter(Recipe.cook_time_minutes.isnot(None))
        .filter(Recipe.cook_time_minutes <= 30)
        .order_by(Recipe.times_cooked.desc())
        .limit(limit)
    )

    recipes = query.all()
    logger.info(f"Found {len(recipes)} quick recipes")
    return recipes


def get_new_recipes(db: Session, limit: int = 10) -> list[Recipe]:
    """
    Get recently created recipes.

    Fallback row for cold start or variety.

    Args:
        db: Database session
        limit: Maximum number of recipes to return (default 10)

    Returns:
        List of Recipe objects sorted by created_at descending
    """
    query = (
        db.query(Recipe)
        .filter(Recipe.is_persisted == True)  # noqa: E712
        .order_by(Recipe.created_at.desc())
        .limit(limit)
    )

    recipes = query.all()
    logger.info(f"Found {len(recipes)} new recipes")
    return recipes


def build_personalized_rows(user_id: UUID, db: Session, max_rows: int = 4) -> list[dict]:
    """
    Build personalized feed rows based on user's tag patterns.

    Detects tags user frequently saves (>=3 saves) and creates rows with
    recipes matching those tags. Each row includes both saved and non-saved
    recipes to encourage discovery.

    Args:
        user_id: User ID to build personalized rows for
        db: Database session
        max_rows: Maximum number of rows to generate (default 4)

    Returns:
        List of row dicts with {title, recipes, browse_url}
    """
    tag_patterns = get_user_tag_patterns(user_id, db, min_saves=3)
    rows = []

    for tag, _count in tag_patterns[:max_rows]:
        recipes = get_recipes_by_tag(user_id, db, tag, limit=10)
        if recipes:
            # Format tag for display: capitalize first letter, add period
            display_tag = tag.capitalize() if tag else tag
            rows.append({
                "title": f"{display_tag}.",
                "recipes": recipes,
                "browse_url": f"/feed/browse?tag={tag}"
            })

    logger.info(f"Built {len(rows)} personalized rows for user {user_id}")
    return rows


def build_source_rows(user_id: UUID, db: Session, max_rows: int = 2) -> list[dict]:
    """
    Build source-specific feed rows based on user's source patterns.

    Detects sources user frequently saves from (>=5 saves) and creates rows
    with recipes from those sources. Each row includes both saved and non-saved
    recipes to encourage discovery.

    Args:
        user_id: User ID to build source rows for
        db: Database session
        max_rows: Maximum number of rows to generate (default 2)

    Returns:
        List of row dicts with {title, recipes, browse_url}
    """
    source_patterns = get_user_source_patterns(user_id, db, min_saves=5)
    rows = []

    # Map source_type to display name
    source_display_names = {
        "hellofresh_card": "HelloFresh",
        "hellofresh_web": "HelloFresh",
        "kitchen_sanctuary": "Kitchen Sanctuary",
        "url_import": "URL imports",
        "manual": "Manual entries",
        "photo_upload": "Photo uploads",
        "ad_hoc": "Ad-hoc recipes"
    }

    for source_type, _count in source_patterns[:max_rows]:
        recipes = get_recipes_by_source(user_id, db, source_type, limit=10)
        if recipes:
            display_name = source_display_names.get(source_type, source_type.replace("_", " ").title())
            rows.append({
                "title": f"From {display_name}.",
                "recipes": recipes,
                "browse_url": f"/feed/browse?source={source_type}"
            })

    logger.info(f"Built {len(rows)} source rows for user {user_id}")
    return rows


def build_fallback_rows(db: Session) -> list[dict]:
    """
    Build fallback feed rows for cold start or variety.

    Returns three standard rows:
    - Popular recipes (by times_cooked)
    - Quick meals (cook_time <= 30 minutes)
    - New recipes (recently created)

    Args:
        db: Database session

    Returns:
        List of row dicts with {title, recipes, browse_url}
    """
    rows = []

    # Popular recipes
    popular_recipes = get_popular_recipes(db, limit=10)
    if popular_recipes:
        rows.append({
            "title": "Popular recipes.",
            "recipes": popular_recipes,
            "browse_url": "/feed/browse?sort=popular"
        })

    # Quick meals
    quick_recipes = get_quick_recipes(db, limit=10)
    if quick_recipes:
        rows.append({
            "title": "Quick meals.",
            "recipes": quick_recipes,
            "browse_url": "/feed/browse?quick=true"
        })

    # New recipes
    new_recipes = get_new_recipes(db, limit=10)
    if new_recipes:
        rows.append({
            "title": "New recipes.",
            "recipes": new_recipes,
            "browse_url": "/feed/browse?sort=newest"
        })

    logger.info(f"Built {len(rows)} fallback rows")
    return rows
