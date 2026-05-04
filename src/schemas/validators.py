"""
Shared validation functions for Unicode-aware string validation.

Centralizes validation logic to ensure consistent handling of Unicode characters
across all schema modules. This prevents security vulnerabilities from duplicated
validation logic diverging over time.
"""

from typing import Optional
from enum import Enum
import unicodedata
from urllib.parse import urlparse



# Validation constants for ingredient/allergy lists
MAX_LIST_ITEM_LENGTH = 100
MAX_LIST_SIZE = 100

# Unicode control and format characters to block (security)
# These include zero-width characters, control chars, and format chars
# Cc=Control, Cf=Format, Co=Private Use, Cn=Unassigned, Cs=Surrogate
BLOCKED_UNICODE_CATEGORIES = {'Cc', 'Cf', 'Co', 'Cn', 'Cs'}

# Common punctuation and symbols used in food names
ALLOWED_PUNCTUATION = set(" -'(),./")

# Validation constants for URL lists
MAX_URL_LENGTH = 2048  # Match other URL fields in schemas
MAX_URL_LIST_SIZE = 10  # Reasonable limit for photo uploads

# Allowed URL schemes for user-submitted content
ALLOWED_URL_SCHEMES = {'http', 'https'}

# Blocked hostnames for SSRF protection
BLOCKED_HOSTNAMES = {
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '::1',
    '[::1]',
}


def contains_blocked_characters(text: str) -> bool:
    """
    Check if text contains blocked Unicode characters.

    Blocks control characters, format characters, and other potentially
    dangerous Unicode that could cause security or display issues.
    """
    for char in text:
        if unicodedata.category(char) in BLOCKED_UNICODE_CATEGORIES:
            return True
    return False


def is_valid_ingredient_character(char: str) -> bool:
    """
    Check if a character is valid for ingredient names.

    Allows:
    - Unicode letters from any language (category L*)
    - Digits (category N*)
    - Common punctuation used in food names
    """
    category = unicodedata.category(char)

    # Allow letters (Lu, Ll, Lt, Lm, Lo)
    if category.startswith('L'):
        return True

    # Allow numbers (Nd, Nl, No)
    if category.startswith('N'):
        return True

    # Allow specific punctuation
    if char in ALLOWED_PUNCTUATION:
        return True

    return False


def validate_ingredient_name(field_name: str, value: str) -> str:
    """
    Validate a single ingredient name with Unicode support.

    Ensures ingredient name is not empty, normalizes Unicode (NFC),
    blocks dangerous control/format characters, and validates allowed characters.

    Args:
        field_name: Name of the field being validated (for error messages)
        value: The ingredient name to validate

    Returns:
        Normalized (NFC) ingredient name

    Raises:
        ValueError: If validation fails
    """
    if not value or not value.strip():
        raise ValueError(f'{field_name} cannot be empty')

    # Normalize to NFC form
    normalized = unicodedata.normalize('NFC', value.strip())

    # Check for blocked Unicode characters (security)
    if contains_blocked_characters(normalized):
        raise ValueError(
            f'{field_name} cannot contain control or format characters'
        )

    # Validate each character
    for char in normalized:
        if not is_valid_ingredient_character(char):
            char_name = unicodedata.name(char, f'U+{ord(char):04X}')
            raise ValueError(
                f'{field_name} can only contain letters, numbers, spaces, '
                f'and common punctuation (- \' ( ) , . /). '
                f'Invalid character: "{char}" ({char_name})'
            )

    return normalized


