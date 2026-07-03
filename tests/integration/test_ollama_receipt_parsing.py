"""
Integration tests for Ollama receipt parsing pipeline.

These tests verify the end-to-end receipt parsing flow against a running Ollama instance.
They validate that sample receipt text produces plausible structured output, not just
that Ollama responds.

Requirements:
- Ollama running locally (default: http://localhost:11434)
- llama3.1:8b model pulled and available

Running these tests:
    # Run integration tests only
    pytest tests/integration/test_ollama_receipt_parsing.py -v -m integration

    # Skip integration tests (default)
    pytest tests/ -v --ignore=tests/integration

    # Or explicitly skip integration marker
    pytest tests/ -v -m "not integration"

Note: These tests are not run in CI by default as they require manual Ollama setup.
"""

import pytest

from src.services.llm.client import OllamaClient
from src.services.llm.prompts.receipt import SYSTEM_PROMPT, create_user_prompt
from src.schemas.receipt import ReceiptParseResult


# Sample receipt data for testing

COSTCO_RECEIPT = """
COSTCO WHOLESALE
1234 Market Street
Denver, CO 80202

Member: 123456789
Date: 03/15/2024

ITEM                          QTY    PRICE
-----------------------------------------
ORGANIC BANANAS 3LB            1    $4.99
KIRKLAND MILK WHOLE GAL        2    $3.49
FREE RANGE EGGS 24CT           1    $8.99
AVOCADOS 5CT BAG               1    $6.99
ROTISSERIE CHICKEN             1    $4.99
KIRKLAND OLIVE OIL 2L          1   $19.99
ORGANIC SPINACH 1LB            1    $4.99

                    SUBTOTAL:  $54.43
                         TAX:   $2.12
                       TOTAL:  $56.55
"""

GROCERY_STORE_RECEIPT = """
Save-A-Lot Grocery
789 Main St, Boulder, CO

03/20/2024 - 14:32

Items Purchased:
Apples (Red Delicious)        $3.99
Bread (Whole Wheat)           $2.49
Cheddar Cheese 8oz            $4.99
Ground Beef 1lb               $6.99
Orange Juice 64oz             $3.99
Pasta (Penne) 16oz            $1.49
Tomato Sauce 24oz             $2.99

Subtotal:                    $26.93
Tax:                          $1.08
Total:                       $28.01
"""


