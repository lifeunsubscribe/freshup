"""
Tests for database seed data functionality.

Tests cover:
- Seed script creates stores with parsing profiles
- Costco store has correct parsing profile schema
- Generic store has correct parsing profile schema
- Parsing profiles are queryable
- Seed script is idempotent (safe to run multiple times)
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.db.database import Base
from src.db import models
from src.db.models.store import Store


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")

    get_settings.cache_clear()


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    from sqlalchemy.pool import StaticPool

    # Import models to ensure all SQLAlchemy model classes are registered
    _ = models

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_seed_stores_have_parsing_profiles(db_session):
    """Test that seed data includes parsing profiles for Costco and Generic stores."""
    from src.db.seed import STORES

    # Verify STORES constant has parsing profiles
    costco_store = next((s for s in STORES if s["name"] == "Costco"), None)
    generic_store = next((s for s in STORES if s["name"] == "Generic"), None)

    assert costco_store is not None, "Costco store not found in STORES"
    assert generic_store is not None, "Generic store not found in STORES"

    assert "parsing_profile" in costco_store, "Costco store missing parsing_profile"
    assert "parsing_profile" in generic_store, "Generic store missing parsing_profile"


def test_costco_parsing_profile_schema(db_session):
    """Test that Costco parsing profile follows the required schema."""
    from src.db.seed import STORES

    costco_store = next((s for s in STORES if s["name"] == "Costco"), None)
    profile = costco_store["parsing_profile"]

    # Verify required schema fields
    assert "header_patterns" in profile, "Missing header_patterns"
    assert "abbreviations" in profile, "Missing abbreviations"
    assert "date_formats" in profile, "Missing date_formats"
    assert "category_hints" in profile, "Missing category_hints"

    # Verify types
    assert isinstance(profile["header_patterns"], list), "header_patterns should be list"
    assert isinstance(profile["abbreviations"], dict), "abbreviations should be dict"
    assert isinstance(profile["date_formats"], list), "date_formats should be list"
    assert isinstance(profile["category_hints"], list), "category_hints should be list"

    # Verify non-empty
    assert len(profile["header_patterns"]) > 0, "header_patterns should not be empty"
    assert len(profile["abbreviations"]) > 0, "abbreviations should not be empty"
    assert len(profile["date_formats"]) > 0, "date_formats should not be empty"
    assert len(profile["category_hints"]) > 0, "category_hints should not be empty"


def test_generic_parsing_profile_schema(db_session):
    """Test that Generic parsing profile follows the required schema."""
    from src.db.seed import STORES

    generic_store = next((s for s in STORES if s["name"] == "Generic"), None)
    profile = generic_store["parsing_profile"]

    # Verify required schema fields
    assert "header_patterns" in profile, "Missing header_patterns"
    assert "abbreviations" in profile, "Missing abbreviations"
    assert "date_formats" in profile, "Missing date_formats"
    assert "category_hints" in profile, "Missing category_hints"

    # Verify types
    assert isinstance(profile["header_patterns"], list), "header_patterns should be list"
    assert isinstance(profile["abbreviations"], dict), "abbreviations should be dict"
    assert isinstance(profile["date_formats"], list), "date_formats should be list"
    assert isinstance(profile["category_hints"], list), "category_hints should be list"

    # Generic should have empty or minimal header_patterns (fallback)
    assert isinstance(profile["header_patterns"], list), "header_patterns should be list"


def test_seed_creates_stores_in_database(db_session, monkeypatch):
    """Test that running seed script creates stores with parsing profiles in database."""
    # Override database URL to use test session
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    from src.config import get_settings
    get_settings.cache_clear()

    # Mock the engine and session factory to use our test db_session
    from src.db import seed
    from unittest.mock import patch

    def mock_session_factory():
        class MockSessionContext:
            def __enter__(self):
                return db_session
            def __exit__(self, *args):
                pass
        return MockSessionContext()

    with patch.object(seed, 'init_engine'), \
         patch.object(seed, 'get_session_factory', return_value=mock_session_factory):
        seed.seed()

    # Query Costco store
    costco = db_session.execute(
        select(Store).where(Store.name == "Costco")
    ).scalar_one_or_none()

    assert costco is not None, "Costco store not created"
    assert costco.parsing_profile is not None, "Costco parsing_profile is None"
    assert "header_patterns" in costco.parsing_profile, "Costco missing header_patterns"

    # Query Generic store
    generic = db_session.execute(
        select(Store).where(Store.name == "Generic")
    ).scalar_one_or_none()

    assert generic is not None, "Generic store not created"
    assert generic.parsing_profile is not None, "Generic parsing_profile is None"
    assert "header_patterns" in generic.parsing_profile, "Generic missing header_patterns"


def test_seed_is_idempotent(db_session, monkeypatch):
    """Test that running seed script multiple times doesn't create duplicates."""
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    from src.config import get_settings
    get_settings.cache_clear()

    from src.db import seed
    from unittest.mock import patch

    def mock_session_factory():
        class MockSessionContext:
            def __enter__(self):
                return db_session
            def __exit__(self, *args):
                pass
        return MockSessionContext()

    with patch.object(seed, 'init_engine'), \
         patch.object(seed, 'get_session_factory', return_value=mock_session_factory):
        # Run seed twice
        seed.seed()
        seed.seed()

    # Count stores
    stores = db_session.execute(select(Store)).scalars().all()
    store_names = [s.name for s in stores]

    # Each store should appear exactly once
    assert store_names.count("Costco") == 1, "Costco store duplicated"
    assert store_names.count("Generic") == 1, "Generic store duplicated"


def test_seed_updates_existing_store_profile(db_session, monkeypatch):
    """Test that seed script updates parsing profile on existing stores."""
    from uuid import uuid4

    # Create a Costco store without parsing profile
    costco = Store(
        id=uuid4(),
        name="Costco",
        has_digital_receipts=True,
        parsing_profile=None
    )
    db_session.add(costco)
    db_session.commit()

    # Verify it has no profile
    assert costco.parsing_profile is None

    # Run seed
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    from src.config import get_settings
    get_settings.cache_clear()

    from src.db import seed
    from unittest.mock import patch

    def mock_session_factory():
        class MockSessionContext:
            def __enter__(self):
                return db_session
            def __exit__(self, *args):
                pass
        return MockSessionContext()

    with patch.object(seed, 'init_engine'), \
         patch.object(seed, 'get_session_factory', return_value=mock_session_factory):
        seed.seed()

    # Refresh and verify profile was added
    db_session.refresh(costco)
    assert costco.parsing_profile is not None, "Parsing profile not updated"
    assert "header_patterns" in costco.parsing_profile, "Missing header_patterns after update"
