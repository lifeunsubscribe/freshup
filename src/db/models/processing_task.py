"""
ProcessingTask model for tracking async LLM processing jobs.

Tracks receipt parsing and other LLM processing tasks through their lifecycle
from creation to completion or failure.
"""

from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class TaskType(str, PyEnum):
    """
    Type of processing task.

    Currently supports receipt parsing, with room for expansion
    to other LLM-based processing tasks.
    """
    receipt_parse = "receipt_parse"


class TaskStatus(str, PyEnum):
    """
    Status of a processing task through its lifecycle.

    - pending: Task queued but not yet started
    - processing: Task currently being processed
    - completed: Task finished successfully
    - failed: Task encountered an error
    """
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProcessingTask(Base):
    """
    Tracks async LLM processing jobs (e.g., receipt parsing).

    Processing tasks queue requests for LLM operations and track their
    status through the processing lifecycle. Results are stored as text
    references that can be resolved by the consuming service.
    """
    __tablename__ = "processing_tasks"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Task classification
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=TaskStatus.pending.value)

    # Input/output references
    input_reference: Mapped[str] = mapped_column(Text, nullable=False)
    result_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Compound index for efficient pending task queries
    __table_args__ = (
        Index('ix_processing_tasks_status_created_at', 'status', 'created_at'),
    )
