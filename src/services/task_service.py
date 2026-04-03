"""
Service layer for ProcessingTask operations.

Provides business logic for task status retrieval and management.
"""

from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session

from src.db.models.processing_task import ProcessingTask


def get_task_by_id(task_id: UUID, db: Session) -> Optional[ProcessingTask]:
    """
    Retrieve a processing task by its ID.

    Args:
        task_id: UUID of the task to retrieve
        db: Database session

    Returns:
        ProcessingTask object if found, None otherwise
    """
    return db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
