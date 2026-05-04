from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, JSON, ForeignKey, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class SourceType(str, PyEnum):
    hellofresh_card = "hellofresh_card"
    hellofresh_web = "hellofresh_web"
    kitchen_sanctuary = "kitchen_sanctuary"
    url_import = "url_import"
    manual = "manual"
    photo_upload = "photo_upload"
    ad_hoc = "ad_hoc"


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_image: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    variation_groups: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    base_servings: Mapped[int] = mapped_column(Integer, default=4)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    nutritional_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    times_cooked: Mapped[int] = mapped_column(Integer, default=0)
    is_persisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(10000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    created_by_user: Mapped[Optional["User"]] = relationship(back_populates="recipes_created")
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="recipe_rel")
    user_relations: Mapped[list["UserRecipeRelation"]] = relationship(back_populates="recipe_rel")
    menu_recipes: Mapped[list["MenuRecipe"]] = relationship(back_populates="recipe_rel")
    prepared_foods: Mapped[list["PreparedFood"]] = relationship(back_populates="source_recipe_rel")
