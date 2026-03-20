"""
Application-wide constants for FreshUp.

This module contains constants used across multiple modules to improve
maintainability and provide clear documentation of their purpose.
"""

# Floating-point comparison tolerance
# Used to handle IEEE 754 floating-point arithmetic precision issues.
# This epsilon value (1e-9) is suitable for typical quantity comparisons
# in the inventory system, where values are expected to be in the range
# of 0.001 (e.g., grams, milliliters) to 10000+ (e.g., large quantities).
#
# For values that should be considered "effectively zero" (e.g., when
# deciding whether to delete an inventory item after consumption),
# comparing against this epsilon prevents precision errors from leaving
# items with quantities like 1e-15 instead of exactly 0.
FLOAT_COMPARISON_EPSILON = 1e-9
