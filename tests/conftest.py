"""
Pytest configuration and shared fixtures for all tests.

This module provides test infrastructure improvements, particularly for
managing the settings cache to prevent test pollution.

Pytest-asyncio Compatibility Patch (Python 3.14+):
    In Python 3.14+, pytest-asyncio expects the Package class from pytest's
    internal API to have an 'obj' attribute that represents the package object.
    This attribute was present in earlier pytest versions but was removed or
    changed in the internal API refactoring.

    Without this patch, pytest-asyncio's fixture collection fails when trying
    to access Package.obj, causing test collection to fail with AttributeError.

    This monkey-patch adds the missing 'obj' attribute dynamically when accessed,
    maintaining backward compatibility with older Python/pytest versions while
    fixing compatibility with Python 3.14+.

    Related: PR #394 (Ollama integration tests)
    Severity: MEDIUM - affects test infrastructure, not production code
"""

import os
import sys
import warnings

import pytest
from _pytest.python import Package


# ============================================================================
# PYTEST-ASYNCIO COMPATIBILITY PATCH FOR PYTHON 3.14+
# ============================================================================
# This patch must be applied at module level before pytest_asyncio hooks
# are registered during test collection.

def _apply_package_obj_patch():
    """
    Apply monkey-patch to _pytest.python.Package for pytest-asyncio compatibility.

    Python 3.14+ introduced changes that affect how pytest's internal Package
    class works with pytest-asyncio. This function patches Package.__getattribute__
    to dynamically provide an 'obj' attribute when accessed.

    The patch:
    1. Only applies on Python 3.14+ (where the issue occurs)
    2. Checks if already patched to prevent double-patching
    3. Validates Package class structure before patching
    4. Fails gracefully with warnings if patching encounters issues

    Returns:
        bool: True if patch was applied successfully, False otherwise
    """
    # Only apply patch for Python 3.14+
    if sys.version_info < (3, 14):
        return False

    # Check if already patched (prevents double-patching)
    if hasattr(Package, '_original_getattribute'):
        return True  # Already patched

    try:
        # Validate that Package class has the expected structure
        if not hasattr(Package, '__getattribute__'):
            warnings.warn(
                "Cannot apply pytest-asyncio compatibility patch: "
                "Package class missing __getattribute__ method. "
                "Tests may fail with pytest-asyncio on Python 3.14+.",
                RuntimeWarning,
                stacklevel=2
            )
            return False

        # Store original __getattribute__ method
        _original_getattribute = Package.__getattribute__

        def _patched_getattribute(self, name):
            """
            Patched __getattribute__ that provides 'obj' attribute on demand.

            When pytest-asyncio tries to access Package.obj, this method:
            1. Checks if 'obj' is being requested
            2. Verifies 'obj' doesn't already exist as a class attribute
            3. Creates a dummy object and caches it on the instance
            4. Returns the cached obj for subsequent accesses

            For all other attribute accesses, delegates to the original method.
            """
            if name == 'obj' and not hasattr(type(self), 'obj'):
                # Create a simple dummy object that can have attributes set on it
                # This satisfies pytest-asyncio's expectations without affecting
                # actual package collection behavior
                class DummyObj:
                    """Placeholder object for Package.obj compatibility."""
                    pass

                # Cache the dummy obj on the instance to ensure consistency
                # across multiple accesses within the same test collection
                object.__setattr__(self, 'obj', DummyObj())
                return object.__getattribute__(self, 'obj')

            # For all other attributes, use the original __getattribute__
            return _original_getattribute(self, name)

        # Apply the patch
        Package.__getattribute__ = _patched_getattribute
        Package._original_getattribute = _original_getattribute

        return True

    except Exception as e:
        # Log warning but don't fail - tests might still work on older versions
        warnings.warn(
            f"Failed to apply pytest-asyncio compatibility patch: {e}. "
            f"Tests may fail with pytest-asyncio on Python 3.14+.",
            RuntimeWarning,
            stacklevel=2
        )
        return False


# Apply the patch at module import time
_apply_package_obj_patch()


def pytest_configure(config):
    """Set required env vars before collection so module-level imports succeed.

    rate_limit.py calls get_settings() at import time (to initialize the limiter).
    Without these vars, collection fails with a pydantic ValidationError before
    any fixtures have a chance to run.
    """
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    """
    Automatically clear the settings cache before and after each test.

    This fixture prevents test pollution from cached settings by ensuring
    that each test starts with a fresh settings cache. The settings cache
    uses functools.lru_cache in src/config.py, which can cause tests to
    interfere with each other if not properly cleared.

    The fixture:
    1. Clears the cache before the test runs
    2. Sets default test environment variables
    3. Clears the cache again to ensure the new env vars are picked up
    4. Runs the test (yield)
    5. Clears the cache after the test completes

    Individual tests can override specific environment variables by calling
    monkeypatch.setenv() and get_settings.cache_clear() within the test.

    Args:
        monkeypatch: Pytest fixture for safely modifying environment variables

    Note:
        This fixture uses autouse=True, so it runs automatically for all tests
        without needing to be explicitly requested in test function signatures.
    """
    from src.config import get_settings

    # Clear cache before test to ensure clean slate
    get_settings.cache_clear()

    # Set default test environment variables that are required by most tests
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")

    # Clear cache after setting env vars to ensure fresh settings are loaded
    # This is critical: without this, get_settings() would return cached settings
    # that were created before we set the test environment variables
    get_settings.cache_clear()

    # Run the test
    yield

    # Clear cache after test completes to prevent pollution of subsequent tests
    # This is a safety measure: pytest's monkeypatch automatically restores
    # environment variables, but the cache could still hold stale settings
    get_settings.cache_clear()
