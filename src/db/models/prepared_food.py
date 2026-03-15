from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class PreparedFoodType(str, PyEnum):
    complete_meal = "complete_meal"
    batch_portion = "batch_portion"
    component_ingredient = "component_ingredient"


class PreparedFood(Base):
    __tablename__ = "prepared_foods"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    source_recipe: Mapped[Optional[UUID]] = mapped_column(ForeignKey("recipes.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(50))
    servings_remaining: Mapped[float] = mapped_column(Float, default=0.0)
    storage_location: Mapped[str] = mapped_column(String(50))
    date_prepared: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    estimated_expiration: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    shareability: Mapped[str] = mapped_column(String(50), default="shared")
    prepared_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    source_recipe_rel: Mapped[Optional["Recipe"]] = relationship(back_populates="prepared_foods")
    prepared_by_user: Mapped["User"] = relationship(back_populates="prepared_foods")
