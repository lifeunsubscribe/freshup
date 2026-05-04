from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Table, Column, func, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Category(str, PyEnum):
    produce = "produce"
    protein = "protein"
    dairy = "dairy"
    grain = "grain"
    pantry_staple = "pantry_staple"
    frozen = "frozen"
    snack = "snack"
    condiment = "condiment"
    beverage = "beverage"
    spice = "spice"
    baking = "baking"
    oil_vinegar = "oil_vinegar"
    canned = "canned"
    other = "other"


class UnitType(str, PyEnum):
    oz = "oz"
    lb = "lb"
    g = "g"
    kg = "kg"
    ml = "ml"
    l = "l"
    count = "count"
    pack = "pack"
    bunch = "bunch"
    can = "can"
    bottle = "bottle"
    bag = "bag"
    box = "box"
    tbsp = "tbsp"
    tsp = "tsp"
    cup = "cup"
    pint = "pint"
    quart = "quart"
    gallon = "gallon"
    other = "other"


class StorageLocation(str, PyEnum):
    pantry = "pantry"
    fridge = "fridge"
    freezer = "freezer"


class Shareability(str, PyEnum):
    shared = "shared"
    reserved = "reserved"
    personal = "personal"


# Association table for inventory items <-> stores (available_at_stores)
inventory_store_association = Table(
    "inventory_store_association",
    Base.metadata,
    Column("inventory_item_id", ForeignKey("inventory_items.id"), primary_key=True),
    Column("store_id", ForeignKey("stores.id"), primary_key=True),
)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    # Normalized lowercase column for efficient case-insensitive matching (issue #477)
    # Automatically maintained via SQLAlchemy event listeners below
    name_lower: Mapped[str] = mapped_column(String(255), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50))
    vegan_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_location: Mapped[str] = mapped_column(String(50))
    date_added: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    frozen_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_staple: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shareability: Mapped[str] = mapped_column(String(50), default=Shareability.shared.value)
    # reserved_for: nullable UUID without FK constraint — FK added in Phase 3
    reserved_for: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    reserved_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    added_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_store: Mapped[Optional[UUID]] = mapped_column(ForeignKey("stores.id"), nullable=True)

    # Relationships
    added_by_user: Mapped["User"] = relationship(back_populates="inventory_items")
    preferred_store_rel: Mapped[Optional["Store"]] = relationship(
        back_populates="inventory_items_preferred", foreign_keys=[preferred_store]
    )
    available_at_stores: Mapped[list["Store"]] = relationship(
        secondary=inventory_store_association
    )


# SQLAlchemy event listeners to automatically maintain name_lower
# This ensures the normalized column stays in sync with name changes
@event.listens_for(InventoryItem, 'before_insert')
@event.listens_for(InventoryItem, 'before_update')
def normalize_inventory_name(mapper, connection, target):
    """Automatically set name_lower from name before insert/update."""
    if target.name is not None:
        target.name_lower = target.name.lower()
