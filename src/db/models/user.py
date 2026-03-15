from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class UserRole(str, PyEnum):
    coordinator = "coordinator"
    member = "member"


class DietaryProfile(str, PyEnum):
    omnivore = "omnivore"
    vegetarian = "vegetarian"
    vegan = "vegan"
    pescatarian = "pescatarian"
    keto = "keto"
    low_carb = "low_carb"
    low_sugar = "low_sugar"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default=UserRole.member.value)
    dietary_profile: Mapped[list] = mapped_column(JSON, default=list)
    allergies: Mapped[list] = mapped_column(JSON, default=list)
    disliked_ingredients: Mapped[list] = mapped_column(JSON, default=list)
    favorite_ingredients: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="added_by_user")
    recipes_created: Mapped[list["Recipe"]] = relationship(back_populates="created_by_user")
    prepared_foods: Mapped[list["PreparedFood"]] = relationship(back_populates="prepared_by_user")
    grocery_list_items: Mapped[list["GroceryListItem"]] = relationship(
        back_populates="added_by_user", foreign_keys="GroceryListItem.added_by"
    )
    substitution_preferences: Mapped[list["SubstitutionPreference"]] = relationship(back_populates="user_rel")
    recipe_ratings: Mapped[list["UserRecipeRating"]] = relationship(back_populates="user_rel")
