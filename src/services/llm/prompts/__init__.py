"""
LLM prompt templates for FreshUp.

Centralized prompt management for all LLM-based features:
- Receipt parsing (Phase 4)
- Recipe card OCR (Phase 2B)
- Photo upload parsing (Phase 2D)
- Voice command interpretation (Phase 5)
- Video transcript parsing (Phase 2D)

Each module exports system and user prompt templates for its domain.
"""

__all__ = [
    'receipt',
    'transcript',
]
