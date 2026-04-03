"""
Pydantic schemas for ProcessingTask endpoints.

Defines request/response models for task CRUD operations and status tracking.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.db.models.processing_task import TaskType, TaskStatus
from src.schemas.validators import validate_enum_value


class ProcessingTaskCreate(BaseModel):
    """Request schema for creating a new processing task."""

    task_type: str = Field(..., description="Type of processing task (receipt_parse)")
    input_reference: str = Field(..., min_length=1, description="Reference to input data (e.g., file path, URL)")

    @field_validator('task_type')
    @classmethod
    def validate_task_type_field(cls, v: str) -> str:
        """Ensure task_type is a valid TaskType enum value."""
        result = validate_enum_value('task_type', v, TaskType, allow_none=False)
        return result  # type: ignore

    @field_validator('input_reference')
    @classmethod
    def validate_input_reference(cls, v: str) -> str:
        """Ensure input_reference is not empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("input_reference cannot be empty or only whitespace")
        return stripped


class ProcessingTaskUpdate(BaseModel):
    """Request schema for updating a processing task (typically status changes)."""

    status: Optional[str] = Field(default=None, description="Task status")
    result_reference: Optional[str] = Field(default=None, description="Reference to processing result")
    error_message: Optional[str] = Field(default=None, description="Error message if task failed")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")

    @field_validator('status')
    @classmethod
    def validate_status_field(cls, v: Optional[str]) -> Optional[str]:
        """Ensure status is a valid TaskStatus enum value if provided."""
        return validate_enum_value('status', v, TaskStatus, allow_none=True)


class ProcessingTaskResponse(BaseModel):
    """Response schema for processing task data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    input_reference: str
    result_reference: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    processing_started_at: Optional[datetime]
    completed_at: Optional[datetime]


class ProcessingTaskListResponse(BaseModel):
    """Response schema for processing task list items (lightweight)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
