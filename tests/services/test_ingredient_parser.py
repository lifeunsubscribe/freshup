"""
Unit tests for ingredient parser service.

Tests cover:
- Basic quantity/unit/name extraction
- Unicode fraction handling
- Mixed numbers and ranges
- Preparation extraction (comma-separated)
- Optional ingredient detection
- Real-world ingredient strings from HelloFresh and Kitchen Sanctuary
- Edge cases and graceful fallback
"""

import pytest
from src.services.ingredient_parser import (
    parse_ingredient,
    ParsedIngredient,
    _normalize_unicode_fractions,
    _parse_fraction,
    _extract_quantity,
    _extract_unit,
    _extract_preparation,
    _is_optional,
)


class TestNormalizeUnicodeFractions:
    """Tests for Unicode fraction normalization."""

    def test_common_fractions(self):
        """Test common Unicode fractions are converted correctly."""
        assert _normalize_unicode_fractions("½") == "1/2"
        assert _normalize_unicode_fractions("⅓") == "1/3"
        assert _normalize_unicode_fractions("¼") == "1/4"
        assert _normalize_unicode_fractions("¾") == "3/4"

    def test_fractions_in_text(self):
        """Test fractions embedded in ingredient strings."""
        assert _normalize_unicode_fractions("½ cup sugar") == "1/2 cup sugar"
        assert _normalize_unicode_fractions("2¼ cups flour") == "2 1/4 cups flour"

    def test_no_fractions(self):
        """Test text without Unicode fractions passes through unchanged."""
        text = "4 oz tomatoes"
        assert _normalize_unicode_fractions(text) == text


class TestParseFraction:
    """Tests for fraction parsing."""

    def test_simple_fractions(self):
        """Test simple fraction parsing."""
        assert _parse_fraction("1/2") == 0.5
        assert _parse_fraction("1/4") == 0.25
        assert _parse_fraction("3/4") == 0.75
        assert _parse_fraction("2/3") == pytest.approx(0.6667, rel=1e-3)

    def test_invalid_fraction(self):
        """Test invalid fraction raises ValueError."""
        with pytest.raises(ValueError):
            _parse_fraction("1/2/3")
        with pytest.raises(ValueError):
            _parse_fraction("invalid")

    def test_division_by_zero(self):
        """Test division by zero raises ValueError."""
        with pytest.raises(ValueError):
            _parse_fraction("1/0")


class TestExtractQuantity:
    """Tests for quantity extraction."""

    def test_simple_number(self):
        """Test simple integer quantity."""
        qty, remaining = _extract_quantity("4 oz tomatoes")
        assert qty == 4.0
        assert remaining == "oz tomatoes"

    def test_decimal_number(self):
        """Test decimal quantity."""
        qty, remaining = _extract_quantity("1.5 cups milk")
        assert qty == 1.5
        assert remaining == "cups milk"

    def test_fraction(self):
        """Test fraction quantity."""
        qty, remaining = _extract_quantity("1/2 cup flour")
        assert qty == 0.5
        assert remaining == "cup flour"

    def test_mixed_number(self):
        """Test mixed number (whole + fraction)."""
        qty, remaining = _extract_quantity("1 1/2 cups milk")
        assert qty == 1.5
        assert remaining == "cups milk"

    def test_range(self):
        """Test range returns midpoint."""
        qty, remaining = _extract_quantity("2-3 tbsp oil")
        assert qty == 2.5
        assert remaining == "tbsp oil"

    def test_no_quantity(self):
        """Test text without quantity."""
        qty, remaining = _extract_quantity("Salt and pepper to taste")
        assert qty == 0.0
        assert remaining == "Salt and pepper to taste"


