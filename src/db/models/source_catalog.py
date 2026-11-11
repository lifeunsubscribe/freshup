from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class SourceCollection(Base):
    """A HelloFresh collection page (e.g. "Vegetarian recipes") with optional parent."""
    __tablename__ = "source_collections"
    __table_args__ = (
        UniqueConstraint("source_type", "slug", name="uq_source_collections_source_type_slug"),
        Index("ix_source_collections_parent_slug", "parent_slug"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50))
    slug: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    # Not a FK: a child collection is often seen before its parent is fetched.
    parent_slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(String(2048))
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    collection_cards: Mapped[list["SourceCollectionCard"]] = relationship(
        back_populates="collection_rel", cascade="all, delete-orphan", passive_deletes=True
    )


class SourceRecipeCard(Base):
    """A recipe card shown on a source collection page, before the recipe is imported."""
    __tablename__ = "source_recipe_cards"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "recipe_url", name="uq_source_recipe_cards_source_type_recipe_url"
        ),
        Index("ix_source_recipe_cards_recipe_id", "recipe_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    headline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rating_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recipe_url: Mapped[str] = mapped_column(String(2048))
    # Set once the card is imported as a full Recipe. ON DELETE SET NULL preserves
    # the card if the imported recipe is later pruned (is_persisted cleanup).
    recipe_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # passive_deletes: let the DB's ON DELETE SET NULL handle recipe removal.
    recipe_rel: Mapped[Optional["Recipe"]] = relationship(  # type: ignore[name-defined]
        "Recipe", foreign_keys=[recipe_id], passive_deletes=True
    )
    collection_cards: Mapped[list["SourceCollectionCard"]] = relationship(
        back_populates="card_rel", cascade="all, delete-orphan", passive_deletes=True
    )


class SourceCollectionCard(Base):
    """Join table linking a SourceCollection to the SourceRecipeCards it lists."""
    __tablename__ = "source_collection_cards"
    __table_args__ = (
        Index("ix_source_collection_cards_card_id", "card_id"),
    )

    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_collections.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_recipe_cards.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)

    collection_rel: Mapped["SourceCollection"] = relationship(
        back_populates="collection_cards"
    )
    card_rel: Mapped["SourceRecipeCard"] = relationship(back_populates="collection_cards")
