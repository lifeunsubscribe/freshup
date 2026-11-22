"""Pydantic schemas for the feedback endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class FeedbackCreate(BaseModel):
    """A note to the developer."""

    message: str = Field(..., max_length=4000, description="What the user wants to say")
    page: Optional[str] = Field(None, max_length=500, description="The page it was sent from")

    @field_validator('message')
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('message must not be empty')
        return v


class FeedbackResponse(BaseModel):
    """One stored note, as the review list shows it."""

    id: UUID
    message: str
    page: Optional[str]
    created_at: datetime
    user_name: str