class TestExtractUnit:
    """Tests for unit extraction."""

    def test_common_volume_units(self):
        """Test common volume unit extraction."""
        unit, remaining = _extract_unit("cup flour")
        assert unit.lower() == "cup"
        assert remaining == "flour"

        unit, remaining = _extract_unit("tbsp oil")
        assert unit.lower() == "tbsp"
        assert remaining == "oil"

        unit, remaining = _extract_unit("tsp vanilla")
        assert unit.lower() == "tsp"
        assert remaining == "vanilla"

    def test_common_weight_units(self):
        """Test common weight unit extraction."""
        unit, remaining = _extract_unit("oz tomatoes")
        assert unit.lower() == "oz"
        assert remaining == "tomatoes"

        unit, remaining = _extract_unit("lb beef")
        assert unit.lower() == "lb"
        assert remaining == "beef"

        unit, remaining = _extract_unit("g sugar")
        assert unit.lower() == "g"
        assert remaining == "sugar"

    def test_count_units(self):
        """Test count/discrete unit extraction."""
        unit, remaining = _extract_unit("cloves garlic")
        assert unit.lower() == "cloves"
        assert remaining == "garlic"

        unit, remaining = _extract_unit("bunch parsley")
        assert unit.lower() == "bunch"
        assert remaining == "parsley"

        unit, remaining = _extract_unit("pinch salt")
        assert unit.lower() == "pinch"
        assert remaining == "salt"

    def test_plural_units(self):
        """Test plural unit forms."""
        unit, remaining = _extract_unit("cups flour")
        assert unit.lower() == "cups"
        assert remaining == "flour"

        unit, remaining = _extract_unit("tablespoons butter")
        assert unit.lower() == "tablespoons"
        assert remaining == "butter"

    def test_no_unit(self):
        """Test text without recognized unit."""
        unit, remaining = _extract_unit("Heirloom Grape Tomatoes")
        assert unit == ""
        assert remaining == "Heirloom Grape Tomatoes"

    def test_case_insensitive(self):
        """Test unit matching is case-insensitive."""
        unit, remaining = _extract_unit("Cup flour")
        assert unit.lower() == "cup"
        assert remaining == "flour"

        unit, remaining = _extract_unit("OZ tomatoes")
        assert unit.lower() == "oz"
        assert remaining == "tomatoes"


class TestExtractPreparation:
    """Tests for preparation extraction."""

    def test_with_preparation(self):
        """Test extraction of preparation after comma."""
        ingredient, prep = _extract_preparation("garlic, minced")
        assert ingredient == "garlic"
        assert prep == "minced"

    def test_complex_preparation(self):
        """Test complex preparation instructions."""
        ingredient, prep = _extract_preparation("onion, finely diced")
        assert ingredient == "onion"
        assert prep == "finely diced"

    def test_no_preparation(self):
        """Test text without comma/preparation."""
        ingredient, prep = _extract_preparation("tomatoes")
        assert ingredient == "tomatoes"
        assert prep == ""

    def test_multiple_commas(self):
        """Test only splits on first comma."""
        ingredient, prep = _extract_preparation("garlic, minced, or sliced")
        assert ingredient == "garlic"
        assert prep == "minced, or sliced"


class TestIsOptional:
    """Tests for optional ingredient detection."""

    def test_to_taste_marker(self):
        """Test 'to taste' marker detection."""
        assert _is_optional("Salt and pepper", "to taste") is True
        assert _is_optional("Salt and pepper to taste", "") is True

    def test_optional_marker(self):
        """Test 'optional' marker detection."""
        assert _is_optional("Parsley", "optional") is True
        assert _is_optional("Parsley (optional)", "") is True

    def test_if_desired_marker(self):
        """Test 'if desired' marker detection."""
        assert _is_optional("Red pepper flakes", "if desired") is True

    def test_as_needed_marker(self):
        """Test 'as needed' marker detection."""
        assert _is_optional("Water", "as needed") is True

    def test_for_garnish_marker(self):
        """Test 'for garnish' marker detection."""
        assert _is_optional("Fresh herbs", "for garnish") is True

    def test_not_optional(self):
        """Test non-optional ingredients."""
        assert _is_optional("garlic", "minced") is False
        assert _is_optional("tomatoes", "") is False


