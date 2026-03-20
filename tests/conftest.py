"""
Pytest configuration and shared fixtures for all tests.

This module provides test infrastructure improvements, particularly for
managing the settings cache to prevent test pollution.
"""

import pytest


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
