"""
Pydantic schemas for recipe import service.

Defines data models for import results and batch import operations.
"""

from enum import Enum
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class ImportStatus(str, Enum):
    """Status of a recipe import operation."""
    success = "success"
    duplicate = "duplicate"
    error = "error"


class ImportResult(BaseModel):
    """
    Result of a single recipe import operation.

    Attributes:
        status: Import status (success/duplicate/error)
        recipe_id: UUID of the created recipe (present on success)
        warnings: List of non-fatal warnings (e.g., unparseable ingredients)
        error_message: Error description (present on error)
        source_url: The URL that was imported
    """
    status: ImportStatus = Field(..., description="Import status")
    recipe_id: Optional[UUID] = Field(default=None, description="UUID of created recipe (success only)")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings during import")
    error_message: Optional[str] = Field(default=None, description="Error description (error status only)")
    source_url: str = Field(..., description="Source URL of the recipe")


class BatchImportResult(BaseModel):
    """
    Result of a batch recipe import operation.

    Provides aggregate statistics and individual results for each URL.

    Attributes:
        total: Total number of URLs processed
        imported: Number of recipes successfully imported
        duplicates: Number of recipes skipped (already exist)
        errors: Number of failed imports
        results: Individual ImportResult for each URL
    """
    total: int = Field(..., description="Total URLs processed")
    imported: int = Field(..., ge=0, description="Successfully imported count")
    duplicates: int = Field(..., ge=0, description="Duplicate recipes skipped count")
    errors: int = Field(..., ge=0, description="Failed imports count")
    results: list[ImportResult] = Field(default_factory=list, description="Individual import results")