class TestParseIngredient:
    """Tests for full ingredient parsing."""

    def test_simple_quantity_unit_name(self):
        """Test: '4 oz Heirloom Grape Tomatoes'"""
        result = parse_ingredient("4 oz Heirloom Grape Tomatoes")
        assert result['quantity'] == 4.0
        assert result['unit'].lower() == 'oz'
        assert result['ingredient_name'] == 'Heirloom Grape Tomatoes'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "4 oz Heirloom Grape Tomatoes"

    def test_with_preparation(self):
        """Test: '2 cloves garlic, minced'"""
        result = parse_ingredient("2 cloves garlic, minced")
        assert result['quantity'] == 2.0
        assert result['unit'].lower() == 'cloves'
        assert result['ingredient_name'] == 'garlic'
        assert result['preparation'] == 'minced'
        assert result['is_optional'] is False
        assert result['raw_text'] == "2 cloves garlic, minced"

    def test_optional_to_taste(self):
        """Test: 'Salt and pepper to taste'"""
        result = parse_ingredient("Salt and pepper to taste")
        assert result['quantity'] == 0.0
        assert result['unit'] == ''
        assert result['ingredient_name'] == 'Salt and pepper to taste'
        assert result['preparation'] == ''
        assert result['is_optional'] is True
        assert result['raw_text'] == "Salt and pepper to taste"

    def test_fraction_quantity(self):
        """Test: '1/2 cup flour'"""
        result = parse_ingredient("1/2 cup flour")
        assert result['quantity'] == 0.5
        assert result['unit'].lower() == 'cup'
        assert result['ingredient_name'] == 'flour'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "1/2 cup flour"

    def test_mixed_number_quantity(self):
        """Test: '1 1/2 cups milk'"""
        result = parse_ingredient("1 1/2 cups milk")
        assert result['quantity'] == 1.5
        assert result['unit'].lower() == 'cups'
        assert result['ingredient_name'] == 'milk'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "1 1/2 cups milk"

    def test_range_quantity(self):
        """Test: '2-3 tbsp oil' (should use midpoint)"""
        result = parse_ingredient("2-3 tbsp oil")
        assert result['quantity'] == 2.5
        assert result['unit'].lower() == 'tbsp'
        assert result['ingredient_name'] == 'oil'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "2-3 tbsp oil"

    def test_unicode_fraction(self):
        """Test: '½ cup sugar' (Unicode fraction)"""
        result = parse_ingredient("½ cup sugar")
        assert result['quantity'] == 0.5
        assert result['unit'].lower() == 'cup'
        assert result['ingredient_name'] == 'sugar'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "½ cup sugar"

    def test_unicode_three_quarters(self):
        """Test: '¾ tsp salt' (Unicode fraction)"""
        result = parse_ingredient("¾ tsp salt")
        assert result['quantity'] == 0.75
        assert result['unit'].lower() == 'tsp'
        assert result['ingredient_name'] == 'salt'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "¾ tsp salt"

    def test_empty_string(self):
        """Test empty string input."""
        result = parse_ingredient("")
        assert result['quantity'] == 0.0
        assert result['unit'] == ''
        assert result['ingredient_name'] == ''
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == ""

    def test_whitespace_only(self):
        """Test whitespace-only input."""
        result = parse_ingredient("   ")
        assert result['quantity'] == 0.0
        assert result['unit'] == ''
        assert result['ingredient_name'] == ''
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "   "

    def test_no_quantity_or_unit(self):
        """Test ingredient with no quantity or unit."""
        result = parse_ingredient("Fresh basil leaves")
        assert result['quantity'] == 0.0
        assert result['unit'] == ''
        assert result['ingredient_name'] == 'Fresh basil leaves'
        assert result['preparation'] == ''
        assert result['is_optional'] is False
        assert result['raw_text'] == "Fresh basil leaves"


