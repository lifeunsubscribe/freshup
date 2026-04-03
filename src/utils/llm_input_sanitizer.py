"""
Input sanitization utilities for LLM prompts.

Provides defense-in-depth security for user input sent to language models,
preventing prompt injection attacks, DoS via excessive length, and context overflow.

Security measures:
- Length limiting with truncation (prevents DoS and context overflow)
- Unicode normalization (prevents encoding attacks)
- Control character filtering (prevents injection via invisible chars)
- Prompt injection pattern detection (mitigates common attack vectors)

Per security best practices: Always sanitize user input before sending to LLMs,
even when using structured output validation, as a defense-in-depth measure.
"""

import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# Unicode categories to block for LLM input (security)
# Excludes normal whitespace chars (space, tab, newline) from blocking
# Cc=Control chars (but we'll manually allow \t, \n, \r)
# Cf=Format chars, Co=Private Use, Cn=Unassigned, Cs=Surrogate
BLOCKED_UNICODE_CATEGORIES = {'Cf', 'Co', 'Cn', 'Cs'}

# Control characters to explicitly allow (normal whitespace)
ALLOWED_CONTROL_CHARS = {'\t', '\n', '\r'}

# Maximum input length for LLM prompts (in characters)
# Conservative limit to fit within typical 8K token context windows
# Assumes ~4 chars per token average, with buffer for system prompt and output
MAX_LLM_INPUT_LENGTH = 16000

# Common prompt injection patterns to detect and log
# These are patterns attackers use to override system instructions
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"disregard\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?previous\s+instructions",
    r"system\s+prompt",
    r"new\s+instructions",
    r"you\s+are\s+now",
    r"act\s+as\s+if",
    r"pretend\s+to\s+be",
]

# Compile patterns for performance
INJECTION_REGEX = re.compile(
    r"|".join(PROMPT_INJECTION_PATTERNS),
    re.IGNORECASE | re.MULTILINE
)


def sanitize_llm_input(
    text: str,
    max_length: int = MAX_LLM_INPUT_LENGTH,
    field_name: str = "input"
) -> str:
    """
    Sanitize user input before sending to LLM.

    Applies multiple security measures:
    1. Unicode normalization (NFC form)
    2. Control character removal (blocks invisible chars used in injection)
    3. Prompt injection pattern detection (logs warnings)
    4. Length limiting with truncation (prevents DoS and context overflow)

    Args:
        text: Raw user input to sanitize
        max_length: Maximum allowed length in characters (default: 16000)
        field_name: Name of the field being sanitized (for logging)

    Returns:
        Sanitized text safe for LLM consumption

    Raises:
        ValueError: If input is empty after sanitization

    Note:
        Uses truncation strategy rather than rejection for better UX.
        Logs warnings when sanitization modifies input significantly.
    """
    if not text:
        raise ValueError(f"{field_name} cannot be empty")

    original_length = len(text)

    # Step 1: Normalize Unicode to NFC form
    # Prevents attacks using different Unicode representations of same chars
    normalized = unicodedata.normalize('NFC', text)

    # Step 2: Remove blocked Unicode characters (control chars, format chars, etc.)
    # These can be used for prompt injection via invisible instructions
    # Allow normal whitespace (space, tab, newline, carriage return)
    cleaned_chars = []
    removed_count = 0

    for char in normalized:
        category = unicodedata.category(char)

        # Always allow normal whitespace control chars
        if char in ALLOWED_CONTROL_CHARS:
            cleaned_chars.append(char)
            continue

        # Block dangerous Unicode categories
        if category in BLOCKED_UNICODE_CATEGORIES:
            removed_count += 1
            continue

        # Block other control chars (Cc category except whitelisted)
        if category == 'Cc':
            removed_count += 1
            continue

        cleaned_chars.append(char)

    cleaned = ''.join(cleaned_chars)

    if removed_count > 0:
        logger.warning(
            f"Removed {removed_count} blocked Unicode characters from {field_name}",
            extra={
                "field_name": field_name,
                "removed_count": removed_count,
                "original_length": original_length
            }
        )

    # Step 3: Check for common prompt injection patterns
    # Don't remove them (could break legitimate content), but log for monitoring
    # SECURITY: Limit text length before regex to prevent ReDoS attacks
    # Only check first max_length chars to avoid catastrophic backtracking
    text_to_check = cleaned[:max_length] if len(cleaned) > max_length else cleaned
    if INJECTION_REGEX.search(text_to_check):
        logger.warning(
            f"Potential prompt injection detected in {field_name}",
            extra={
                "field_name": field_name,
                "input_preview": cleaned[:200]  # First 200 chars for investigation
            }
        )

    # Step 4: Enforce maximum length (truncate if needed)
    if len(cleaned) > max_length:
        truncated = cleaned[:max_length] + "..."
        logger.warning(
            f"{field_name} truncated from {len(cleaned)} to {max_length} characters",
            extra={
                "field_name": field_name,
                "original_length": len(cleaned),
                "max_length": max_length
            }
        )
        cleaned = truncated

    # Final validation: ensure we still have content
    if not cleaned.strip():
        raise ValueError(f"{field_name} cannot be empty (empty after sanitization)")

    # Log info if significant changes were made
    if len(cleaned) < original_length * 0.95:  # More than 5% reduction
        logger.info(
            f"Sanitization significantly modified {field_name}",
            extra={
                "field_name": field_name,
                "original_length": original_length,
                "sanitized_length": len(cleaned),
                "reduction_pct": round((1 - len(cleaned)/original_length) * 100, 1)
            }
        )

    return cleaned


def validate_llm_input_length(text: str, max_length: int = MAX_LLM_INPUT_LENGTH) -> bool:
    """
    Check if input exceeds maximum allowed length without sanitizing.

    Useful for validation before processing, to provide early feedback.

    Args:
        text: Input text to check
        max_length: Maximum allowed length in characters

    Returns:
        True if input is within limit, False otherwise
    """
    return len(text) <= max_length


def get_recommended_max_length() -> int:
    """
    Get the recommended maximum input length for LLM prompts.

    Returns:
        Maximum input length in characters
    """
    return MAX_LLM_INPUT_LENGTH
