from __future__ import annotations

from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, Boolean, JSON, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    # Normalized lowercase column for efficient case-insensitive lookups (issue #477)
    # Automatically maintained via SQLAlchemy event listeners below
    # Unique constraint mirrors the uniqueness of stores.name
    name_lower: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    has_digital_receipts: Mapped[bool] = mapped_column(Boolean, default=False)
    parsing_profile: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    inventory_items_preferred: Mapped[list["InventoryItem"]] = relationship(
        back_populates="preferred_store_rel", foreign_keys="InventoryItem.preferred_store"
    )
    grocery_list_items: Mapped[list["GroceryListItem"]] = relationship(back_populates="target_store_rel")


# SQLAlchemy event listeners to automatically maintain name_lower
# This ensures the normalized column stays in sync with name changes
@event.listens_for(Store, 'before_insert')
@event.listens_for(Store, 'before_update')
def normalize_store_name(mapper, connection, target):
    """Automatically set name_lower from name before insert/update.

    Note: This event listener operates on ORM-level operations and will NOT fire
    for bulk operations executed via connection.execute() or session.execute() with
    bulk_insert_mappings(), bulk_update_mappings(), or raw SQL UPDATE statements.
    For bulk operations, ensure name_lower is set explicitly or use database triggers.
    """
    if target.name is not None:
        target.name_lower = target.name.lower()
