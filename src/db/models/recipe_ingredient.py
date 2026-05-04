from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, Integer, ForeignKey, DateTime, func, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    ingredient_name: Mapped[str] = mapped_column(String(255))
    # Normalized lowercase column for efficient case-insensitive matching (issue #477)
    # Automatically maintained via SQLAlchemy event listeners below
    ingredient_name_lower: Mapped[str] = mapped_column(String(255), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    variation_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    variation_diet: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="ingredients")


# SQLAlchemy event listeners to automatically maintain ingredient_name_lower
# This ensures the normalized column stays in sync with ingredient_name changes
@event.listens_for(RecipeIngredient, 'before_insert')
@event.listens_for(RecipeIngredient, 'before_update')
def normalize_ingredient_name(mapper, connection, target):
    """Automatically set ingredient_name_lower from ingredient_name before insert/update.

    Note: This event listener operates on ORM-level operations and will NOT fire
    for bulk operations executed via connection.execute() or session.execute() with
    bulk_insert_mappings(), bulk_update_mappings(), or raw SQL UPDATE statements.
    For bulk operations, ensure ingredient_name_lower is set explicitly or use database triggers.
    """
    if target.ingredient_name is not None:
        target.ingredient_name_lower = target.ingredient_name.lower()
