from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class Feedback(Base):
    """
    A note a user sent to the developer from inside the app.

    Kept so it can be read back while the app is being built; nothing acts on
    it automatically.
    """
    __tablename__ = "feedback"
    # Declared here as well as in the migration: the review list is newest first.
    __table_args__ = (
        Index("ix_feedback_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", name="fk_feedback_user_id_users")
    )
    message: Mapped[str] = mapped_column(Text)
    # What the note is about: wrong-info, not-working, idea or other.
    kind: Mapped[str] = mapped_column(String(30), default="other", server_default="other")
    # The page the user was on when they sent it, e.g. "/plan/2026-11-15".
    page: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user_rel: Mapped["User"] = relationship(foreign_keys=[user_id])  # type: ignore[name-defined]
