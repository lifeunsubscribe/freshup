"""
Test that sentinel constants are properly exported from the services module.

This test verifies that the public API exports work correctly, ensuring
external code can import the sentinel constant and helper function without
accessing internal implementation details.
"""


def test_sentinel_constant_exported_from_services():
    """Test that UNPARSEABLE_QUANTITY_SENTINEL is exported from src.services."""
    from src.services import UNPARSEABLE_QUANTITY_SENTINEL

    assert UNPARSEABLE_QUANTITY_SENTINEL == 0.001


def test_is_unparseable_quantity_exported_from_services():
    """Test that is_unparseable_quantity is exported from src.services."""
    from src.services import is_unparseable_quantity

    # Test with exact sentinel value
    assert is_unparseable_quantity(0.001) is True

    # Test with value very close to sentinel (within tolerance)
    assert is_unparseable_quantity(0.00105) is True

    # Test with non-sentinel value
    assert is_unparseable_quantity(0.125) is False

    # Test with regular quantity
    assert is_unparseable_quantity(1.0) is False


def test_exports_match_import_service():
    """Verify that exported values match the original import_service values."""
    from src.services import UNPARSEABLE_QUANTITY_SENTINEL as exported_constant
    from src.services import is_unparseable_quantity as exported_function
    from src.services.import_service import (
        UNPARSEABLE_QUANTITY_SENTINEL as original_constant,
        is_unparseable_quantity as original_function,
    )

    # Constants should be identical
    assert exported_constant == original_constant
    assert exported_constant is original_constant

    # Functions should be the same reference
    assert exported_function is original_function


def test_all_exports_defined():
    """Test that __all__ is properly defined with expected exports."""
    from src.services import __all__

    expected_exports = ["UNPARSEABLE_QUANTITY_SENTINEL", "is_unparseable_quantity"]

    for export in expected_exports:
        assert export in __all__, f"{export} should be in __all__"
