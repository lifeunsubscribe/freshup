"""
Application-wide constants for FreshUp.

This module contains constants used across multiple modules to ensure
consistency and maintainability.
"""

# Floating-point comparison tolerance
# Used when comparing floating-point quantities to determine if they are
# effectively zero or equal. This tolerance accounts for floating-point
# arithmetic precision limitations.
#
# Value: 1e-9 (0.000000001)
# Rationale: Suitable for typical kitchen inventory quantities which are
# rarely precise beyond 6-7 decimal places. This tolerance prevents
# floating-point rounding errors from leaving trace amounts (e.g., 1e-15)
# in the database while being strict enough for practical use cases.
#
# Example use cases:
# - Determining if an inventory item quantity has reached zero after consumption
# - Comparing recipe ingredient amounts for equality
FLOAT_COMPARISON_TOLERANCE = 1e-9
