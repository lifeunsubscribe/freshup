"""
Unit tests for receipt service mapping functions.

Tests receipt-to-inventory mapping logic including category mapping,
unit parsing, storage location inference, and edge case handling.
"""

import pytest
from datetime import date

from src.services.receipt_service import (
    map_receipt_to_inventory,
    map_category_guess_to_enum,
    infer_storage_location,
)
from src.schemas.receipt import ReceiptParseResult, ReceiptLineItem
from src.db.models.inventory_item import Category, UnitType, StorageLocation


class TestMapCategoryGuessToEnum:
    """Test category_guess string mapping to Category enum."""

    def test_exact_match_produce(self):
        """Test exact match for 'produce' category."""
        result = map_category_guess_to_enum("produce")
        assert result == Category.produce

    def test_exact_match_protein(self):
        """Test exact match for 'protein' category."""
        result = map_category_guess_to_enum("protein")
        assert result == Category.protein

    def test_exact_match_dairy(self):
        """Test exact match for 'dairy' category."""
        result = map_category_guess_to_enum("dairy")
        assert result == Category.dairy

    def test_exact_match_frozen(self):
        """Test exact match for 'frozen' category."""
        result = map_category_guess_to_enum("frozen")
        assert result == Category.frozen

    def test_exact_match_grain(self):
        """Test exact match for 'grain' category."""
        result = map_category_guess_to_enum("grain")
        assert result == Category.grain

    def test_exact_match_pantry_staple(self):
        """Test exact match for 'pantry_staple' category."""
        result = map_category_guess_to_enum("pantry_staple")
        assert result == Category.pantry_staple

    def test_case_insensitive_matching(self):
        """Test case-insensitive category matching."""
        assert map_category_guess_to_enum("PRODUCE") == Category.produce
        assert map_category_guess_to_enum("Dairy") == Category.dairy
        assert map_category_guess_to_enum("FrOzEn") == Category.frozen

    def test_whitespace_handling(self):
        """Test category matching with leading/trailing whitespace."""
        assert map_category_guess_to_enum("  produce  ") == Category.produce
        assert map_category_guess_to_enum("\tdairy\n") == Category.dairy

    def test_alias_matching_fruits(self):
        """Test alias matching for produce variations."""
        assert map_category_guess_to_enum("fruit") == Category.produce
        assert map_category_guess_to_enum("fruits") == Category.produce
        assert map_category_guess_to_enum("vegetable") == Category.produce
        assert map_category_guess_to_enum("vegetables") == Category.produce
        assert map_category_guess_to_enum("veggies") == Category.produce

    def test_alias_matching_meat(self):
        """Test alias matching for protein variations."""
        assert map_category_guess_to_enum("meat") == Category.protein
        assert map_category_guess_to_enum("chicken") == Category.protein
        assert map_category_guess_to_enum("beef") == Category.protein
        assert map_category_guess_to_enum("seafood") == Category.protein

    def test_alias_matching_grains(self):
        """Test alias matching for grain variations."""
        assert map_category_guess_to_enum("bread") == Category.grain
        assert map_category_guess_to_enum("pasta") == Category.grain
        assert map_category_guess_to_enum("rice") == Category.grain

    def test_alias_matching_beverages(self):
        """Test alias matching for beverage variations."""
        assert map_category_guess_to_enum("beverage") == Category.beverage
        assert map_category_guess_to_enum("drink") == Category.beverage
        assert map_category_guess_to_enum("soda") == Category.beverage
        assert map_category_guess_to_enum("juice") == Category.beverage

    def test_null_category_defaults_to_other(self):
        """Test null category_guess defaults to 'other'."""
        result = map_category_guess_to_enum(None)
        assert result == Category.other

    def test_empty_string_defaults_to_other(self):
        """Test empty string category_guess defaults to 'other'."""
        result = map_category_guess_to_enum("")
        assert result == Category.other

    def test_whitespace_only_defaults_to_other(self):
        """Test whitespace-only category_guess defaults to 'other'."""
        result = map_category_guess_to_enum("   ")
        assert result == Category.other

    def test_unrecognized_category_defaults_to_other(self):
        """Test unrecognized category_guess defaults to 'other'."""
        result = map_category_guess_to_enum("unknown_category_xyz")
        assert result == Category.other


