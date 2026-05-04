from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, JSON, Integer, func
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
    # Email is nullable to support migration of existing users without email addresses
    # New users will be required to provide an email during registration
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    # Password is nullable to support migration of existing users without passwords
    # and potential future OAuth/SSO authentication methods
    hashed_password: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.member.value)
    dietary_profile: Mapped[list] = mapped_column(JSON, default=list)
    allergies: Mapped[list] = mapped_column(JSON, default=list)
    disliked_ingredients: Mapped[list] = mapped_column(JSON, default=list)
    favorite_ingredients: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Account lockout fields for brute force protection
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    lockout_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    lockout_count: Mapped[int] = mapped_column(Integer, default=0)  # Tracks number of lockout events for progressive duration

    # Relationships
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="added_by_user")
    recipes_created: Mapped[list["Recipe"]] = relationship(back_populates="created_by_user")
    prepared_foods: Mapped[list["PreparedFood"]] = relationship(back_populates="prepared_by_user")
    grocery_list_items: Mapped[list["GroceryListItem"]] = relationship(
        back_populates="added_by_user", foreign_keys="GroceryListItem.added_by"
    )
    substitution_preferences: Mapped[list["SubstitutionPreference"]] = relationship(back_populates="user_rel")
    recipe_relations: Mapped[list["UserRecipeRelation"]] = relationship(back_populates="user_rel")
    menus: Mapped[list["Menu"]] = relationship(back_populates="user_rel")
    audit_logs: Mapped[list["AuthAuditLog"]] = relationship(back_populates="user")
