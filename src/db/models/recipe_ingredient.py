from __future__ import annotations

from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    ingredient_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    variation_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    variation_diet: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="ingredients")