class TestInferStorageLocation:
    """Test storage location inference from category."""

    def test_produce_infers_fridge(self):
        """Test produce category infers fridge storage."""
        result = infer_storage_location(Category.produce)
        assert result == StorageLocation.fridge

    def test_dairy_infers_fridge(self):
        """Test dairy category infers fridge storage."""
        result = infer_storage_location(Category.dairy)
        assert result == StorageLocation.fridge

    def test_frozen_infers_freezer(self):
        """Test frozen category infers freezer storage."""
        result = infer_storage_location(Category.frozen)
        assert result == StorageLocation.freezer

    def test_pantry_staple_infers_pantry(self):
        """Test pantry_staple category infers pantry storage."""
        result = infer_storage_location(Category.pantry_staple)
        assert result == StorageLocation.pantry

    def test_grain_infers_pantry(self):
        """Test grain category infers pantry storage."""
        result = infer_storage_location(Category.grain)
        assert result == StorageLocation.pantry

    def test_protein_infers_pantry(self):
        """Test protein category infers pantry storage (default)."""
        # Note: Fresh protein should go to fridge, but without more context
        # we default to pantry. Users can override during confirmation.
        result = infer_storage_location(Category.protein)
        assert result == StorageLocation.pantry

    def test_snack_infers_pantry(self):
        """Test snack category infers pantry storage."""
        result = infer_storage_location(Category.snack)
        assert result == StorageLocation.pantry

    def test_beverage_infers_pantry(self):
        """Test beverage category infers pantry storage (default)."""
        result = infer_storage_location(Category.beverage)
        assert result == StorageLocation.pantry

    def test_other_infers_pantry(self):
        """Test 'other' category infers pantry storage (default)."""
        result = infer_storage_location(Category.other)
        assert result == StorageLocation.pantry