class TestRealWorldIngredients:
    """Tests using real ingredient strings from HelloFresh and Kitchen Sanctuary."""

    def test_hellofresh_tomatoes(self):
        """HelloFresh: Heirloom grape tomatoes."""
        result = parse_ingredient("4 oz Heirloom Grape Tomatoes")
        assert result['quantity'] == 4.0
        assert result['unit'].lower() == 'oz'
        assert 'Tomatoes' in result['ingredient_name']

    def test_hellofresh_garlic(self):
        """HelloFresh: Garlic with preparation."""
        result = parse_ingredient("2 Cloves Garlic, minced")
        assert result['quantity'] == 2.0
        assert result['unit'].lower() == 'cloves'
        assert result['ingredient_name'].lower() == 'garlic'
        assert result['preparation'] == 'minced'

    def test_hellofresh_butter(self):
        """HelloFresh: Butter with mixed number."""
        result = parse_ingredient("1 1/2 tbsp Butter")
        assert result['quantity'] == 1.5
        assert result['unit'].lower() == 'tbsp'
        assert 'Butter' in result['ingredient_name']

    def test_hellofresh_stock(self):
        """HelloFresh: Stock concentrate."""
        result = parse_ingredient("1 Chicken Stock Concentrate")
        assert result['quantity'] == 1.0
        assert 'Stock' in result['ingredient_name'] or 'Chicken' in result['ingredient_name']

    def test_kitchen_sanctuary_olive_oil(self):
        """Kitchen Sanctuary: Olive oil with range."""
        result = parse_ingredient("2-3 tablespoons olive oil")
        assert result['quantity'] == 2.5
        assert result['unit'].lower() == 'tablespoons'
        assert 'olive oil' in result['ingredient_name']

    def test_kitchen_sanctuary_onion(self):
        """Kitchen Sanctuary: Onion with preparation."""
        result = parse_ingredient("1 large onion, finely diced")
        assert result['quantity'] == 1.0
        assert result['unit'].lower() == 'large'
        assert 'onion' in result['ingredient_name']
        assert result['preparation'] == 'finely diced'

    def test_kitchen_sanctuary_paprika(self):
        """Kitchen Sanctuary: Spice with fraction."""
        result = parse_ingredient("1/2 teaspoon smoked paprika")
        assert result['quantity'] == 0.5
        assert result['unit'].lower() == 'teaspoon'
        assert 'paprika' in result['ingredient_name']

    def test_kitchen_sanctuary_bay_leaves(self):
        """Kitchen Sanctuary: Bay leaves."""
        result = parse_ingredient("2 bay leaves")
        assert result['quantity'] == 2.0
        assert result['unit'].lower() == 'bay'
        assert 'leaves' in result['ingredient_name']

    def test_kitchen_sanctuary_fresh_parsley(self):
        """Kitchen Sanctuary: Fresh herbs with preparation."""
        result = parse_ingredient("Fresh parsley, chopped, to garnish")
        assert 'parsley' in result['ingredient_name'].lower() or 'parsley' in result['preparation'].lower()
        # Should detect 'chopped, to garnish' as preparation or 'to garnish' could mark it optional

    def test_hellofresh_cheese(self):
        """HelloFresh: Shredded cheese."""
        result = parse_ingredient("1/4 cup Shredded Parmesan Cheese")
        assert result['quantity'] == 0.25
        assert result['unit'].lower() == 'cup'
        assert 'Cheese' in result['ingredient_name'] or 'Parmesan' in result['ingredient_name']

    def test_hellofresh_sour_cream(self):
        """HelloFresh: Sour cream."""
        result = parse_ingredient("4 tbsp Sour Cream")
        assert result['quantity'] == 4.0
        assert result['unit'].lower() == 'tbsp'
        assert 'Sour Cream' in result['ingredient_name']

    def test_kitchen_sanctuary_coconut_milk(self):
        """Kitchen Sanctuary: Canned ingredient."""
        result = parse_ingredient("1 can (400ml) coconut milk")
        assert result['quantity'] == 1.0
        assert result['unit'].lower() == 'can'
        assert 'coconut milk' in result['ingredient_name']

    def test_kitchen_sanctuary_ginger(self):
        """Kitchen Sanctuary: Ginger with measurement."""
        result = parse_ingredient("1 inch fresh ginger, grated")
        assert result['quantity'] == 1.0
        assert result['unit'].lower() == 'inch'
        assert 'ginger' in result['ingredient_name']
        assert result['preparation'] == 'grated'

    def test_hellofresh_pasta(self):
        """HelloFresh: Pasta in ounces."""
        result = parse_ingredient("6 oz Rigatoni Pasta")
        assert result['quantity'] == 6.0
        assert result['unit'].lower() == 'oz'
        assert 'Pasta' in result['ingredient_name'] or 'Rigatoni' in result['ingredient_name']

    def test_kitchen_sanctuary_chicken(self):
        """Kitchen Sanctuary: Chicken with weight."""
        result = parse_ingredient("1 lb boneless chicken thighs, diced")
        assert result['quantity'] == 1.0
        assert result['unit'].lower() == 'lb'
        assert 'chicken' in result['ingredient_name']
        assert result['preparation'] == 'diced'

    def test_hellofresh_scallions(self):
        """HelloFresh: Scallions."""
        result = parse_ingredient("2 Scallions")
        assert result['quantity'] == 2.0
        # No unit, but that's okay - quantity is extracted
        assert 'Scallions' in result['ingredient_name']

    def test_kitchen_sanctuary_black_pepper(self):
        """Kitchen Sanctuary: Black pepper optional."""
        result = parse_ingredient("Black pepper, to taste")
        assert result['is_optional'] is True
        assert 'pepper' in result['ingredient_name'].lower()

    def test_hellofresh_lemon(self):
        """HelloFresh: Lemon."""
        result = parse_ingredient("1 Lemon")
        assert result['quantity'] == 1.0
        assert 'Lemon' in result['ingredient_name']

    def test_kitchen_sanctuary_curry_paste(self):
        """Kitchen Sanctuary: Curry paste with range and unit."""
        result = parse_ingredient("2-3 tbsp red curry paste")
        assert result['quantity'] == 2.5
        assert result['unit'].lower() == 'tbsp'
        assert 'curry paste' in result['ingredient_name']

    def test_unicode_fraction_mixed(self):
        """Test Unicode fraction in real context."""
        result = parse_ingredient("2¼ cups all-purpose flour")
        assert result['quantity'] == 2.25
        assert result['unit'].lower() == 'cups'
        assert 'flour' in result['ingredient_name']


class TestGracefulFallback:
    """Tests for graceful fallback behavior."""

    def test_preserves_raw_text(self):
        """Ensure raw_text is always preserved."""
        original = "Some weird ingredient format!!!"
        result = parse_ingredient(original)
        assert result['raw_text'] == original

    def test_malformed_never_crashes(self):
        """Test that malformed input never crashes."""
        test_cases = [
            "!!!",
            "1/0 cups flour",  # Division by zero
            "@#$%^&*()",
            "🍕🍔🍟",  # Emojis
            "a b c d e f g h i j k l m n o p",  # Random text
        ]
        for test_input in test_cases:
            result = parse_ingredient(test_input)
            assert result['raw_text'] == test_input
            assert isinstance(result['quantity'], float)
            assert isinstance(result['unit'], str)
            assert isinstance(result['ingredient_name'], str)

    def test_complex_unparseable_returns_full_text(self):
        """Test that complex unparseable input returns full text as ingredient_name."""
        result = parse_ingredient("???")
        assert result['ingredient_name'] == "???"
        assert result['quantity'] == 0.0
        assert result['unit'] == ""
