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

from sqlalchemy import String, Text, DateTime, Integer, func, Index, ForeignKey
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

    The processing_started_at timestamp enables automatic recovery of tasks
    stuck in "processing" status due to worker crashes, preventing the race
    condition window between status change and task completion.

    The retry_count field tracks how many times a task has been recovered
    from stale status, preventing infinite retry loops for tasks that
    consistently crash workers.
    """
    __tablename__ = "processing_tasks"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # User ownership for multi-tenant isolation
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Task classification
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=TaskStatus.pending.value)

    # Input/output references
    input_reference: Mapped[str] = mapped_column(Text, nullable=False)
    result_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Retry tracking for stale task recovery
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Indexes for efficient task queries
    __table_args__ = (
        # Compound index for pending task queries
        Index('ix_processing_tasks_status_created_at', 'status', 'created_at'),
        # Compound index for stale task detection
        Index('ix_processing_tasks_status_processing_started_at', 'status', 'processing_started_at'),
        # Single-column index for user-specific queries and foreign key performance
        Index('ix_processing_tasks_user_id', 'user_id'),
    )
