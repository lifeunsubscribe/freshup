"""
Ingredient string parser for FreshUp.

Provides deterministic parsing of ingredient strings from recipe-scrapers into
structured components (quantity, unit, name, preparation, optional flag).

No LLM usage per ADR-003 - pure rule-based parsing.
"""

import logging
import re
from typing import TypedDict

logger = logging.getLogger(__name__)


class ParsedIngredient(TypedDict):
    """
    Structured representation of a parsed ingredient.

    Attributes:
        quantity: Numeric amount (0.0 if unparseable or absent)
        unit: Measurement unit (empty string if none)
        ingredient_name: The core ingredient name
        preparation: Preparation instructions (e.g., "minced", "chopped")
        is_optional: Whether the ingredient is optional
        raw_text: Original input string for debugging
    """
    quantity: float
    unit: str
    ingredient_name: str
    preparation: str
    is_optional: bool
    raw_text: str


# Unicode fraction mappings
UNICODE_FRACTIONS = {
    '½': '1/2',
    '⅓': '1/3',
    '⅔': '2/3',
    '¼': '1/4',
    '¾': '3/4',
    '⅕': '1/5',
    '⅖': '2/5',
    '⅗': '3/5',
    '⅘': '4/5',
    '⅙': '1/6',
    '⅚': '5/6',
    '⅐': '1/7',
    '⅛': '1/8',
    '⅜': '3/8',
    '⅝': '5/8',
    '⅞': '7/8',
    '⅑': '1/9',
    '⅒': '1/10',
}

# Known measurement units (lowercase for case-insensitive matching)
KNOWN_UNITS = {
    # Volume
    'cup', 'cups', 'c',
    'tablespoon', 'tablespoons', 'tbsp', 'tbs', 'tb',
    'teaspoon', 'teaspoons', 'tsp', 'ts',
    'milliliter', 'milliliters', 'ml', 'mls',
    'liter', 'liters', 'l',
    'fluid ounce', 'fluid ounces', 'fl oz', 'fl. oz.',
    'pint', 'pints', 'pt', 'pts',
    'quart', 'quarts', 'qt', 'qts',
    'gallon', 'gallons', 'gal', 'gals',

    # Weight
    'ounce', 'ounces', 'oz',
    'pound', 'pounds', 'lb', 'lbs',
    'gram', 'grams', 'g',
    'kilogram', 'kilograms', 'kg',

    # Count/discrete
    'clove', 'cloves',
    'bunch', 'bunches',
    'pinch', 'pinches',
    'dash', 'dashes',
    'piece', 'pieces',
    'slice', 'slices',
    'can', 'cans',
    'package', 'packages', 'pkg', 'pkgs',
    'jar', 'jars',
    'box', 'boxes',
    'bag', 'bags',
    'sprig', 'sprigs',
    'stalk', 'stalks',
    'head', 'heads',
    'leaf', 'leaves',
    'bay',  # bay leaves
    'whole', 'halves', 'half',
    'large', 'medium', 'small',  # size descriptors often used as units
    'inch', 'inches',  # dimensional measurements
}

# Markers indicating optional ingredients
OPTIONAL_MARKERS = {
    'to taste',
    'optional',
    'if desired',
    'as needed',
    'for serving',
    'for garnish',
}


def _normalize_unicode_fractions(text: str) -> str:
    """
    Replace Unicode fraction characters with ASCII equivalents.

    Args:
        text: Input string potentially containing Unicode fractions

    Returns:
        String with Unicode fractions replaced by ASCII (e.g., "½" → "1/2")
    """
    for unicode_char, ascii_equiv in UNICODE_FRACTIONS.items():
        # If the Unicode fraction is preceded by a digit, add a space
        # This handles mixed numbers like "2¼" → "2 1/4" (not "21/4")
        text = re.sub(r'(\d)' + re.escape(unicode_char), r'\1 ' + ascii_equiv, text)
        # Handle standalone fractions (not preceded by digit)
        text = text.replace(unicode_char, ascii_equiv)
    return text


