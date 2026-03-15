from __future__ import annotations

from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, Float, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class ConsumptionPattern(Base):
    __tablename__ = "consumption_patterns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_name: Mapped[str] = mapped_column(String(255))
    purchase_dates: Mapped[list] = mapped_column(JSON, default=list)
    depletion_dates: Mapped[list] = mapped_column(JSON, default=list)
    avg_interval_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notification_threshold: Mapped[float] = mapped_column(Float, default=0.8)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
