from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserRecipeView(Base):
    """
    Records each time a user views a recipe.

    No unique constraint — repeat views are each recorded. The feed signal
    compares view count to cook count to surface viewed-but-not-cooked recipes.

    Allowed values for source: 'browse', 'detail', 'search', 'feed', 'menu'.

    FK delete behaviour:
    - user_id CASCADE: a removed household member's view history goes with them.
    - recipe_id CASCADE: Load-bearing. Viewing does not trigger persistence, so
      a viewed browse-cache recipe is still pruned by
      cleanup_service.prune_unpersisted_recipes after BROWSE_CACHE_TTL_DAYS.
      Without cascade those view rows would orphan or the delete would fail.
    """
    __tablename__ = "user_recipe_views"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipe_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True
    )
    viewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="recipe_views")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="views")
