from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, ForeignKey, JSON, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Menu(Base):
    """
    User-created recipe collections with optional auto-generation via filter rules.

    Menus can be manually curated or auto-generated based on filter rules (e.g., dietary
    preferences, tags, ratings). The MenuRecipe join table tracks manual additions/removals
    to override auto-generated results.
    """
    __tablename__ = "menus"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    filter_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    cover_image: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user_rel: Mapped["User"] = relationship(back_populates="menus")
    menu_recipes: Mapped[list["MenuRecipe"]] = relationship(back_populates="menu_rel", cascade="all, delete-orphan")
    user_recipe_relations: Mapped[list["UserRecipeRelation"]] = relationship(back_populates="menu_rel")


class MenuRecipe(Base):
    """
    Join table for Menu-Recipe many-to-many relationship with ordering and manual override flags.

    Tracks which recipes belong to which menus, plus metadata about manual user actions
    (manually added/removed recipes override auto-generation rules).
    """
    __tablename__ = "menu_recipes"
    __table_args__ = (
        UniqueConstraint('menu_id', 'recipe_id', name='uq_menu_recipe'),
    )

    menu_id: Mapped[UUID] = mapped_column(ForeignKey("menus.id"), primary_key=True)
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    manually_added: Mapped[bool] = mapped_column(Boolean, default=False)
    manually_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    menu_rel: Mapped["Menu"] = relationship(back_populates="menu_recipes")
    recipe_rel: Mapped["Recipe"] = relationship(back_populates="menu_recipes")