class TestMapReceiptToInventory:
    """Test complete receipt-to-inventory mapping pipeline."""

    def test_happy_path_single_item(self):
        """Test mapping single line item with all fields populated."""
        parse_result = ReceiptParseResult(
            store_name="Costco",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Organic Bananas",
                    quantity=3.0,
                    unit_price=0.99,
                    total_price=2.97,
                    category_guess="produce"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        candidate = candidates[0]

        assert candidate.name == "Organic Bananas"
        assert candidate.quantity == 3.0
        assert candidate.unit == UnitType.count.value
        assert candidate.category == Category.produce.value
        assert candidate.storage_location == StorageLocation.fridge.value
        assert candidate.price == 2.97

    def test_happy_path_multiple_items(self):
        """Test mapping multiple line items with different categories."""
        parse_result = ReceiptParseResult(
            store_name="Whole Foods",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Organic Milk",
                    quantity=1.0,
                    total_price=5.99,
                    category_guess="dairy"
                ),
                ReceiptLineItem(
                    item_name="Frozen Pizza",
                    quantity=2.0,
                    total_price=12.99,
                    category_guess="frozen"
                ),
                ReceiptLineItem(
                    item_name="Pasta",
                    quantity=1.0,
                    total_price=3.49,
                    category_guess="grain"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 3

        # Check dairy item
        assert candidates[0].name == "Organic Milk"
        assert candidates[0].category == Category.dairy.value
        assert candidates[0].storage_location == StorageLocation.fridge.value

        # Check frozen item
        assert candidates[1].name == "Frozen Pizza"
        assert candidates[1].category == Category.frozen.value
        assert candidates[1].storage_location == StorageLocation.freezer.value

        # Check grain item
        assert candidates[2].name == "Pasta"
        assert candidates[2].category == Category.grain.value
        assert candidates[2].storage_location == StorageLocation.pantry.value

    def test_null_quantity_defaults_to_one(self):
        """Test null quantity defaults to 1.0."""
        parse_result = ReceiptParseResult(
            store_name="Target",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Mystery Item",
                    quantity=None,  # Null quantity
                    total_price=9.99,
                    category_guess="other"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        assert candidates[0].quantity == 1.0

    def test_null_category_defaults_to_other(self):
        """Test null category_guess defaults to 'other' category."""
        parse_result = ReceiptParseResult(
            store_name="CVS",
            receipt_date=None,
            line_items=[
                ReceiptLineItem(
                    item_name="Unknown Product",
                    quantity=1.0,
                    total_price=7.49,
                    category_guess=None  # Null category
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        assert candidates[0].category == Category.other.value
        assert candidates[0].storage_location == StorageLocation.pantry.value

    def test_unrecognized_category_defaults_to_other(self):
        """Test unrecognized category_guess defaults to 'other'."""
        parse_result = ReceiptParseResult(
            store_name="Random Store",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Weird Item",
                    quantity=1.0,
                    total_price=4.99,
                    category_guess="completely_unknown_category_xyz"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        assert candidates[0].category == Category.other.value
        assert candidates[0].storage_location == StorageLocation.pantry.value

    def test_null_price_is_preserved(self):
        """Test null price is preserved in candidate (nullable field)."""
        parse_result = ReceiptParseResult(
            store_name="Trader Joe's",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Free Sample",
                    quantity=1.0,
                    total_price=None,  # Null price
                    category_guess="snack"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        assert candidates[0].price is None

    def test_all_units_default_to_count(self):
        """Test all items default to 'count' unit."""
        parse_result = ReceiptParseResult(
            store_name="Safeway",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(item_name="Item 1", quantity=1.0, category_guess="produce"),
                ReceiptLineItem(item_name="Item 2", quantity=2.0, category_guess="dairy"),
                ReceiptLineItem(item_name="Item 3", quantity=3.0, category_guess="frozen"),
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert all(c.unit == UnitType.count.value for c in candidates)

    def test_category_alias_mapping_in_full_pipeline(self):
        """Test category alias mapping works in full pipeline."""
        parse_result = ReceiptParseResult(
            store_name="Kroger",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(item_name="Apples", quantity=5.0, category_guess="fruit"),
                ReceiptLineItem(item_name="Chicken Breast", quantity=2.0, category_guess="meat"),
                ReceiptLineItem(item_name="Sourdough Bread", quantity=1.0, category_guess="bread"),
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        # Check alias mappings
        assert candidates[0].category == Category.produce.value  # fruit → produce
        assert candidates[1].category == Category.protein.value  # meat → protein
        assert candidates[2].category == Category.grain.value    # bread → grain

    def test_empty_line_items_list(self):
        """Test mapping empty line items list returns empty candidates."""
        # Note: ReceiptParseResult schema requires min_length=1 for line_items,
        # so this test would fail validation. Testing the function behavior directly.
        parse_result = ReceiptParseResult(
            store_name="Empty Store",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(item_name="Dummy", quantity=1.0, category_guess="other")
            ]
        )
        # Manually set to empty to test function behavior
        parse_result.line_items = []

        candidates = map_receipt_to_inventory(parse_result)

        assert candidates == []

    def test_edge_case_very_large_quantity(self):
        """Test handling very large quantities."""
        parse_result = ReceiptParseResult(
            store_name="Bulk Store",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Bulk Rice",
                    quantity=9999.99,
                    total_price=299.99,
                    category_guess="grain"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        assert candidates[0].quantity == 9999.99

    def test_edge_case_fractional_quantity(self):
        """Test handling fractional quantities."""
        parse_result = ReceiptParseResult(
            store_name="Deli",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(
                    item_name="Sliced Turkey",
                    quantity=0.5,
                    total_price=4.99,
                    category_guess="protein"
                )
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert len(candidates) == 1
        assert candidates[0].quantity == 0.5

    def test_case_insensitive_category_in_pipeline(self):
        """Test case-insensitive category matching in full pipeline."""
        parse_result = ReceiptParseResult(
            store_name="Mixed Case Store",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(item_name="Item 1", quantity=1.0, category_guess="PRODUCE"),
                ReceiptLineItem(item_name="Item 2", quantity=1.0, category_guess="Dairy"),
                ReceiptLineItem(item_name="Item 3", quantity=1.0, category_guess="fRoZeN"),
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        assert candidates[0].category == Category.produce.value
        assert candidates[1].category == Category.dairy.value
        assert candidates[2].category == Category.frozen.value

    def test_storage_inference_for_all_categories(self):
        """Test storage location inference for comprehensive category coverage."""
        parse_result = ReceiptParseResult(
            store_name="Comprehensive Store",
            receipt_date=date(2026, 4, 4),
            line_items=[
                ReceiptLineItem(item_name="Lettuce", quantity=1.0, category_guess="produce"),
                ReceiptLineItem(item_name="Cheese", quantity=1.0, category_guess="dairy"),
                ReceiptLineItem(item_name="Ice Cream", quantity=1.0, category_guess="frozen"),
                ReceiptLineItem(item_name="Crackers", quantity=1.0, category_guess="snack"),
                ReceiptLineItem(item_name="Soy Sauce", quantity=1.0, category_guess="condiment"),
                ReceiptLineItem(item_name="Coffee", quantity=1.0, category_guess="beverage"),
                ReceiptLineItem(item_name="Oregano", quantity=1.0, category_guess="spice"),
                ReceiptLineItem(item_name="Flour", quantity=1.0, category_guess="baking"),
            ]
        )

        candidates = map_receipt_to_inventory(parse_result)

        # Verify storage locations
        assert candidates[0].storage_location == StorageLocation.fridge.value   # produce
        assert candidates[1].storage_location == StorageLocation.fridge.value   # dairy
        assert candidates[2].storage_location == StorageLocation.freezer.value  # frozen
        assert candidates[3].storage_location == StorageLocation.pantry.value   # snack
        assert candidates[4].storage_location == StorageLocation.pantry.value   # condiment
        assert candidates[5].storage_location == StorageLocation.pantry.value   # beverage
        assert candidates[6].storage_location == StorageLocation.pantry.value   # spice
        assert candidates[7].storage_location == StorageLocation.pantry.value   # baking