def validate_string_list(
    field_name: str,
    values: Optional[list[str]],
    max_item_length: int = MAX_LIST_ITEM_LENGTH,
    max_list_size: int = MAX_LIST_SIZE,
) -> Optional[list[str]]:
    """
    Validate a list of strings for ingredient/allergy fields.

    Ensures items meet length constraints and contain only allowed characters.
    Strips whitespace and filters out empty strings. Supports Unicode characters
    (e.g., jalapeño, crème fraîche) while blocking dangerous control characters.

    Args:
        field_name: Name of the field being validated (for error messages)
        values: List of strings to validate
        max_item_length: Maximum allowed length per item
        max_list_size: Maximum number of items in the list

    Returns:
        Validated, normalized (NFC), and cleaned list of strings, or None if input was None

    Raises:
        ValueError: If validation fails
    """
    if values is None:
        return None

    # Strip whitespace and filter empty strings
    cleaned = [item.strip() for item in values if item.strip()]

    # Check list size
    if len(cleaned) > max_list_size:
        raise ValueError(f'{field_name} cannot contain more than {max_list_size} items')

    # Normalize and validate each item
    normalized = []
    for item in cleaned:
        # Normalize to NFC form to handle different Unicode representations
        normalized_item = unicodedata.normalize('NFC', item)

        # Check item length
        if len(normalized_item) > max_item_length:
            raise ValueError(
                f'{field_name} items cannot exceed {max_item_length} characters. '
                f'Item "{normalized_item[:20]}..." is {len(normalized_item)} characters long'
            )

        # Check for blocked Unicode characters (security)
        if contains_blocked_characters(normalized_item):
            raise ValueError(
                f'{field_name} items cannot contain control or format characters. '
                f'Invalid item: "{normalized_item}"'
            )

        # Check allowed characters (Unicode-aware)
        for char in normalized_item:
            if not is_valid_ingredient_character(char):
                char_name = unicodedata.name(char, f'U+{ord(char):04X}')
                raise ValueError(
                    f'{field_name} items can only contain letters, numbers, spaces, '
                    f'and common punctuation (- \' ( ) , . /). '
                    f'Invalid character: "{char}" ({char_name}) in "{normalized_item}"'
                )

        normalized.append(normalized_item)

    return normalized


def validate_name_not_empty(value: Optional[str], strip: bool = True) -> Optional[str]:
    """
    Validate that a name field is not empty or whitespace-only.

    Normalizes Unicode to NFC form to prevent duplicate names with different
    Unicode representations (e.g., "café" with composed vs decomposed accents).

    Args:
        value: The name to validate
        strip: Whether to strip whitespace from the result (default: True)

    Returns:
        Stripped and NFC-normalized name if valid, or None if input was None

    Raises:
        ValueError: If name is empty or whitespace-only
    """
    if value is None:
        return None

    if not value or not value.strip():
        raise ValueError('Name cannot be empty')

    # Normalize to NFC form for consistent Unicode representation
    # Strip whitespace only if requested
    to_normalize = value.strip() if strip else value
    return unicodedata.normalize('NFC', to_normalize)


def validate_enum_value(
    field_name: str,
    value: Optional[str],
    enum_class: type[Enum],
    allow_none: bool = False
) -> Optional[str]:
    """
    Validate that a string value matches a valid enum value.

    Args:
        field_name: Name of the field being validated (for error messages)
        value: The value to validate
        enum_class: The Enum class to validate against
        allow_none: Whether None is allowed (default: False)

    Returns:
        The validated value, or None if value was None and allow_none is True

    Raises:
        ValueError: If value is not a valid enum value
    """
    if value is None:
        if allow_none:
            return None
        raise ValueError(f'{field_name} cannot be None')

    valid_values = [item.value for item in enum_class]
    if value not in valid_values:
        raise ValueError(f'{field_name} must be one of: {", ".join(valid_values)}. Got: {value}')

    return value


def validate_non_negative(
    field_name: str,
    value: Optional[float],
    allow_none: bool = True
) -> Optional[float]:
    """
    Validate that a numeric value is non-negative.

    Args:
        field_name: Name of the field being validated (for error messages)
        value: The numeric value to validate
        allow_none: Whether None is allowed (default: True)

    Returns:
        The validated value, or None if value was None and allow_none is True

    Raises:
        ValueError: If value is negative or None when not allowed
    """
    if value is None:
        if allow_none:
            return None
        raise ValueError(f'{field_name} cannot be None')

    if value < 0:
        raise ValueError(f'{field_name} cannot be negative')

    return value


def normalize_email(email: str) -> str:
    """
    Normalize email to lowercase for case-insensitive comparison.

    Args:
        email: The email address to normalize

    Returns:
        Lowercase email address
    """
    return email.lower()


