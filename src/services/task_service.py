"""
Service layer for ProcessingTask operations.

Provides business logic for task status retrieval and management.
"""

from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session

from src.db.models.processing_task import ProcessingTask


def get_task_by_id(task_id: UUID, user_id: UUID, db: Session) -> Optional[ProcessingTask]:
    """
    Retrieve a processing task by its ID for a specific user.

    Enforces multi-tenant isolation by filtering on both task_id and user_id.
    This defense-in-depth approach ensures authorization at the service layer,
    not just the router layer.

    Args:
        task_id: UUID of the task to retrieve
        user_id: UUID of the user who owns the task
        db: Database session

    Returns:
        ProcessingTask object if found and owned by user, None otherwise
    """
    return db.query(ProcessingTask).filter(
        ProcessingTask.id == task_id,
        ProcessingTask.user_id == user_id
    ).first()
