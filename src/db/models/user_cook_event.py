from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserCookEvent(Base):
    """
    Records each time a user cooks a recipe.

    There is no unique constraint — a user can cook the same recipe many times
    and each cook is an independent row. The feed signal uses cook count vs.
    view count to surface viewed-but-not-cooked recipes.
    """
    __tablename__ = "user_cook_events"
    __table_args__ = (
        Index("ix_user_cook_events_user_id", "user_id"),
        Index("ix_user_cook_events_recipe_id", "recipe_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    cooked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Links the cook to a planned meal when it was scheduled via the meal plan
    meal_plan_entry_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("meal_plan_entries.id"), nullable=True
    )
    # Optional free-text notes the user can attach to a cook event
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="cook_events")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="cook_events")
    meal_plan_entry_rel: Mapped[Optional["MealPlanEntry"]] = relationship()
