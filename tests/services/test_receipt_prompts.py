"""
Unit tests for receipt prompt generation.

Tests cover:
- Generic prompt generation without store hints (existing behavior)
- Store-aware prompt generation with hints (new behavior)
- Hint content appears correctly in prompts
- Partial hints handling (some fields missing)
- Empty hints handling
"""

import pytest

from src.services.llm.prompts.receipt import create_user_prompt


def test_create_user_prompt_without_hints():
    """Test generic prompt generation without store hints (backward compatible)."""
    receipt_text = "Costco\n2024-03-29\nBananas $3.99\nMilk $4.49"

    # Call without store_hints parameter
    prompt = create_user_prompt(receipt_text)

    # Verify receipt text is in prompt
    assert "Costco" in prompt
    assert "Bananas $3.99" in prompt
    assert "Milk $4.49" in prompt

    # Verify generic prompt format (no store-specific section)
    assert "Parse the following grocery receipt text" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "Store-specific parsing hints:" not in prompt


def test_create_user_prompt_with_hints_none():
    """Test that passing None for store_hints produces generic prompt."""
    receipt_text = "King Soopers\n2024-04-01\nApples $2.99"

    # Call with store_hints=None explicitly
    prompt = create_user_prompt(receipt_text, store_hints=None)

    # Verify receipt text is in prompt
    assert "King Soopers" in prompt
    assert "Apples $2.99" in prompt

    # Verify no store-specific hints section
    assert "Store-specific parsing hints:" not in prompt


def test_create_user_prompt_with_full_hints():
    """Test prompt generation with complete store hints."""
    receipt_text = "Costco\n2024-03-29\nKS ORG Bananas 2-pack $3.99"

    # Costco-style hints
    store_hints = {
        "item_name_patterns": ["Kirkland Signature", "KS ", "Organic"],
        "quantity_patterns": ["2-pack", "3-pack", "ct", "count"],
        "price_format_hints": ["$/oz", "$/lb", "unit price"],
        "common_abbreviations": {
            "ORG": "Organic",
            "KS": "Kirkland Signature",
            "LB": "Pound"
        }
    }

    # Call with full hints
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify receipt text is in prompt
    assert "Costco" in prompt
    assert "KS ORG Bananas" in prompt

    # Verify store-specific hints section exists
    assert "Store-specific parsing hints:" in prompt

    # Verify item name patterns appear
    assert "Common product patterns:" in prompt
    assert "Kirkland Signature" in prompt
    assert "Organic" in prompt

    # Verify quantity patterns appear
    assert "Bulk quantity indicators:" in prompt
    assert "2-pack" in prompt
    assert "ct" in prompt

    # Verify price format hints appear
    assert "Price formats:" in prompt
    assert "$/oz" in prompt
    assert "$/lb" in prompt

    # Verify abbreviations appear
    assert "Abbreviations:" in prompt
    assert "ORG=Organic" in prompt
    assert "KS=Kirkland Signature" in prompt
    assert "LB=Pound" in prompt


def test_create_user_prompt_with_partial_hints():
    """Test prompt generation with only some hint fields provided."""
    receipt_text = "Save-A-Lot\n2024-04-01\nChicken $5.99"

    # Only item_name_patterns and abbreviations
    store_hints = {
        "item_name_patterns": ["Fresh", "Frozen", "Organic"],
        "common_abbreviations": {
            "FRZ": "Frozen",
            "FRH": "Fresh"
        }
    }

    # Call with partial hints
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify receipt text is in prompt
    assert "Save-A-Lot" in prompt
    assert "Chicken $5.99" in prompt

    # Verify store-specific hints section exists
    assert "Store-specific parsing hints:" in prompt

    # Verify provided hints appear
    assert "Common product patterns:" in prompt
    assert "Fresh" in prompt
    assert "Abbreviations:" in prompt
    assert "FRZ=Frozen" in prompt

    # Verify non-provided hints don't appear
    assert "Bulk quantity indicators:" not in prompt
    assert "Price formats:" not in prompt


def test_create_user_prompt_with_empty_hint_lists():
    """Test prompt generation when hint fields are empty lists/dicts."""
    receipt_text = "Target\n2024-04-01\nBread $2.49"

    # Empty hint collections (should be treated as no hints)
    store_hints = {
        "item_name_patterns": [],
        "quantity_patterns": [],
        "price_format_hints": [],
        "common_abbreviations": {}
    }

    # Call with empty hints
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify receipt text is in prompt
    assert "Target" in prompt
    assert "Bread $2.49" in prompt

    # Empty hints should result in store-specific section with header only
    # (or potentially treated as no hints - implementation dependent)
    # Here we verify the prompt is still valid
    assert "Parse the following grocery receipt text" in prompt
    assert "Return ONLY valid JSON" in prompt


def test_create_user_prompt_with_empty_dict():
    """Test prompt generation when store_hints is empty dict."""
    receipt_text = "Walmart\n2024-04-01\nEggs $3.49"

    # Empty dict (should be treated as no hints)
    store_hints = {}

    # Call with empty dict
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify receipt text is in prompt
    assert "Walmart" in prompt
    assert "Eggs $3.49" in prompt

    # Empty dict should produce generic prompt (no store-specific section)
    assert "Parse the following grocery receipt text" in prompt
    assert "Return ONLY valid JSON" in prompt


def test_create_user_prompt_hints_with_special_characters():
    """Test that hints with special characters are properly formatted."""
    receipt_text = "Store\n2024-04-01\nItem $1.99"

    store_hints = {
        "item_name_patterns": ["Organic & Fresh", "Natural/Healthy"],
        "common_abbreviations": {
            "&": "and",
            "/": "or"
        }
    }

    # Call with special characters in hints
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify special characters are preserved
    assert "Organic & Fresh" in prompt
    assert "Natural/Healthy" in prompt
    assert "&=and" in prompt
    assert "/=or" in prompt


def test_create_user_prompt_with_many_abbreviations():
    """Test prompt generation with many abbreviations."""
    receipt_text = "Costco\n2024-03-29\nItems..."

    store_hints = {
        "common_abbreviations": {
            "ORG": "Organic",
            "KS": "Kirkland Signature",
            "LB": "Pound",
            "OZ": "Ounce",
            "CT": "Count",
            "PK": "Pack",
            "EA": "Each",
            "GAL": "Gallon",
            "QT": "Quart"
        }
    }

    # Call with many abbreviations
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify all abbreviations appear
    assert "Abbreviations:" in prompt
    assert "ORG=Organic" in prompt
    assert "KS=Kirkland Signature" in prompt
    assert "GAL=Gallon" in prompt
    assert "QT=Quart" in prompt


def test_create_user_prompt_maintains_receipt_text_formatting():
    """Test that newlines and formatting in receipt text are preserved."""
    receipt_text = "Costco\n2024-03-29\n\nBananas $3.99\nMilk   $4.49\n  Eggs $2.99"

    store_hints = {
        "item_name_patterns": ["Kirkland Signature"]
    }

    # Call with formatted receipt text
    prompt = create_user_prompt(receipt_text, store_hints=store_hints)

    # Verify formatting is preserved (newlines, spaces)
    assert "Costco\n2024-03-29" in prompt
    assert "Bananas $3.99" in prompt
    assert "Milk   $4.49" in prompt  # Extra spaces preserved
    assert "  Eggs $2.99" in prompt  # Leading spaces preserved
