from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Index, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class GrocerySource(str, PyEnum):
    meal_plan_auto = "meal_plan_auto"
    staple_threshold = "staple_threshold"
    manual = "manual"
    consumption_pattern = "consumption_pattern"


class GroceryListItem(Base):
    __tablename__ = "grocery_list_items"
    __table_args__ = (
        # purchased first (the filter), then created_at (the ordering) — matches
        # the list query. Declared here so create_all and the migrations agree.
        Index('ix_grocery_list_items_purchased_created_at', 'purchased', 'created_at'),
    )

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
    # For an item imported from a week's shopping list: the dinners it is for,
    # [{"line", "entry_id", "recipe_id", "recipe_name", "date", "quantity"}].
    # One item can serve several dinners; removing a dinner takes its share off.
    plan_sources: Mapped[Optional[list]] = mapped_column(JSON(none_as_null=True), nullable=True)
    target_store: Mapped[Optional[UUID]] = mapped_column(ForeignKey("stores.id"), nullable=True)
    purchased: Mapped[bool] = mapped_column(Boolean, default=False)
    purchased_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    purchased_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

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

    def _source_dicts(self) -> list[dict]:
        return [s for s in (self.plan_sources or []) if isinstance(s, dict)]

    @property
    def recipes(self) -> list[dict]:
        """Every recipe this item is for, as {"id", "name"}, in the order the dinners are planned."""
        sources = sorted(self._source_dicts(), key=lambda s: s.get("date") or "")
        seen: dict[str, dict] = {}
        for s in sources:
            if s.get("recipe_id") and s["recipe_id"] not in seen:
                seen[s["recipe_id"]] = {"id": s["recipe_id"], "name": s.get("recipe_name") or ""}
        if not seen and self.linked_recipe_rel is not None:
            return [{"id": str(self.linked_recipe_rel.id), "name": self.linked_recipe_rel.name}]
        return list(seen.values())

    @property
    def recipe_names(self) -> list[str]:
        """Every recipe this item is for, in the order the dinners are planned."""
        sources = sorted(self._source_dicts(), key=lambda s: s.get("date") or "")
        names = list(dict.fromkeys(s["recipe_name"] for s in sources if s.get("recipe_name")))
        if not names and self.linked_recipe_rel is not None:
            names = [self.linked_recipe_rel.name]
        return names

    @property
    def recipe_name(self) -> Optional[str]:
        """Name of the one recipe this item is for; None when there is none or several."""
        names = self.recipe_names
        return names[0] if len(names) == 1 else None

    @property
    def plan_date(self):
        """Day of the one planned meal this item is for, if any."""
        entry = self.linked_meal_plan_entry_rel
        if entry is not None:
            return entry.date
        sources = self._source_dicts()
        if len(sources) == 1 and sources[0].get("date"):
            from datetime import date as _date
            return _date.fromisoformat(sources[0]["date"])
        return None
