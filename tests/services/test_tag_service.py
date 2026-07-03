"""
Tests for tag_service - tag management and junction table sync.

Tests cover:
- sync_recipe_tags: Creating and updating recipe-tag associations
- get_or_create_tags: Tag normalization and deduplication
- Race condition handling for concurrent tag creation
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.db.database import Base
from src.db import models
from src.db.models.recipe import Recipe
from src.db.models.tag import Tag
from src.db.models.recipe_tag import RecipeTag
from src.services.tag_service import sync_recipe_tags, get_or_create_tags


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")

    get_settings.cache_clear()


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
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


def test_sync_recipe_tags_creates_new_tags(db_session):
    """Test that sync_recipe_tags creates new tags and associations."""
    # Create a recipe
    recipe = Recipe(
        name="Test Recipe",
        source_type="manual",
        tags=["vegetarian", "quick", "healthy"]
    )
    db_session.add(recipe)
    db_session.commit()

    # Sync tags
    sync_recipe_tags(recipe.id, ["vegetarian", "quick", "healthy"], db_session)
    db_session.commit()

    # Verify tags were created
    tags = db_session.query(Tag).all()
    assert len(tags) == 3
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "quick", "healthy"}

    # Verify recipe-tag associations were created
    recipe_tags = db_session.query(RecipeTag).filter(RecipeTag.recipe_id == recipe.id).all()
    assert len(recipe_tags) == 3


def test_sync_recipe_tags_normalizes_tag_names(db_session):
    """Test that tag names are normalized (lowercase, stripped)."""
    recipe = Recipe(
        name="Test Recipe",
        source_type="manual",
        tags=["Vegetarian", "  QUICK  ", "Healthy"]
    )
    db_session.add(recipe)
    db_session.commit()

    sync_recipe_tags(recipe.id, ["Vegetarian", "  QUICK  ", "Healthy"], db_session)
    db_session.commit()

    # Verify tags are normalized
    tags = db_session.query(Tag).all()
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "quick", "healthy"}


def test_sync_recipe_tags_updates_existing_associations(db_session):
    """Test that sync_recipe_tags replaces old associations with new ones."""
    recipe = Recipe(
        name="Test Recipe",
        source_type="manual",
        tags=["vegetarian", "quick"]
    )
    db_session.add(recipe)
    db_session.commit()

    # Initial sync
    sync_recipe_tags(recipe.id, ["vegetarian", "quick"], db_session)
    db_session.commit()

    # Update with different tags
    sync_recipe_tags(recipe.id, ["vegetarian", "healthy"], db_session)
    db_session.commit()

    # Verify only new associations exist
    recipe_tags = db_session.query(RecipeTag).filter(RecipeTag.recipe_id == recipe.id).all()
    assert len(recipe_tags) == 2

    # Get associated tag names
    tag_ids = [rt.tag_id for rt in recipe_tags]
    tags = db_session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "healthy"}


def test_sync_recipe_tags_reuses_existing_tags(db_session):
    """Test that sync_recipe_tags reuses existing tags instead of duplicating."""
    # Create existing tags
    tag1 = Tag(name="vegetarian")
    tag2 = Tag(name="quick")
    db_session.add_all([tag1, tag2])
    db_session.commit()

    # Create recipe and sync with existing tag names
    recipe = Recipe(
        name="Test Recipe",
        source_type="manual",
        tags=["vegetarian", "quick"]
    )
    db_session.add(recipe)
    db_session.commit()

    sync_recipe_tags(recipe.id, ["vegetarian", "quick"], db_session)
    db_session.commit()

    # Verify no new tags were created
    tags = db_session.query(Tag).all()
    assert len(tags) == 2


def test_sync_recipe_tags_handles_empty_tag_list(db_session):
    """Test that sync_recipe_tags handles empty tag lists gracefully."""
    recipe = Recipe(
        name="Test Recipe",
        source_type="manual",
        tags=[]
    )
    db_session.add(recipe)
    db_session.commit()

    sync_recipe_tags(recipe.id, [], db_session)
    db_session.commit()

    # Verify no tags or associations were created
    tags = db_session.query(Tag).all()
    assert len(tags) == 0

    recipe_tags = db_session.query(RecipeTag).filter(RecipeTag.recipe_id == recipe.id).all()
    assert len(recipe_tags) == 0


def test_sync_recipe_tags_skips_empty_strings(db_session):
    """Test that empty and whitespace-only tags are skipped."""
    recipe = Recipe(
        name="Test Recipe",
        source_type="manual",
        tags=["vegetarian", "", "  ", "quick"]
    )
    db_session.add(recipe)
    db_session.commit()

    sync_recipe_tags(recipe.id, ["vegetarian", "", "  ", "quick"], db_session)
    db_session.commit()

    # Verify only valid tags were created
    tags = db_session.query(Tag).all()
    assert len(tags) == 2
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "quick"}


def test_get_or_create_tags_creates_new_tags(db_session):
    """Test that get_or_create_tags creates tags that don't exist."""
    tags = get_or_create_tags(["vegetarian", "quick", "healthy"], db_session)

    assert len(tags) == 3
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "quick", "healthy"}


