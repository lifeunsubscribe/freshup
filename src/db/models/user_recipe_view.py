from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserRecipeView(Base):
    """
    Records each time a user views a recipe.

    There is no unique constraint — repeat views are each recorded as separate
    rows. The feed signal compares view count to cook count to surface recipes
    the user has looked at but never cooked.
    """
    __tablename__ = "user_recipe_views"
    __table_args__ = (
        Index("ix_user_recipe_views_user_id", "user_id"),
        Index("ix_user_recipe_views_recipe_id", "recipe_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    viewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Tracks how the user arrived at this recipe; one of:
    # browse, detail, search, feed, menu
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="recipe_views")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="views")
