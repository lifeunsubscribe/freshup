"""Tag service for managing recipe tags and junction table."""

import logging
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.db.models.tag import Tag
from src.db.models.recipe_tag import RecipeTag

logger = logging.getLogger(__name__)


def sync_recipe_tags(recipe_id: UUID, tag_names: list[str], db: Session) -> None:
    """
    Synchronize recipe tags with the junction table.

    This function ensures the recipe_tags junction table matches the provided
    tag names. It handles tag creation if needed and maintains referential
    integrity between recipes and tags.

    IMPORTANT: Call this function whenever recipe.tags JSON is updated to keep
    the junction table in sync for optimal query performance.

    Args:
        recipe_id: Recipe ID to sync tags for
        tag_names: List of tag names (strings) to associate with the recipe
        db: Database session

    Implementation:
        1. Remove existing recipe-tag associations
        2. Get or create Tag records for each tag name
        3. Create new RecipeTag junction records
        4. Commit changes

    Note:
        This function modifies the database but does NOT commit. The caller
        is responsible for committing the transaction.
    """
    # Remove existing recipe-tag associations
    # This ensures we have a clean slate before adding new associations
    db.query(RecipeTag).filter(RecipeTag.recipe_id == recipe_id).delete()

    # Process each tag name
    for tag_name in tag_names:
        if not tag_name or not tag_name.strip():
            # Skip empty or whitespace-only tags
            continue

        # Normalize tag name (lowercase, strip whitespace)
        normalized_tag = tag_name.strip().lower()

        # Get or create Tag record
        tag = db.query(Tag).filter(Tag.name == normalized_tag).first()
        if not tag:
            # Create new tag if it doesn't exist
            tag = Tag(name=normalized_tag)
            db.add(tag)
            try:
                db.flush()  # Flush to get the tag ID without committing
            except IntegrityError:
                # Handle race condition: another transaction created this tag
                # Roll back the tag creation and fetch the existing tag
                db.rollback()
                tag = db.query(Tag).filter(Tag.name == normalized_tag).first()

        # Create recipe-tag association
        recipe_tag = RecipeTag(recipe_id=recipe_id, tag_id=tag.id)
        db.add(recipe_tag)

    logger.debug(f"Synced {len(tag_names)} tags for recipe {recipe_id}")


def get_or_create_tags(tag_names: list[str], db: Session) -> list[Tag]:
    """
    Get existing tags or create new ones for the given tag names.

    Args:
        tag_names: List of tag names (strings)
        db: Database session

    Returns:
        List of Tag objects corresponding to the tag names

    Note:
        This function modifies the database but does NOT commit. The caller
        is responsible for committing the transaction.
    """
    tags = []
    for tag_name in tag_names:
        if not tag_name or not tag_name.strip():
            continue

        normalized_tag = tag_name.strip().lower()

        # Get or create Tag record
        tag = db.query(Tag).filter(Tag.name == normalized_tag).first()
        if not tag:
            tag = Tag(name=normalized_tag)
            db.add(tag)
            try:
                db.flush()
            except IntegrityError:
                # Handle race condition
                db.rollback()
                tag = db.query(Tag).filter(Tag.name == normalized_tag).first()

        tags.append(tag)

    return tags
