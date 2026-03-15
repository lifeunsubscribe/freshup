from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class GrocerySource(str, PyEnum):
    meal_plan_auto = "meal_plan_auto"
    staple_threshold = "staple_threshold"
    manual = "manual"
    consumption_pattern = "consumption_pattern"


class GroceryListItem(Base):
    __tablename__ = "grocery_list_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50))
    linked_recipe: Mapped[Optional[UUID]] = mapped_column(ForeignKey("recipes.id"), nullable=True)
    linked_meal_plan_entry: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("meal_plan_entries.id"), nullable=True
    )
    added_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    target_store: Mapped[Optional[UUID]] = mapped_column(ForeignKey("stores.id"), nullable=True)
    purchased: Mapped[bool] = mapped_column(Boolean, default=False)
    purchased_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    purchased_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    added_by_user: Mapped["User"] = relationship(
        back_populates="grocery_list_items", foreign_keys=[added_by]
    )
    purchased_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[purchased_by])
    target_store_rel: Mapped[Optional["Store"]] = relationship(back_populates="grocery_list_items")
    linked_recipe_rel: Mapped[Optional["Recipe"]] = relationship(foreign_keys=[linked_recipe])
    linked_meal_plan_entry_rel: Mapped[Optional["MealPlanEntry"]] = relationship(
        foreign_keys=[linked_meal_plan_entry]
    )
