from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class SubstitutionContext(str, PyEnum):
    side_dish = "side_dish"
    in_recipe = "in_recipe"
    protein = "protein"
    sauce = "sauce"
    any = "any"


class SubstitutionPreference(Base):
    __tablename__ = "substitution_preferences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    original_ingredient: Mapped[str] = mapped_column(String(255))
    replacements: Mapped[list] = mapped_column(JSON, default=list)
    context: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="substitution_preferences")
