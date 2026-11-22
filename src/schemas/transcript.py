"""
Pydantic schemas for video transcript cooking-note extraction.

Defines the LLM output structures used by transcript_recipe_service.
Per Phase 2D: per-chunk extraction keeps each call inside the model's
context window regardless of video length.
"""

from typing import Optional
from pydantic import BaseModel, Field


class IngredientMention(BaseModel):
    """An ingredient name and optional spoken amount extracted from one transcript chunk."""

    name: str = Field(..., description="Ingredient name as the speaker said it")
    amount: Optional[str] = Field(
        default=None,
        description="Spoken amount in the speaker's words, or null when not stated",
    )


class ChunkNotes(BaseModel):
    """Cooking notes extracted from a single transcript chunk."""

    ingredients: list[IngredientMention] = Field(
        default_factory=list,
        description="Ingredients mentioned in this chunk",
    )
    actions: list[str] = Field(
        default_factory=list,
        description="Cooking actions in the order spoken",
    )


class NotesResult(BaseModel):
    """Aggregated result from extract_all_notes."""

    notes: list[ChunkNotes] = Field(
        default_factory=list,
        description="One ChunkNotes per successfully processed chunk, in order",
    )
    failed_chunks: int = Field(
        default=0,
        description="Number of chunks that raised LLMResponseError and were skipped",
    )
