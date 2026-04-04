"""
Sanitization utilities for removing PII from exception messages.

Provides pattern-based redaction of sensitive data (emails, phone numbers,
credit cards, addresses) from exception messages before logging or storage.

Per Security Issue #377: LLM responses may contain PII from receipts that
could be exposed through error reporting systems. This module ensures
exception messages are sanitized before being logged or stored.
"""

import re
from typing import Pattern


class PIIPatterns:
    """
    Compiled regex patterns for common PII types.

    Patterns are intentionally broad to favor over-redaction (false positives)
    over under-redaction (false negatives) for security.
    """

    # Email addresses: username@domain.tld
    EMAIL: Pattern[str] = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        re.IGNORECASE
    )

    # Phone numbers: Various formats (US-focused but covers international)
    # Matches: (123) 456-7890, 123-456-7890, 123.456.7890, 1234567890, +1-123-456-7890
    PHONE: Pattern[str] = re.compile(
        r'(?:\+?1[-.\s]?)?'  # Optional country code
        r'(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?'  # Area code
        r'[0-9]{3}[-.\s]?'  # Exchange
        r'[0-9]{4}\b'  # Subscriber number
    )

    # Credit card numbers: 4 groups of 4 digits (with optional separators)
    # Matches: 1234-5678-9012-3456, 1234 5678 9012 3456, 1234567890123456
    CREDIT_CARD: Pattern[str] = re.compile(
        r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    )

    # Social Security Numbers: 123-45-6789 (requires dashes to reduce false positives)
    # Note: Does not match 9-digit sequences without dashes to avoid redacting
    # transaction IDs, order numbers, etc. that commonly appear in receipts.
    SSN: Pattern[str] = re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    )

    # ZIP codes followed by street patterns (simple address detection)
    # Matches common address patterns to catch receipt headers/footers
    ADDRESS: Pattern[str] = re.compile(
        r'\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way)\b',
        re.IGNORECASE
    )

    # US ZIP codes: 12345 or 12345-6789
    # Use word boundaries and negative lookbehind to avoid matching:
    # - Port numbers (preceded by colon): localhost:12345
    # - URL path segments (preceded by slash): /users/12345
    # - Query parameter values (preceded by equals): ?user_id=12345
    ZIP_CODE: Pattern[str] = re.compile(
        r'(?<![=:\/])\b\d{5}(?:-\d{4})?\b'
    )


# Redaction labels for different PII types
REDACTION_LABELS = {
    'email': '[EMAIL_REDACTED]',
    'phone': '[PHONE_REDACTED]',
    'credit_card': '[CARD_REDACTED]',
    'ssn': '[SSN_REDACTED]',
    'address': '[ADDRESS_REDACTED]',
    'zip_code': '[ZIP_REDACTED]',
}


def sanitize_exception_message(message: str, max_length: int = 500) -> str:
    """
    Sanitize an exception message by redacting PII and truncating length.

    Applies pattern-based redaction for common PII types (emails, phone numbers,
    credit cards, SSNs, addresses) and truncates the message to a safe length
    to prevent receipt data from leaking through validation errors.

    Args:
        message: The exception message to sanitize
        max_length: Maximum length for the sanitized message (default: 500)

    Returns:
        Sanitized message with PII redacted and length constrained

    Examples:
        >>> sanitize_exception_message("Error: email user@example.com not found")
        "Error: email [EMAIL_REDACTED] not found"

        >>> sanitize_exception_message("Failed to parse: " + "x" * 600)
        "Failed to parse: xxx...[TRUNCATED 100 chars]"

    Security Note:
        This function intentionally favors over-redaction (false positives) to
        ensure PII is not leaked through logs or error tracking systems.
    """
    # Handle None input to maintain str return type contract
    if message is None:
        return ""
    if not message:
        return message

    # Normalize literal \n (from repr'd/serialized strings like Pydantic
    # input_value) to spaces so PII patterns can match across them.
    sanitized = message.replace('\\n', ' ')

    # Apply PII pattern redactions in order of specificity
    # More specific patterns first to avoid partial matches

    # 1. Credit card numbers (before phone numbers to avoid partial matches)
    sanitized = PIIPatterns.CREDIT_CARD.sub(
        REDACTION_LABELS['credit_card'],
        sanitized
    )

    # 2. Social Security Numbers
    sanitized = PIIPatterns.SSN.sub(
        REDACTION_LABELS['ssn'],
        sanitized
    )

    # 3. Email addresses
    sanitized = PIIPatterns.EMAIL.sub(
        REDACTION_LABELS['email'],
        sanitized
    )

    # 4. Phone numbers
    sanitized = PIIPatterns.PHONE.sub(
        REDACTION_LABELS['phone'],
        sanitized
    )

    # 5. Street addresses (before ZIP codes to catch full addresses)
    sanitized = PIIPatterns.ADDRESS.sub(
        REDACTION_LABELS['address'],
        sanitized
    )

    # 6. ZIP codes (catch any remaining standalone ZIPs)
    sanitized = PIIPatterns.ZIP_CODE.sub(
        REDACTION_LABELS['zip_code'],
        sanitized
    )

    # Truncate to max_length to prevent receipt data dumps
    if len(sanitized) > max_length:
        truncated_chars = len(sanitized) - max_length
        sanitized = sanitized[:max_length] + f"...[TRUNCATED {truncated_chars} chars]"

    return sanitized


def sanitize_llm_response_preview(response: str, preview_length: int = 100) -> str:
    """
    Sanitize an LLM response for safe preview logging.

    Applies aggressive truncation and PII redaction for debug logging of
    LLM responses. Use this when you need to log response snippets for
    debugging without exposing full receipt data.

    Args:
        response: The LLM response text to sanitize
        preview_length: Maximum preview length (default: 100)

    Returns:
        Heavily sanitized preview safe for debug logging

    Example:
        >>> sanitize_llm_response_preview('{"store": "Costco", "items": [...]}', 50)
        '[LLM_RESPONSE_REDACTED: 39 chars, starts with: {"st...]'
    """
    if not response:
        return "[EMPTY_RESPONSE]"

    # For LLM responses, be extra conservative - just show length and prefix
    char_count = len(response)
    safe_prefix = response[:preview_length]

    # Still sanitize the prefix in case it contains PII
    safe_prefix = sanitize_exception_message(safe_prefix, max_length=preview_length)

    return f"[LLM_RESPONSE_REDACTED: {char_count} chars, starts with: {safe_prefix}]"
