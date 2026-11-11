"""
Model tests for SourceCollection, SourceRecipeCard, and SourceCollectionCard.

Tests cover:
- Creating rows and reading them back
- UniqueConstraint(source_type, slug) on source_collections raises IntegrityError
- UniqueConstraint(source_type, recipe_url) on source_recipe_cards raises IntegrityError
- Deleting a Recipe sets recipe_id to NULL on its card (ON DELETE SET NULL)
- Deleting a SourceCollection removes join rows but leaves the cards (ON DELETE CASCADE)
- Tables visible in Base.metadata
"""

import pytest
from uuid import uuid4

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models  # noqa: F401 — registers all models with Base.metadata
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceRecipeCard, SourceCollectionCard


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set required environment variables."""
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
    """Fresh in-memory SQLite database with FK enforcement for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
    user = User(
        id=uuid4(),
        name="Catalog Tester",
        email="catalogtester@example.com",
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_recipe(db_session, test_user):
    recipe = Recipe(
        id=uuid4(),
        name="Test Catalog Recipe",
        source_type="hellofresh_web",
        is_persisted=True,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


@pytest.fixture
def test_collection(db_session):
    col = SourceCollection(
        id=uuid4(),
        source_type="hellofresh_web",
        slug="vegetarian-recipes",
        name="Vegetarian Recipes",
        url="https://www.hellofresh.com/recipes/vegetarian-recipes",
    )
    db_session.add(col)
    db_session.commit()
    db_session.refresh(col)
    return col


@pytest.fixture
def test_card(db_session):
    card = SourceRecipeCard(
        id=uuid4(),
        source_type="hellofresh_web",
        external_id="abc123def456abc123def456",
        name="Lemon Herb Chicken",
        recipe_url="https://www.hellofresh.com/recipes/lemon-herb-chicken-abc123",
        fetched_at=__import__("datetime").datetime.utcnow(),
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# SourceCollection tests
# ---------------------------------------------------------------------------

class TestSourceCollectionModel:

    def test_create_and_read_back(self, db_session):
        col = SourceCollection(
            id=uuid4(),
            source_type="hellofresh_web",
            slug="quick-meals",
            name="Quick Meals",
            url="https://www.hellofresh.com/recipes/quick-meals",
            parent_slug="all-recipes",
        )
        db_session.add(col)
        db_session.commit()

        loaded = db_session.get(SourceCollection, col.id)
        assert loaded is not None
        assert loaded.slug == "quick-meals"
        assert loaded.parent_slug == "all-recipes"
        assert loaded.last_fetched_at is None
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

    def test_unique_source_type_slug_raises_integrity_error(self, db_session, test_collection):
        """(source_type, slug) uniqueness is enforced."""
        duplicate = SourceCollection(
            id=uuid4(),
            source_type=test_collection.source_type,
            slug=test_collection.slug,
            name="Duplicate Collection",
            url="https://www.hellofresh.com/recipes/vegetarian-recipes",
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_same_slug_different_source_type_allowed(self, db_session, test_collection):
        """Same slug for a different source_type is not a constraint violation."""
        other = SourceCollection(
            id=uuid4(),
            source_type="kitchen_sanctuary",
            slug=test_collection.slug,
            name="Vegetarian Recipes",
            url="https://www.kitchensanctuary.com/vegetarian",
        )
        db_session.add(other)
        db_session.commit()
        assert db_session.get(SourceCollection, other.id) is not None


# ---------------------------------------------------------------------------
# SourceRecipeCard tests
# ---------------------------------------------------------------------------

class TestSourceRecipeCardModel:

    def test_create_and_read_back(self, db_session, test_card):
        loaded = db_session.get(SourceRecipeCard, test_card.id)
        assert loaded is not None
        assert loaded.name == "Lemon Herb Chicken"
        assert loaded.recipe_id is None
        assert loaded.headline is None
        assert loaded.fetched_at is not None

    def test_unique_source_type_recipe_url_raises_integrity_error(self, db_session, test_card):
        """(source_type, recipe_url) uniqueness is enforced."""
        duplicate = SourceRecipeCard(
            id=uuid4(),
            source_type=test_card.source_type,
            external_id="differentid000000000000",
            name="Different Name Same URL",
            recipe_url=test_card.recipe_url,
            fetched_at=__import__("datetime").datetime.utcnow(),
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_same_recipe_url_different_source_type_allowed(self, db_session, test_card):
        """Same recipe_url for a different source_type is allowed."""
        other = SourceRecipeCard(
            id=uuid4(),
            source_type="kitchen_sanctuary",
            external_id="ks000001",
            name="Some Recipe",
            recipe_url=test_card.recipe_url,
            fetched_at=__import__("datetime").datetime.utcnow(),
        )
        db_session.add(other)
        db_session.commit()
        assert db_session.get(SourceRecipeCard, other.id) is not None

    def test_delete_recipe_nulls_recipe_id(self, db_session, test_card, test_recipe):
        """ON DELETE SET NULL: deleting a Recipe nulls recipe_id on the card."""
        test_card.recipe_id = test_recipe.id
        db_session.commit()

        card_id = test_card.id
        db_session.delete(test_recipe)
        db_session.commit()

        db_session.expire_all()
        loaded = db_session.get(SourceRecipeCard, card_id)
        assert loaded is not None, "Card must survive after Recipe is deleted"
        assert loaded.recipe_id is None

    def test_recipe_rel_resolves(self, db_session, test_card, test_recipe):
        """recipe_rel relationship traverses to the linked Recipe."""
        test_card.recipe_id = test_recipe.id
        db_session.commit()
        db_session.refresh(test_card)

        assert test_card.recipe_rel is not None
        assert test_card.recipe_rel.id == test_recipe.id


# ---------------------------------------------------------------------------
# SourceCollectionCard (join table) tests
# ---------------------------------------------------------------------------

class TestSourceCollectionCardModel:

    def test_create_join_row(self, db_session, test_collection, test_card):
        join = SourceCollectionCard(
            collection_id=test_collection.id,
            card_id=test_card.id,
            position=0,
        )
        db_session.add(join)
        db_session.commit()

        loaded = db_session.get(SourceCollectionCard, (test_collection.id, test_card.id))
        assert loaded is not None
        assert loaded.position == 0

    def test_delete_collection_removes_join_rows_leaves_cards(
        self, db_session, test_collection, test_card
    ):
        """ON DELETE CASCADE: deleting a collection removes its join rows, not its cards."""
        join = SourceCollectionCard(
            collection_id=test_collection.id,
            card_id=test_card.id,
            position=0,
        )
        db_session.add(join)
        db_session.commit()

        card_id = test_card.id
        collection_id = test_collection.id

        db_session.delete(test_collection)
        db_session.commit()

        assert db_session.get(SourceCollectionCard, (collection_id, card_id)) is None
        assert db_session.get(SourceRecipeCard, card_id) is not None

    def test_delete_card_removes_join_rows(self, db_session, test_collection, test_card):
        """ON DELETE CASCADE: deleting a card removes its join rows."""
        join = SourceCollectionCard(
            collection_id=test_collection.id,
            card_id=test_card.id,
            position=1,
        )
        db_session.add(join)
        db_session.commit()

        card_id = test_card.id
        collection_id = test_collection.id

        db_session.delete(test_card)
        db_session.commit()

        assert db_session.get(SourceCollectionCard, (collection_id, card_id)) is None
        assert db_session.get(SourceCollection, collection_id) is not None

    def test_card_in_multiple_collections(self, db_session, test_card):
        """A single card can appear in multiple collections."""
        col_a = SourceCollection(
            id=uuid4(), source_type="hellofresh_web", slug="col-a",
            name="Col A", url="https://example.com/a",
        )
        col_b = SourceCollection(
            id=uuid4(), source_type="hellofresh_web", slug="col-b",
            name="Col B", url="https://example.com/b",
        )
        db_session.add_all([col_a, col_b])
        db_session.commit()

        db_session.add(SourceCollectionCard(collection_id=col_a.id, card_id=test_card.id, position=0))
        db_session.add(SourceCollectionCard(collection_id=col_b.id, card_id=test_card.id, position=5))
        db_session.commit()

        assert db_session.get(SourceCollectionCard, (col_a.id, test_card.id)) is not None
        assert db_session.get(SourceCollectionCard, (col_b.id, test_card.id)) is not None


# ---------------------------------------------------------------------------
# Registration / metadata tests
# ---------------------------------------------------------------------------

class TestCatalogTablesRegistered:

    def test_all_three_tables_in_metadata(self):
        assert "source_collections" in Base.metadata.tables
        assert "source_recipe_cards" in Base.metadata.tables
        assert "source_collection_cards" in Base.metadata.tables
