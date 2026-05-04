from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, ForeignKey, UniqueConstraint, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserRecipeRelation(Base):
    """
    Tracks user engagement with recipes: ratings, bookmarks, likes, and menu associations.

    Each user can have one relation record per recipe containing all their interactions
    with that recipe (rating, bookmark status, like status, photos, comments).
    """
    __tablename__ = "user_recipe_relations"
    __table_args__ = (
        UniqueConstraint('user_id', 'recipe_id', name='uq_user_recipe_relation'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id"))
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_liked: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_photos: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    rating_comment: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    menu_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("menus.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="recipe_relations")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="user_relations")
    menu_rel: Mapped[Optional["Menu"]] = relationship(back_populates="user_recipe_relations")