def validate_dietary_profile(values: Optional[list[str]], valid_profiles: list[str]) -> Optional[list[str]]:
    """
    Validate dietary profile list against allowed values.

    Strips whitespace from each item and filters out empty strings.

    Args:
        values: List of dietary profile strings to validate
        valid_profiles: List of valid profile values

    Returns:
        Cleaned list of valid profiles, or None if input was None

    Raises:
        ValueError: If any profile is not in the valid list
    """
    if values is None:
        return None

    # Strip whitespace from each item and filter empty strings
    cleaned = [item.strip() for item in values if item.strip()]

    # Validate each profile
    for profile in cleaned:
        if profile not in valid_profiles:
            raise ValueError(f'Invalid dietary profile: {profile}. Must be one of: {", ".join(valid_profiles)}')

    return cleaned


def validate_url_list(
    field_name: str,
    values: Optional[list[str]],
    max_url_length: int = MAX_URL_LENGTH,
    max_list_size: int = MAX_URL_LIST_SIZE,
) -> Optional[list[str]]:
    """
    Validate a list of URLs with security checks.

    Ensures URLs are properly formatted, use allowed protocols, don't exceed
    length limits, and aren't targeting internal/localhost addresses (SSRF protection).

    Security checks:
    - Protocol whitelist: only http/https allowed
    - Length limits: per-URL and total array size
    - SSRF protection: blocks localhost, 127.0.0.1, ::1, etc.
    - Blocks dangerous protocols: javascript:, file:, data:, etc.

    Args:
        field_name: Name of the field being validated (for error messages)
        values: List of URL strings to validate
        max_url_length: Maximum allowed length per URL (default: 2048)
        max_list_size: Maximum number of URLs in the list (default: 10)

    Returns:
        Validated and stripped list of URLs, or None if input was None

    Raises:
        ValueError: If validation fails (invalid URL, blocked protocol, SSRF attempt, etc.)
    """
    if values is None:
        return None

    # Strip whitespace and filter empty strings
    cleaned = [url.strip() for url in values if url and url.strip()]

    # Check list size
    if len(cleaned) > max_list_size:
        raise ValueError(f'{field_name} cannot contain more than {max_list_size} URLs')

    validated = []
    for url in cleaned:
        # Check URL length
        if len(url) > max_url_length:
            raise ValueError(
                f'{field_name} URLs cannot exceed {max_url_length} characters. '
                f'URL "{url[:50]}..." is {len(url)} characters long'
            )

        # Parse URL to validate format and extract components
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f'{field_name} contains invalid URL "{url[:50]}...": {str(e)}')

        # Validate scheme exists and is allowed
        if not parsed.scheme:
            raise ValueError(f'{field_name} URL must include protocol (http:// or https://): "{url[:50]}..."')

        if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
            raise ValueError(
                f'{field_name} URL must use http:// or https:// protocol. '
                f'Got "{parsed.scheme}://" in "{url[:50]}..."'
            )

        # Validate hostname exists (SSRF protection - block missing/suspicious hosts)
        if not parsed.netloc:
            raise ValueError(f'{field_name} URL must include a hostname: "{url[:50]}..."')

        # SSRF protection: block localhost and loopback addresses
        # Extract hostname without port (handle both IPv4/hostname:port and [IPv6]:port)
        hostname_lower = parsed.netloc.lower()
        if ':' in hostname_lower and not hostname_lower.startswith('['):
            hostname_lower = hostname_lower.split(':')[0]  # Remove port for IPv4/hostname
        # For IPv6 like [::1]:port, netloc includes brackets, check with and without
        if hostname_lower in BLOCKED_HOSTNAMES or hostname_lower.strip('[]') in {'::1'}:
            raise ValueError(
                f'{field_name} cannot contain URLs targeting localhost or internal addresses: "{url[:50]}..."'
            )

        # Additional SSRF check: block IP addresses starting with 127.
        if hostname_lower.startswith('127.'):
            raise ValueError(
                f'{field_name} cannot contain URLs targeting localhost (127.x.x.x): "{url[:50]}..."'
            )

        validated.append(url)

    return validated
