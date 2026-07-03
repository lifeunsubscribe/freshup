"""Tag model for recipe categorization."""

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Tag(Base):
    """
    Tag model for categorizing recipes.

    Tags are normalized strings used for recipe categorization (e.g., "vegetarian",
    "quick", "dessert"). This table supports efficient tag-based queries through
    indexed lookups.

    The many-to-many relationship with Recipe is managed through the recipe_tags
    junction table.
    """
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Relationships
    recipe_associations: Mapped[list["RecipeTag"]] = relationship(
        "RecipeTag",
        back_populates="tag_rel",
        cascade="all, delete-orphan"
    )
