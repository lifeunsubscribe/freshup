from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class SourceHealthCheck(Base):
    """
    One check result per source per run.

    All rows are retained; the endpoint reads the latest per source.
    """
    __tablename__ = "source_health_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime)
    # 'healthy' or 'failing'
    status: Mapped[str] = mapped_column(String(20))
    # Sanitised one-sentence description of the failure, null when healthy
    detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 'link' or 'saved_page' — describes how the source is normally imported
    import_mode: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