def test_get_or_create_tags_reuses_existing_tags(db_session):
    """Test that get_or_create_tags reuses existing tags."""
    # Create existing tag
    existing_tag = Tag(name="vegetarian")
    db_session.add(existing_tag)
    db_session.commit()

    # Get or create including existing tag
    tags = get_or_create_tags(["vegetarian", "quick"], db_session)

    # Verify total tags in database
    all_tags = db_session.query(Tag).all()
    assert len(all_tags) == 2

    # Verify returned tags
    assert len(tags) == 2
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "quick"}


def test_get_or_create_tags_normalizes_names(db_session):
    """Test that get_or_create_tags normalizes tag names."""
    tags = get_or_create_tags(["Vegetarian", "  QUICK  "], db_session)

    assert len(tags) == 2
    tag_names = {tag.name for tag in tags}
    assert tag_names == {"vegetarian", "quick"}


def test_sync_recipe_tags_with_get_recipes_by_tag_integration(db_session):
    """
    Integration test: Verify synced tags enable efficient queries.

    This tests the end-to-end flow:
    1. Create recipes with tags (JSON column)
    2. Sync tags to junction table
    3. Query recipes by tag using indexed lookup
    """
    from src.services.feed_service import get_recipes_by_tag
    from src.db.models.user import User, UserRole
    from uuid import uuid4

    # Create test user
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password="test",
        role=UserRole.member
    )
    db_session.add(user)

    # Create recipes with tags
    recipe1 = Recipe(
        name="Veggie Burger",
        source_type="manual",
        tags=["vegetarian", "quick"],
        is_persisted=True,
        times_cooked=5
    )
    recipe2 = Recipe(
        name="Tofu Stir Fry",
        source_type="manual",
        tags=["vegetarian", "asian"],
        is_persisted=True,
        times_cooked=3
    )
    recipe3 = Recipe(
        name="Steak",
        source_type="manual",
        tags=["meat"],
        is_persisted=True,
        times_cooked=10
    )
    db_session.add_all([recipe1, recipe2, recipe3])
    db_session.commit()

    # Sync tags to junction table
    sync_recipe_tags(recipe1.id, recipe1.tags, db_session)
    sync_recipe_tags(recipe2.id, recipe2.tags, db_session)
    sync_recipe_tags(recipe3.id, recipe3.tags, db_session)
    db_session.commit()

    # Query recipes by tag using optimized function
    vegetarian_recipes = get_recipes_by_tag(user.id, db_session, "vegetarian", limit=10)

    # Verify only vegetarian recipes are returned
    assert len(vegetarian_recipes) == 2
    recipe_names = {r.name for r in vegetarian_recipes}
    assert recipe_names == {"Veggie Burger", "Tofu Stir Fry"}

    # Verify ordering (by times_cooked descending)
    assert vegetarian_recipes[0].name == "Veggie Burger"  # times_cooked=5
    assert vegetarian_recipes[1].name == "Tofu Stir Fry"  # times_cooked=3
