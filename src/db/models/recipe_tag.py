"""RecipeTag junction table for many-to-many recipe-tag relationships."""

from uuid import UUID
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class RecipeTag(Base):
    """
    Junction table for many-to-many relationship between recipes and tags.

    This table enables efficient tag-based recipe queries by providing indexed
    lookups on both recipe_id and tag_id. Replaces the inefficient JSON-based
    tag filtering that required full table scans.

    Composite primary key ensures each recipe-tag pair is unique.
    """
    __tablename__ = "recipe_tags"

    recipe_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        index=True  # Index for efficient tag-based queries
    )

    # Relationships
    recipe_rel: Mapped["Recipe"] = relationship("Recipe", back_populates="tag_associations")
    tag_rel: Mapped["Tag"] = relationship("Tag", back_populates="recipe_associations")
