from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserRecipeRating(Base):
    __tablename__ = "user_recipe_ratings"
    __table_args__ = (
        UniqueConstraint('user_id', 'recipe_id', name='uq_user_recipe_rating'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="recipe_ratings")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="user_ratings")
