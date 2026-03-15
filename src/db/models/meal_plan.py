from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, Date, DateTime, JSON, ForeignKey, Table, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class MealType(str, PyEnum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class MealPlanStatus(str, PyEnum):
    draft = "draft"
    voting = "voting"
    approved = "approved"
    shopping = "shopping"
    ready = "ready"
    cooked = "cooked"
    skipped = "skipped"
    pushed = "pushed"


class VotingStatus(str, PyEnum):
    candidate_generation = "candidate_generation"
    ranking = "ranking"
    draft_review = "draft_review"
    approved = "approved"
    active = "active"


# Association table for meal plan entry <-> users (opt-ins)
meal_plan_user_association = Table(
    "meal_plan_user_association",
    Base.metadata,
    Column("meal_plan_entry_id", ForeignKey("meal_plan_entries.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    date: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String(50))
    recipe_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("recipes.id"), nullable=True)
    prepared_food_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("prepared_foods.id"), nullable=True)
    planned_servings: Mapped[int] = mapped_column(Integer, default=1)
    make_extra: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_servings_purpose: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    user_variations: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default=MealPlanStatus.draft.value)
    leftovers_generated: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("prepared_foods.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Relationships
    recipe_rel: Mapped[Optional["Recipe"]] = relationship(foreign_keys=[recipe_id])
    prepared_food_rel: Mapped[Optional["PreparedFood"]] = relationship(foreign_keys=[prepared_food_id])
    leftovers_rel: Mapped[Optional["PreparedFood"]] = relationship(foreign_keys=[leftovers_generated])
    user_opt_ins: Mapped[list["User"]] = relationship(secondary=meal_plan_user_association)


class WeeklyMealPlanVote(Base):
    __tablename__ = "weekly_meal_plan_votes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    week_start: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default=VotingStatus.candidate_generation.value)
    candidate_recipes: Mapped[list] = mapped_column(JSON, default=list)
    user_rankings: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_plan: Mapped[list] = mapped_column(JSON, default=list)
    approved_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
