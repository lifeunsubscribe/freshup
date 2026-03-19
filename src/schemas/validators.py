"""
Shared validation functions for Unicode-aware string validation.

Centralizes validation logic to ensure consistent handling of Unicode characters
across all schema modules. This prevents security vulnerabilities from duplicated
validation logic diverging over time.
"""

from typing import Optional
import unicodedata


# Validation constants for ingredient/allergy lists
MAX_LIST_ITEM_LENGTH = 100
MAX_LIST_SIZE = 100

# Unicode control and format characters to block (security)
# These include zero-width characters, control chars, and format chars
# Cc=Control, Cf=Format, Co=Private Use, Cn=Unassigned, Cs=Surrogate
BLOCKED_UNICODE_CATEGORIES = {'Cc', 'Cf', 'Co', 'Cn', 'Cs'}

# Common punctuation and symbols used in food names
ALLOWED_PUNCTUATION = set(" -'(),./")


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