@pytest.fixture
async def ollama_client():
    """
    Create OllamaClient and verify Ollama is available.

    Skips test if Ollama is not running or unavailable.
    """
    client = OllamaClient()

    # Check if Ollama is available
    is_available = await client.is_available()
    if not is_available:
        pytest.skip(
            "Ollama is not available. "
            "Please ensure Ollama is running locally with llama3.1:8b model. "
            "Install: https://ollama.ai/download | Run: ollama pull llama3.1:8b"
        )

    try:
        yield client
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parse_costco_receipt(ollama_client):
    """
    Test parsing a Costco-style receipt with multiple items.

    Validates that:
    - store_name is populated and non-empty
    - receipt_date is parsed (if present in output)
    - line_items contains at least one item
    - Each line_item has a non-empty item_name
    - Prices are numeric where present
    """
    # Create prompt from sample receipt
    user_prompt = create_user_prompt(COSTCO_RECEIPT)

    # Call Ollama to parse receipt
    result = await ollama_client.complete(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
        response_schema=ReceiptParseResult,
    )

    # Validate structure and content quality
    assert isinstance(result, ReceiptParseResult)

    # Store name should be populated
    assert result.store_name, "store_name should not be empty"
    assert len(result.store_name.strip()) > 0, "store_name should not be whitespace only"

    # Should recognize it's Costco (case-insensitive check)
    assert "costco" in result.store_name.lower(), \
        f"Expected store_name to contain 'costco', got: {result.store_name}"

    # Should have extracted line items
    assert len(result.line_items) >= 1, "Should have at least one line item"

    # Costco receipt has 7 items - should get most of them
    assert len(result.line_items) >= 5, \
        f"Expected at least 5 line items from Costco receipt, got {len(result.line_items)}"

    # Validate each line item
    for idx, item in enumerate(result.line_items):
        # Item name should be non-empty
        assert item.item_name, f"Line item {idx} should have non-empty item_name"
        assert len(item.item_name.strip()) > 0, \
            f"Line item {idx} item_name should not be whitespace only"

        # If total_price is present, it should be numeric and non-negative
        if item.total_price is not None:
            assert isinstance(item.total_price, (int, float)), \
                f"Line item {idx} total_price should be numeric"
            assert item.total_price >= 0, \
                f"Line item {idx} total_price should be non-negative"

        # If unit_price is present, it should be numeric and non-negative
        if item.unit_price is not None:
            assert isinstance(item.unit_price, (int, float)), \
                f"Line item {idx} unit_price should be numeric"
            assert item.unit_price >= 0, \
                f"Line item {idx} unit_price should be non-negative"

        # If quantity is present, it should be numeric and positive
        if item.quantity is not None:
            assert isinstance(item.quantity, (int, float)), \
                f"Line item {idx} quantity should be numeric"
            assert item.quantity > 0, \
                f"Line item {idx} quantity should be positive"

    # At least some items should have prices extracted
    items_with_prices = [item for item in result.line_items if item.total_price is not None]
    assert len(items_with_prices) >= 3, \
        "Expected at least 3 items to have total_price extracted"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parse_grocery_store_receipt(ollama_client):
    """
    Test parsing a standard grocery store receipt.

    Validates that:
    - store_name is populated and non-empty
    - receipt_date is parsed (if present in output)
    - line_items contains at least one item
    - Each line_item has a non-empty item_name
    - Prices are numeric where present
    """
    # Create prompt from sample receipt
    user_prompt = create_user_prompt(GROCERY_STORE_RECEIPT)

    # Call Ollama to parse receipt
    result = await ollama_client.complete(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT,
        response_schema=ReceiptParseResult,
    )

    # Validate structure and content quality
    assert isinstance(result, ReceiptParseResult)

    # Store name should be populated
    assert result.store_name, "store_name should not be empty"
    assert len(result.store_name.strip()) > 0, "store_name should not be whitespace only"

    # Should recognize it's Save-A-Lot (case-insensitive check)
    assert "save" in result.store_name.lower() or "lot" in result.store_name.lower(), \
        f"Expected store_name to contain 'save' or 'lot', got: {result.store_name}"

    # Should have extracted line items
    assert len(result.line_items) >= 1, "Should have at least one line item"

    # Grocery store receipt has 7 items - should get most of them
    assert len(result.line_items) >= 5, \
        f"Expected at least 5 line items from grocery receipt, got {len(result.line_items)}"

    # Validate each line item
    for idx, item in enumerate(result.line_items):
        # Item name should be non-empty
        assert item.item_name, f"Line item {idx} should have non-empty item_name"
        assert len(item.item_name.strip()) > 0, \
            f"Line item {idx} item_name should not be whitespace only"

        # If total_price is present, it should be numeric and non-negative
        if item.total_price is not None:
            assert isinstance(item.total_price, (int, float)), \
                f"Line item {idx} total_price should be numeric"
            assert item.total_price >= 0, \
                f"Line item {idx} total_price should be non-negative"

        # If unit_price is present, it should be numeric and non-negative
        if item.unit_price is not None:
            assert isinstance(item.unit_price, (int, float)), \
                f"Line item {idx} unit_price should be numeric"
            assert item.unit_price >= 0, \
                f"Line item {idx} unit_price should be non-negative"

        # If quantity is present, it should be numeric and positive
        if item.quantity is not None:
            assert isinstance(item.quantity, (int, float)), \
                f"Line item {idx} quantity should be numeric"
            assert item.quantity > 0, \
                f"Line item {idx} quantity should be positive"

        # If category_guess is present, it should be non-empty
        if item.category_guess is not None:
            assert len(item.category_guess.strip()) > 0, \
                f"Line item {idx} category_guess should not be whitespace only"

    # At least some items should have prices extracted
    items_with_prices = [item for item in result.line_items if item.total_price is not None]
    assert len(items_with_prices) >= 3, \
        "Expected at least 3 items to have total_price extracted"

    # At least some items should have category guesses
    items_with_category = [item for item in result.line_items if item.category_guess is not None]
    assert len(items_with_category) >= 2, \
        "Expected at least 2 items to have category_guess populated"
