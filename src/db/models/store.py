from __future__ import annotations

from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    has_digital_receipts: Mapped[bool] = mapped_column(Boolean, default=False)
    parsing_profile: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    inventory_items_preferred: Mapped[list["InventoryItem"]] = relationship(
        back_populates="preferred_store_rel", foreign_keys="InventoryItem.preferred_store"
    )
    grocery_list_items: Mapped[list["GroceryListItem"]] = relationship(back_populates="target_store_rel")
