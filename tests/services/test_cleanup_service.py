"""
Unit tests for browse cache cleanup service.

Tests cover:
- Pruning non-persisted recipes older than TTL
- Preserving persisted recipes
- Preserving non-persisted recipes newer than TTL
- Cascade deletion of UserRecipeRelation records
- Correct count of pruned recipes
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.db.database import Base
from src.db import models  # Import all models to ensure Base.metadata has all tables
from src.db.models.recipe import Recipe
from src.db.models.user import User, UserRole
from src.db.models.user_recipe import UserRecipeRelation
from src.services.cleanup_service import prune_unpersisted_recipes
from src.services.auth_service import hash_password


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """
    Set up test environment variables.

    Uses monkeypatch to ensure clean setup/teardown and prevent test pollution.
    autouse=True means this fixture runs automatically for all tests in this module.
    """
    # Clear the settings cache before setting environment variables
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("BROWSE_CACHE_TTL_DAYS", "7")  # Default TTL for most tests

    # Clear the cache again to ensure fresh settings are loaded
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    # Ensure all models are imported by accessing them
    _ = models  # This forces the import of all models

    # Create a new engine with StaticPool to ensure all connections share the same in-memory database
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Critical for SQLite :memory: to work correctly
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


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestPruneUnpersistedRecipes:
    """Tests for the prune_unpersisted_recipes function."""

    def test_prunes_old_unpersisted_recipe(self, db_session, test_user):
        """Test that non-persisted recipe older than TTL is pruned."""
        # Create a recipe that's 10 days old and not persisted
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        recipe_id = uuid4()
        old_recipe = Recipe(
            id=recipe_id,
            name="Old Browse Recipe",
            source_type="hellofresh_web",
            is_persisted=False,
            created_at=old_date,
            created_by=test_user.id,
        )
        db_session.add(old_recipe)
        db_session.commit()

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify recipe was pruned
        assert pruned_count == 1
        remaining = db_session.query(Recipe).filter_by(id=recipe_id).first()
        assert remaining is None

    def test_preserves_persisted_recipe(self, db_session, test_user):
        """Test that persisted recipe is not pruned regardless of age."""
        # Create a persisted recipe that's 10 days old
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        recipe_id = uuid4()
        persisted_recipe = Recipe(
            id=recipe_id,
            name="Persisted Recipe",
            source_type="manual",
            is_persisted=True,
            created_at=old_date,
            created_by=test_user.id,
        )
        db_session.add(persisted_recipe)
        db_session.commit()

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify recipe was NOT pruned
        assert pruned_count == 0
        remaining = db_session.query(Recipe).filter_by(id=recipe_id).first()
        assert remaining is not None

    def test_preserves_recent_unpersisted_recipe(self, db_session, test_user):
        """Test that non-persisted recipe newer than TTL is not pruned."""
        # Create a recipe that's 3 days old (within 7-day TTL)
        recent_date = datetime.now(timezone.utc) - timedelta(days=3)
        recipe_id = uuid4()
        recent_recipe = Recipe(
            id=recipe_id,
            name="Recent Browse Recipe",
            source_type="hellofresh_web",
            is_persisted=False,
            created_at=recent_date,
            created_by=test_user.id,
        )
        db_session.add(recent_recipe)
        db_session.commit()

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify recipe was NOT pruned
        assert pruned_count == 0
        remaining = db_session.query(Recipe).filter_by(id=recipe_id).first()
        assert remaining is not None

    def test_deletes_orphaned_user_recipe_ratings(self, db_session, test_user):
        """Test that UserRecipeRelation records for pruned recipes are deleted."""
        # Create an old unpersisted recipe
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        recipe_id = uuid4()
        old_recipe = Recipe(
            id=recipe_id,
            name="Old Browse Recipe",
            source_type="hellofresh_web",
            is_persisted=False,
            created_at=old_date,
            created_by=test_user.id,
        )
        db_session.add(old_recipe)
        db_session.commit()

        # Create a rating for this recipe
        rating_id = uuid4()
        rating = UserRecipeRelation(
            id=rating_id,
            user_id=test_user.id,
            recipe_id=recipe_id,
            rating=4.5,
            is_bookmarked=True,
        )
        db_session.add(rating)
        db_session.commit()

        # Verify rating exists before cleanup
        rating_before = db_session.query(UserRecipeRelation).filter_by(id=rating_id).first()
        assert rating_before is not None

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify recipe and rating were both deleted
        assert pruned_count == 1
        recipe_after = db_session.query(Recipe).filter_by(id=recipe_id).first()
        rating_after = db_session.query(UserRecipeRelation).filter_by(id=rating_id).first()
        assert recipe_after is None
        assert rating_after is None

    def test_returns_correct_count_multiple_recipes(self, db_session, test_user):
        """Test that prune function returns correct count when multiple recipes are pruned."""
        old_date = datetime.now(timezone.utc) - timedelta(days=10)

        # Create 3 old unpersisted recipes
        old_recipe_ids = []
        for i in range(3):
            recipe_id = uuid4()
            recipe = Recipe(
                id=recipe_id,
                name=f"Old Recipe {i}",
                source_type="hellofresh_web",
                is_persisted=False,
                created_at=old_date,
                created_by=test_user.id,
            )
            old_recipe_ids.append(recipe_id)
            db_session.add(recipe)

        # Create 1 persisted old recipe (should not be pruned)
        persisted_recipe_id = uuid4()
        persisted_recipe = Recipe(
            id=persisted_recipe_id,
            name="Persisted Recipe",
            source_type="manual",
            is_persisted=True,
            created_at=old_date,
            created_by=test_user.id,
        )
        db_session.add(persisted_recipe)

        # Create 1 recent unpersisted recipe (should not be pruned)
        recent_recipe_id = uuid4()
        recent_recipe = Recipe(
            id=recent_recipe_id,
            name="Recent Recipe",
            source_type="hellofresh_web",
            is_persisted=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            created_by=test_user.id,
        )
        db_session.add(recent_recipe)
        db_session.commit()

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify correct count
        assert pruned_count == 3

        # Verify only the old unpersisted recipes were deleted
        for recipe_id in old_recipe_ids:
            assert db_session.query(Recipe).filter_by(id=recipe_id).first() is None
        assert db_session.query(Recipe).filter_by(id=persisted_recipe_id).first() is not None
        assert db_session.query(Recipe).filter_by(id=recent_recipe_id).first() is not None

    def test_no_recipes_to_prune(self, db_session, test_user):
        """Test that cleanup returns 0 when there are no recipes to prune."""
        # Create only recent recipes
        recipe_id = uuid4()
        recent_recipe = Recipe(
            id=recipe_id,
            name="Recent Recipe",
            source_type="hellofresh_web",
            is_persisted=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            created_by=test_user.id,
        )
        db_session.add(recent_recipe)
        db_session.commit()

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify no recipes were pruned
        assert pruned_count == 0

    def test_empty_database(self, db_session):
        """Test that cleanup handles empty database gracefully."""
        # Run cleanup on empty database
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify no errors and returns 0
        assert pruned_count == 0

    def test_custom_ttl_setting(self, db_session, test_user, monkeypatch):
        """Test that cleanup respects custom TTL setting."""
        # Set custom TTL to 3 days
        monkeypatch.setenv("BROWSE_CACHE_TTL_DAYS", "3")
        from src.config import get_settings
        get_settings.cache_clear()  # Clear cache to pick up new setting

        # Create a recipe that's 5 days old (would be pruned with 3-day TTL)
        old_date = datetime.now(timezone.utc) - timedelta(days=5)
        recipe_id = uuid4()
        old_recipe = Recipe(
            id=recipe_id,
            name="5-Day Old Recipe",
            source_type="hellofresh_web",
            is_persisted=False,
            created_at=old_date,
            created_by=test_user.id,
        )
        db_session.add(old_recipe)
        db_session.commit()

        # Run cleanup
        pruned_count = prune_unpersisted_recipes(db_session)

        # Verify recipe was pruned (5 days > 3 day TTL)
        assert pruned_count == 1
        remaining = db_session.query(Recipe).filter_by(id=recipe_id).first()
        assert remaining is None