def _parse_fraction(fraction_str: str) -> float:
    """
    Parse a fraction string to float.

    Args:
        fraction_str: String like "1/2", "3/4", etc.

    Returns:
        Float value of the fraction

    Raises:
        ValueError: If fraction cannot be parsed
    """
    parts = fraction_str.split('/')
    if len(parts) != 2:
        raise ValueError(f"Invalid fraction: {fraction_str}")

    numerator = float(parts[0].strip())
    denominator = float(parts[1].strip())

    if denominator == 0:
        raise ValueError(f"Division by zero in fraction: {fraction_str}")

    return numerator / denominator


def _extract_quantity(text: str) -> tuple[float, str]:
    """
    Extract quantity from the beginning of the text.

    Handles:
    - Simple numbers: "4" → 4.0
    - Fractions: "1/2" → 0.5
    - Mixed numbers: "1 1/2" → 1.5
    - Ranges: "2-3" → 2.5 (midpoint)
    - Decimal: "1.5" → 1.5

    Args:
        text: Input text

    Returns:
        Tuple of (quantity, remaining_text)
        Returns (0.0, original_text) if no quantity found

    Security:
        Pattern uses explicit alternation (decimal|integer) instead of optional groups
        to prevent catastrophic backtracking (ReDoS vulnerability).
    """
    text = text.strip()

    # Pattern for quantity extraction (handles ranges, mixed numbers, fractions, decimals)
    # Matches: "1-2", "1 1/2", "1/2", "1.5", "1"
    # Security: Uses (\d+\.\d+|\d+) instead of (\d+(?:\.\d+)?) to prevent ReDoS
    # The alternation forces a definite choice (decimal OR integer) with no backtracking
    quantity_pattern = r'^(\d+\.\d+|\d+)\s*-\s*(\d+\.\d+|\d+)|^(\d+)\s+(\d+/\d+)|^(\d+/\d+)|^(\d+\.\d+|\d+)'

    match = re.match(quantity_pattern, text)

    if not match:
        return 0.0, text

    # Handle range (e.g., "2-3")
    if match.group(1) and match.group(2):
        start = float(match.group(1))
        end = float(match.group(2))
        quantity = (start + end) / 2  # Use midpoint
        remaining = text[match.end():].strip()
        return quantity, remaining

    # Handle mixed number (e.g., "1 1/2")
    if match.group(3) and match.group(4):
        whole = float(match.group(3))
        fraction = _parse_fraction(match.group(4))
        quantity = whole + fraction
        remaining = text[match.end():].strip()
        return quantity, remaining

    # Handle fraction (e.g., "1/2")
    if match.group(5):
        quantity = _parse_fraction(match.group(5))
        remaining = text[match.end():].strip()
        return quantity, remaining

    # Handle simple number or decimal (e.g., "4" or "1.5")
    if match.group(6):
        quantity = float(match.group(6))
        remaining = text[match.end():].strip()
        return quantity, remaining

    return 0.0, text


def _extract_unit(text: str) -> tuple[str, str]:
    """
    Extract measurement unit from the beginning of the text.

    Args:
        text: Input text (after quantity extraction)

    Returns:
        Tuple of (unit, remaining_text)
        Returns ("", original_text) if no known unit found
    """
    text = text.strip()

    # Try to match known units at the start of the text
    # Use word boundary to avoid partial matches
    for unit in sorted(KNOWN_UNITS, key=len, reverse=True):  # Longest first to avoid partial matches
        # Case-insensitive pattern with word boundary
        pattern = r'^' + re.escape(unit) + r'\b'
        if re.match(pattern, text, re.IGNORECASE):
            matched_unit = text[:len(unit)]
            remaining = text[len(unit):].strip()
            return matched_unit, remaining

    return "", text


