from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserCookEvent(Base):
    """
    Records each time a user cooks a recipe.

    No unique constraint — a user can cook the same recipe many times and each
    occurrence is a separate row. Linked optionally to the meal plan entry that
    prompted the cook via meal_plan_entry_id.

    FK delete behaviour:
    - user_id CASCADE: a removed household member's cook history goes with them.
    - recipe_id CASCADE: cook events for a deleted recipe become orphans.
    - meal_plan_entry_id SET NULL: deleting a planned meal does not un-cook the
      meal — keep the event, drop the link.
    """
    __tablename__ = "user_cook_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipe_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), index=True
    )
    cooked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    meal_plan_entry_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("meal_plan_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="cook_events")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="cook_events")
    meal_plan_entry_rel: Mapped[Optional["MealPlanEntry"]] = relationship()