def _extract_preparation(text: str) -> tuple[str, str]:
    """
    Extract preparation instructions after a comma.

    Args:
        text: Input text

    Returns:
        Tuple of (ingredient_text, preparation)
        If comma found: splits at first comma
        If no comma: returns (text, "")
    """
    if ',' in text:
        parts = text.split(',', 1)
        ingredient = parts[0].strip()
        preparation = parts[1].strip()
        return ingredient, preparation

    return text, ""


def _is_optional(text: str, preparation: str) -> bool:
    """
    Detect if ingredient is marked as optional.

    Checks both the main text and preparation for optional markers.

    Args:
        text: Main ingredient text
        preparation: Preparation text

    Returns:
        True if optional marker found, False otherwise
    """
    combined = f"{text} {preparation}".lower()

    for marker in OPTIONAL_MARKERS:
        if marker in combined:
            return True

    return False


def parse_ingredient(raw: str) -> ParsedIngredient:
    """
    Parse a raw ingredient string into structured components.

    Decomposes ingredient strings like:
    - "4 oz Heirloom Grape Tomatoes" → qty=4, unit=oz, name=Tomatoes
    - "2 cloves garlic, minced" → qty=2, unit=clove, name=garlic, prep=minced
    - "Salt and pepper to taste" → qty=0, unit="", name=Salt and pepper, optional=True
    - "1/2 cup flour" → qty=0.5, unit=cup, name=flour
    - "1 1/2 cups milk" → qty=1.5, unit=cup, name=milk
    - "2-3 tbsp oil" → qty=2.5, unit=tbsp, name=oil

    Args:
        raw: Raw ingredient string from recipe-scrapers

    Returns:
        ParsedIngredient with all fields populated

    Raises:
        ValueError: If input exceeds maximum length (500 characters) - ReDoS protection

    Note:
        Never crashes - returns graceful fallback with full text as ingredient_name
        if parsing fails completely.
    """
    # Preserve original for debugging
    original = raw.strip()

    # Security: Input length validation to prevent ReDoS attacks
    # Recipe ingredient strings are typically < 100 chars; 500 is generous
    MAX_INGREDIENT_LENGTH = 500
    if len(original) > MAX_INGREDIENT_LENGTH:
        raise ValueError(
            f"Ingredient string exceeds maximum length of {MAX_INGREDIENT_LENGTH} characters "
            f"(got {len(original)}). This limit prevents ReDoS attacks."
        )

    if not original:
        return ParsedIngredient(
            quantity=0.0,
            unit="",
            ingredient_name="",
            preparation="",
            is_optional=False,
            raw_text=raw,
        )

    try:
        # Step 1: Normalize Unicode fractions
        text = _normalize_unicode_fractions(original)

        # Step 2: Extract quantity
        quantity, text = _extract_quantity(text)

        # Step 3: Extract unit
        unit, text = _extract_unit(text)

        # Step 4: Extract preparation (split on comma)
        text, preparation = _extract_preparation(text)

        # Step 5: Detect if optional
        is_optional = _is_optional(text, preparation)

        # Step 6: Remaining text is ingredient name
        ingredient_name = text.strip()

        # If we couldn't extract a name but have original text, use full text as name
        if not ingredient_name and original:
            ingredient_name = original

        return ParsedIngredient(
            quantity=quantity,
            unit=unit,
            ingredient_name=ingredient_name,
            preparation=preparation,
            is_optional=is_optional,
            raw_text=raw,
        )

    except Exception as e:
        # Log parsing failure for debuggability and parser improvement
        logger.warning(
            "Failed to parse ingredient string",
            extra={
                "raw_text": raw,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        # Graceful fallback: return unparsed with full text as ingredient_name
        return ParsedIngredient(
            quantity=0.0,
            unit="",
            ingredient_name=original,
            preparation="",
            is_optional=False,
            raw_text=raw,
        )
