"""
Tests for catalog_service: seed, upsert_collection_page, get_collection, open_card,
enrich_next_cards, card_enrichment_worker.
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.schemas.catalog import CollectionCard, CollectionChild, CollectionPage
from src.schemas.import_service import ImportResult, ImportStatus
from src.services import catalog_service
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError

TEST_DATABASE_URL = "sqlite:///:memory:"
HELLOFRESH_SOURCE = "hellofresh_web"


@pytest.fixture
def db_session():
    _ = models  # ensure all models are registered
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page(slug: str = "vegetarian-recipes", n_cards: int = 3, n_children: int = 2) -> CollectionPage:
    """Build a minimal CollectionPage for testing."""
    cards = [
        CollectionCard(
            external_id=f"id{i:024x}",
            name=f"Recipe {i}",
            headline=f"Tagline {i}" if i % 2 == 0 else None,
            image_url=f"https://img.hellofresh.com/image/recipe{i}.jpg",
            prep_time_minutes=20 + i * 5 if i < 2 else None,
            rating=4.0 + i * 0.1 if i < 2 else None,
            rating_count=100 * i if i < 2 else None,
            recipe_url=f"https://www.hellofresh.com/recipes/recipe-{i}-{'a' * 24}",
        )
        for i in range(n_cards)
    ]
    children = [
        CollectionChild(name=f"Child {i}", slug=f"child-{i}")
        for i in range(n_children)
    ]
    return CollectionPage(
        name="Vegetarian Recipes",
        slug=slug,
        url=f"https://www.hellofresh.com/recipes/{slug}",
        cards=cards,
        children=children,
    )


def _seed_collection(db, slug: str = "vegetarian-recipes") -> SourceCollection:
    """Insert a bare SourceCollection row (simulates seed step)."""
    coll = SourceCollection(
        source_type=HELLOFRESH_SOURCE,
        slug=slug,
        name=catalog_service._slug_to_name(slug),
        url=f"https://www.hellofresh.com/recipes/{slug}",
        last_fetched_at=None,
        parent_slug=None,
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


# ---------------------------------------------------------------------------
# seed_hellofresh_collections
# ---------------------------------------------------------------------------


SAMPLE_SITEMAP = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.hellofresh.com/recipes/vegetarian-recipes</loc></url>
  <url><loc>https://www.hellofresh.com/recipes/pasta-recipes</loc></url>
  <url><loc>https://www.hellofresh.com/recipes/some-recipe-5a1b2c3d4e5f6a7b8c9d0e1f</loc></url>
</urlset>
"""


class TestSeedHellofreshCollections:
    def test_inserts_collection_rows(self, db_session):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_SITEMAP.encode()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_session_factory.return_value = mock_http

            count = catalog_service.seed_hellofresh_collections(db_session)

        assert count == 2
        rows = db_session.query(SourceCollection).filter_by(source_type=HELLOFRESH_SOURCE).all()
        slugs = {r.slug for r in rows}
        assert slugs == {"vegetarian-recipes", "pasta-recipes"}

    def test_names_derived_from_slugs(self, db_session):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_SITEMAP.encode()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_session_factory.return_value = mock_http

            catalog_service.seed_hellofresh_collections(db_session)

        veg = db_session.query(SourceCollection).filter_by(slug="vegetarian-recipes").first()
        assert veg.name == "Vegetarian recipes"

    def test_last_fetched_at_is_null(self, db_session):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_SITEMAP.encode()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_session_factory.return_value = mock_http

            catalog_service.seed_hellofresh_collections(db_session)

        rows = db_session.query(SourceCollection).filter_by(source_type=HELLOFRESH_SOURCE).all()
        assert all(r.last_fetched_at is None for r in rows)

    def test_idempotent_on_second_call(self, db_session):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_SITEMAP.encode()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_session_factory.return_value = mock_http

            catalog_service.seed_hellofresh_collections(db_session)
            count2 = catalog_service.seed_hellofresh_collections(db_session)

        # Second call inserts zero new rows
        assert count2 == 0
        total = db_session.query(SourceCollection).filter_by(source_type=HELLOFRESH_SOURCE).count()
        assert total == 2

    def test_nested_urls_seed_as_children_of_their_url_parent(self, db_session):
        """
        /recipes/<parent>/<slug> is a sub-collection (usually an ingredient), not
        a top-level category. Seeding them all as top-level once filled the
        Recipes page with rows like "Arborio rice" and "Bacon".
        """
        sitemap = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.hellofresh.com/recipes/grain-recipes</loc></url>
  <url><loc>https://www.hellofresh.com/recipes/grain-recipes/arborio-rice</loc></url>
</urlset>
"""
        mock_response = MagicMock()
        mock_response.content = sitemap.encode()
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_session_factory.return_value = mock_http

            catalog_service.seed_hellofresh_collections(db_session)

        rows = {r.slug: r for r in db_session.query(SourceCollection).all()}
        assert rows["grain-recipes"].parent_slug is None
        assert rows["arborio-rice"].parent_slug == "grain-recipes"
        assert rows["arborio-rice"].url == "https://www.hellofresh.com/recipes/grain-recipes/arborio-rice"

    def test_network_error_raises_crawler_error(self, db_session):
        import requests

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.side_effect = requests.exceptions.ConnectionError("refused")
            mock_session_factory.return_value = mock_http

            with pytest.raises(CrawlerNetworkError):
                catalog_service.seed_hellofresh_collections(db_session)

    def test_invalid_xml_raises_parse_error(self, db_session):
        mock_response = MagicMock()
        mock_response.content = b"<not valid xml"
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.catalog_service.create_http_session") as mock_session_factory:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_session_factory.return_value = mock_http

            with pytest.raises(CrawlerParseError):
                catalog_service.seed_hellofresh_collections(db_session)


# ---------------------------------------------------------------------------
# upsert_collection_page
# ---------------------------------------------------------------------------


class TestUpsertCollectionPage:
    def test_stores_cards(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=3, n_children=0)
        catalog_service.upsert_collection_page(db_session, page)

        cards = db_session.query(SourceRecipeCard).filter_by(source_type=HELLOFRESH_SOURCE).all()
        assert len(cards) == 3

    def test_stores_children_with_parent_slug(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=0, n_children=2)
        catalog_service.upsert_collection_page(db_session, page)

        children = db_session.query(SourceCollection).filter_by(
            source_type=HELLOFRESH_SOURCE, parent_slug="vegetarian-recipes"
        ).all()
        assert len(children) == 2
        assert {c.slug for c in children} == {"child-0", "child-1"}

    def test_new_children_get_urls_under_the_parent_path(self, db_session):
        """/recipes/<child> alone serves the /recipes hub; the child lives under its parent."""
        _seed_collection(db_session)
        page = _make_page(n_cards=0, n_children=1)
        catalog_service.upsert_collection_page(db_session, page)

        child = db_session.query(SourceCollection).filter_by(slug="child-0").one()
        assert child.url == "https://www.hellofresh.com/recipes/vegetarian-recipes/child-0"

    def test_join_rows_in_page_order(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=3, n_children=0)
        catalog_service.upsert_collection_page(db_session, page)

        collection = db_session.query(SourceCollection).filter_by(slug="vegetarian-recipes").first()
        join_rows = (
            db_session.query(SourceCollectionCard)
            .filter_by(collection_id=collection.id)
            .order_by(SourceCollectionCard.position)
            .all()
        )
        assert [r.position for r in join_rows] == [0, 1, 2]

    def test_shared_card_one_row_two_join_rows(self, db_session):
        """A card URL that appears in two collections creates one SourceRecipeCard and two join rows."""
        slug_a = "vegetarian-recipes"
        slug_b = "quick-meals"
        _seed_collection(db_session, slug_a)
        _seed_collection(db_session, slug_b)

        shared_url = "https://www.hellofresh.com/recipes/shared-recipe-5a1b2c3d4e5f6a7b8c9d0e1f"
        shared_card = CollectionCard(
            external_id="5a1b2c3d4e5f6a7b8c9d0e1f",
            name="Shared Recipe",
            image_url="https://img.hellofresh.com/image/shared.jpg",
            recipe_url=shared_url,
        )

        page_a = CollectionPage(
            name="Vegetarian Recipes",
            slug=slug_a,
            url=f"https://www.hellofresh.com/recipes/{slug_a}",
            cards=[shared_card],
            children=[],
        )
        page_b = CollectionPage(
            name="Quick Meals",
            slug=slug_b,
            url=f"https://www.hellofresh.com/recipes/{slug_b}",
            cards=[shared_card],
            children=[],
        )

        catalog_service.upsert_collection_page(db_session, page_a)
        catalog_service.upsert_collection_page(db_session, page_b)

        total_cards = db_session.query(SourceRecipeCard).filter_by(
            source_type=HELLOFRESH_SOURCE, recipe_url=shared_url
        ).count()
        assert total_cards == 1  # one row despite two collections

        total_joins = db_session.query(SourceCollectionCard).count()
        assert total_joins == 2  # one per collection

    def test_second_upsert_replaces_join_rows(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=3, n_children=0)
        catalog_service.upsert_collection_page(db_session, page)

        # Upsert again with fewer cards
        page2 = _make_page(n_cards=1, n_children=0)
        catalog_service.upsert_collection_page(db_session, page2)

        collection = db_session.query(SourceCollection).filter_by(slug="vegetarian-recipes").first()
        join_count = db_session.query(SourceCollectionCard).filter_by(
            collection_id=collection.id
        ).count()
        assert join_count == 1

    def test_upsert_updates_collection_name_and_fetched_at(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=0, n_children=0)
        catalog_service.upsert_collection_page(db_session, page)

        collection = db_session.query(SourceCollection).filter_by(slug="vegetarian-recipes").first()
        assert collection.name == "Vegetarian Recipes"
        assert collection.last_fetched_at is not None

    def test_duplicate_card_in_page_creates_one_row(self, db_session):
        """A page listing the same recipe_url twice inserts one SourceRecipeCard, not two."""
        _seed_collection(db_session)
        dup_url = "https://www.hellofresh.com/recipes/dup-recipe-5a1b2c3d4e5f6a7b8c9d0e1f"
        dup_card = CollectionCard(
            external_id="5a1b2c3d4e5f6a7b8c9d0e1f",
            name="Duplicate Recipe",
            image_url="https://img.hellofresh.com/image/dup.jpg",
            recipe_url=dup_url,
        )
        page = CollectionPage(
            name="Vegetarian Recipes",
            slug="vegetarian-recipes",
            url="https://www.hellofresh.com/recipes/vegetarian-recipes",
            cards=[dup_card, dup_card],
            children=[],
        )
        catalog_service.upsert_collection_page(db_session, page)

        total_cards = db_session.query(SourceRecipeCard).filter_by(
            source_type=HELLOFRESH_SOURCE, recipe_url=dup_url
        ).count()
        assert total_cards == 1

    def test_upsert_adopts_a_seeded_collection_as_child(self, db_session):
        """A collection known only from the sitemap (parent_slug=None) gets its parent from the first page that lists it."""
        _seed_collection(db_session, "vegetarian-recipes")
        _seed_collection(db_session, "spinach")  # seeded flat: parent unknown

        page = CollectionPage(
            name="Vegetarian Recipes",
            slug="vegetarian-recipes",
            url="https://www.hellofresh.com/recipes/vegetarian-recipes",
            cards=[],
            children=[CollectionChild(name="Spinach Recipes", slug="spinach")],
        )
        catalog_service.upsert_collection_page(db_session, page)

        spinach = db_session.query(SourceCollection).filter_by(slug="spinach").first()
        assert spinach.parent_slug == "vegetarian-recipes"
        assert spinach.name == "Spinach Recipes"
        top_level = [c.slug for c in db_session.query(SourceCollection).filter_by(parent_slug=None).all()]
        assert top_level == ["vegetarian-recipes"]

# ---------------------------------------------------------------------------
# get_collection
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_returns_none_for_unknown_slug(self, db_session):
        result = catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "no-such-slug")
        assert result is None

    def test_fetches_nested_collection_by_its_stored_url(self, db_session):
        coll = SourceCollection(
            source_type=HELLOFRESH_SOURCE,
            slug="arborio-rice",
            name="Arborio rice",
            url="https://www.hellofresh.com/recipes/grain-recipes/arborio-rice",
            parent_slug="grain-recipes",
            last_fetched_at=None,
        )
        db_session.add(coll)
        db_session.commit()

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = _make_page(slug="arborio-rice", n_cards=1, n_children=0)

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "arborio-rice")

        mock_crawler.fetch_collection.assert_called_once_with(
            "arborio-rice", "https://www.hellofresh.com/recipes/grain-recipes/arborio-rice"
        )

    def test_calls_fetch_collection_on_null_fetched_at(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=3, n_children=2)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            result = catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "vegetarian-recipes")

        mock_crawler.fetch_collection.assert_called_once_with(
            "vegetarian-recipes", "https://www.hellofresh.com/recipes/vegetarian-recipes"
        )
        assert result is not None
        assert len(result.cards) == 3
        assert len(result.children) == 2

    def test_no_fetch_when_not_stale(self, db_session):
        """Collection fetched 1 hour ago should not be re-fetched."""
        coll = _seed_collection(db_session)
        coll.last_fetched_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        mock_crawler = MagicMock()

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "vegetarian-recipes")

        mock_crawler.fetch_collection.assert_not_called()

    def test_fetches_when_stale(self, db_session):
        """Collection fetched 25 hours ago (default refresh=24h) should be re-fetched."""
        coll = _seed_collection(db_session)
        coll.last_fetched_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db_session.commit()

        page = _make_page(n_cards=1, n_children=0)
        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "vegetarian-recipes")

        mock_crawler.fetch_collection.assert_called_once()

    def test_fresh_false_never_fetches(self, db_session):
        _seed_collection(db_session)  # last_fetched_at is None → would normally fetch

        mock_crawler = MagicMock()

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            catalog_service.get_collection(
                db_session, HELLOFRESH_SOURCE, "vegetarian-recipes", refresh_if_stale=False
            )

        mock_crawler.fetch_collection.assert_not_called()

    def test_force_refresh_always_fetches(self, db_session):
        """force_refresh=True fetches even when last_fetched_at is recent."""
        coll = _seed_collection(db_session)
        coll.last_fetched_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        page = _make_page(n_cards=1, n_children=0)
        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            catalog_service.get_collection(
                db_session, HELLOFRESH_SOURCE, "vegetarian-recipes", force_refresh=True
            )

        mock_crawler.fetch_collection.assert_called_once()

    def test_fetch_failure_with_stored_cards_returns_error_field(self, db_session):
        """Fetch fails but stored cards exist → result with fetch_error, no exception."""
        coll = _seed_collection(db_session)
        # Pre-load cards
        page = _make_page(n_cards=2, n_children=0)
        catalog_service.upsert_collection_page(db_session, page)
        # Make it stale so a fetch is attempted
        coll.last_fetched_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db_session.commit()

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.side_effect = CrawlerNetworkError("timeout")

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            result = catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "vegetarian-recipes")

        assert result is not None
        assert result.fetch_error is not None
        assert len(result.cards) == 2

    def test_fetch_failure_without_stored_cards_raises(self, db_session):
        """Fetch fails and no stored cards → exception propagates."""
        _seed_collection(db_session)  # no cards

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.side_effect = CrawlerNetworkError("timeout")

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            with pytest.raises(CrawlerNetworkError):
                catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "vegetarian-recipes")


# ---------------------------------------------------------------------------
# open_card
# ---------------------------------------------------------------------------


def _make_card(db, recipe_id=None) -> SourceRecipeCard:
    """Insert a bare SourceRecipeCard and return it."""
    card = SourceRecipeCard(
        source_type=HELLOFRESH_SOURCE,
        external_id="ext001",
        name="Test Recipe",
        recipe_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
        recipe_id=recipe_id,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _make_recipe(db, is_persisted=False) -> Recipe:
    """Insert a minimal Recipe row and return it."""
    recipe = Recipe(
        name="Veggie Pasta",
        source_type="hellofresh_web",
        source_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
        is_persisted=is_persisted,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def _import_success(recipe_id):
    return ImportResult(
        status=ImportStatus.success,
        recipe_id=recipe_id,
        warnings=[],
        error_message=None,
        source_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
    )


def _import_duplicate(recipe_id):
    return ImportResult(
        status=ImportStatus.duplicate,
        recipe_id=recipe_id,
        warnings=[],
        error_message=None,
        source_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
    )


def _import_error():
    return ImportResult(
        status=ImportStatus.error,
        recipe_id=None,
        warnings=[],
        error_message="Scraping failed: connection refused",
        source_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
    )


class TestOpenCard:
    def test_unlinked_card_calls_import_links_and_returns_recipe(self, db_session):
        """Opening an unlinked card imports the URL, links the card, and returns the recipe."""
        recipe = _make_recipe(db_session)
        card = _make_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_success(recipe.id),
        ) as mock_import:
            result = catalog_service.open_card(db_session, card.id)

        mock_import.assert_called_once_with(card.recipe_url, db_session)
        assert result is not None
        assert result.imported is True
        assert result.recipe.id == recipe.id

        db_session.refresh(card)
        assert card.recipe_id == recipe.id

    def test_already_linked_card_skips_import(self, db_session):
        """Opening a card whose recipe_id is already set does not call import."""
        recipe = _make_recipe(db_session)
        card = _make_card(db_session, recipe_id=recipe.id)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
        ) as mock_import:
            result = catalog_service.open_card(db_session, card.id)

        mock_import.assert_not_called()
        assert result is not None
        assert result.imported is False
        assert result.recipe.id == recipe.id

    def test_duplicate_import_links_card_to_existing_recipe(self, db_session):
        """Duplicate import result links the card to the already-existing recipe."""
        existing_recipe = _make_recipe(db_session)
        card = _make_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_duplicate(existing_recipe.id),
        ):
            result = catalog_service.open_card(db_session, card.id)

        assert result is not None
        assert result.imported is True
        assert result.recipe.id == existing_recipe.id

        db_session.refresh(card)
        assert card.recipe_id == existing_recipe.id

    def test_pruned_recipe_triggers_reimport(self, db_session):
        """Card linked to a deleted recipe (stale recipe_id) falls through to re-import."""
        stale_recipe_id = uuid4()
        card = _make_card(db_session, recipe_id=stale_recipe_id)
        new_recipe = _make_recipe(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_success(new_recipe.id),
        ) as mock_import:
            result = catalog_service.open_card(db_session, card.id)

        mock_import.assert_called_once_with(card.recipe_url, db_session)
        assert result is not None
        assert result.imported is True
        assert result.recipe.id == new_recipe.id

        db_session.refresh(card)
        assert card.recipe_id == new_recipe.id

    def test_import_error_raises_value_error_and_card_stays_unlinked(self, db_session):
        """Import error raises ValueError; card.recipe_id remains None."""
        card = _make_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_error(),
        ):
            with pytest.raises(ValueError):
                catalog_service.open_card(db_session, card.id)

        db_session.refresh(card)
        assert card.recipe_id is None

    def test_unknown_card_returns_none(self, db_session):
        """Non-existent card_id returns None."""
        result = catalog_service.open_card(db_session, uuid4())
        assert result is None

    def test_returned_recipe_is_not_persisted(self, db_session):
        """The recipe returned by open_card has is_persisted=False (browse cache)."""
        recipe = _make_recipe(db_session, is_persisted=False)
        card = _make_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_success(recipe.id),
        ):
            result = catalog_service.open_card(db_session, card.id)

        assert result is not None
        assert result.recipe.is_persisted is False

    def test_open_card_stores_sorted_ingredient_keys(self, db_session):
        """Opening a card sets ingredient_keys to the sorted keys from the recipe."""
        recipe = _make_recipe(db_session)
        ing = RecipeIngredient(recipe_id=recipe.id, ingredient_name="broccoli", quantity=1.0, unit="cup")
        db_session.add(ing)
        db_session.commit()

        card = _make_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_success(recipe.id),
        ):
            catalog_service.open_card(db_session, card.id)

        db_session.refresh(card)
        assert card.ingredient_keys == ["broccoli"]

    def test_open_card_stores_empty_list_when_no_known_ingredients(self, db_session):
        """A card whose import produced no recognized ingredients stores [] not NULL."""
        recipe = _make_recipe(db_session)
        ing = RecipeIngredient(recipe_id=recipe.id, ingredient_name="exotic mystery spice", quantity=1.0, unit="tsp")
        db_session.add(ing)
        db_session.commit()

        card = _make_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_import_success(recipe.id),
        ):
            catalog_service.open_card(db_session, card.id)

        db_session.refresh(card)
        assert card.ingredient_keys == []

    def test_open_card_backfills_ingredient_keys_on_fast_path(self, db_session):
        """A card already linked with ingredient_keys=None gets keys set on next open."""
        recipe = _make_recipe(db_session)
        ing = RecipeIngredient(recipe_id=recipe.id, ingredient_name="chicken", quantity=2.0, unit="lbs")
        db_session.add(ing)
        db_session.commit()

        card = _make_card(db_session, recipe_id=recipe.id)
        assert card.ingredient_keys is None

        with patch("src.services.catalog_service.import_recipe_from_url") as mock_import:
            result = catalog_service.open_card(db_session, card.id)

        mock_import.assert_not_called()
        assert result is not None
        assert result.imported is False

        db_session.refresh(card)
        assert card.ingredient_keys == ["chicken"]

    def test_open_card_backfill_commit_error_returns_not_imported(self, db_session):
        """When the backfill db.commit() raises SQLAlchemyError, open_card still returns imported=False and ingredient_keys stays None."""
        recipe = _make_recipe(db_session)
        ing = RecipeIngredient(recipe_id=recipe.id, ingredient_name="chicken", quantity=2.0, unit="lbs")
        db_session.add(ing)
        db_session.commit()

        card = _make_card(db_session, recipe_id=recipe.id)
        assert card.ingredient_keys is None

        with patch.object(db_session, "commit", side_effect=SQLAlchemyError("simulated backfill commit failure")):
            result = catalog_service.open_card(db_session, card.id)

        assert result is not None
        assert result.imported is False
        db_session.refresh(card)
        assert card.ingredient_keys is None


# ---------------------------------------------------------------------------
# enrich_next_cards
# ---------------------------------------------------------------------------


def _make_null_card(db, slug: str = "vegetarian-recipes", recipe_url: str = None) -> SourceRecipeCard:
    """Insert a SourceRecipeCard with ingredient_keys=None (not yet enriched)."""
    if recipe_url is None:
        recipe_url = f"https://www.hellofresh.com/recipes/{slug}-recipe-{'a' * 24}"
    card = SourceRecipeCard(
        source_type=HELLOFRESH_SOURCE,
        external_id=slug[:24].ljust(24, "0"),
        name=f"Recipe for {slug}",
        recipe_url=recipe_url,
        ingredient_keys=None,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _add_card_to_collection(db, card: SourceRecipeCard, collection: SourceCollection, position: int = 0) -> None:
    """Link a card to a collection (creates a SourceCollectionCard join row)."""
    db.add(SourceCollectionCard(collection_id=collection.id, card_id=card.id, position=position))
    db.commit()


def _make_scraped_data(ingredients: list[str]):
    """Return a minimal ScrapedRecipeData-like mock with the given ingredient strings."""
    scraped = MagicMock()
    scraped.ingredients = ingredients
    return scraped


class TestEnrichNextCards:
    def test_fills_null_cards_and_skips_already_set(self, db_session):
        """Cards with ingredient_keys=None are enriched; cards already set are ignored."""
        null_card = _make_null_card(db_session, slug="null-card",
                                    recipe_url="https://www.hellofresh.com/recipes/null-card-" + "a" * 24)
        filled_card = SourceRecipeCard(
            source_type=HELLOFRESH_SOURCE,
            external_id="f" * 24,
            name="Already filled",
            recipe_url="https://www.hellofresh.com/recipes/filled-" + "b" * 24,
            ingredient_keys=["chicken"],
        )
        db_session.add(filled_card)
        db_session.commit()

        mock_crawler = MagicMock()
        mock_crawler.robots_parser.can_fetch.return_value = True
        mock_crawler.rate_limiter.wait_if_needed = MagicMock()

        scraped = _make_scraped_data(["broccoli"])

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler), \
             patch("src.services.catalog_service.scrape_recipe", return_value=scraped):
            count = catalog_service.enrich_next_cards(db_session, limit=10)

        assert count == 1
        db_session.refresh(null_card)
        assert null_card.ingredient_keys == ["broccoli"]
        db_session.refresh(filled_card)
        assert filled_card.ingredient_keys == ["chicken"]  # unchanged

    def test_respects_limit_and_returns_count(self, db_session):
        """Only up to `limit` cards are enriched; the return value is the count."""
        for i in range(4):
            _make_null_card(db_session, slug=f"card-{i}",
                            recipe_url=f"https://www.hellofresh.com/recipes/card-{i}-" + "a" * 24)

        mock_crawler = MagicMock()
        mock_crawler.robots_parser.can_fetch.return_value = True
        mock_crawler.rate_limiter.wait_if_needed = MagicMock()

        scraped = _make_scraped_data([])

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler), \
             patch("src.services.catalog_service.scrape_recipe", return_value=scraped):
            count = catalog_service.enrich_next_cards(db_session, limit=2)

        assert count == 2

    def test_parse_failure_stores_empty_list_and_continues(self, db_session):
        """A scrape failure on card 1 stores [] and card 2 is still enriched."""
        card1 = _make_null_card(db_session, slug="bad-card",
                                recipe_url="https://www.hellofresh.com/recipes/bad-card-" + "a" * 24)
        card2 = _make_null_card(db_session, slug="good-card",
                                recipe_url="https://www.hellofresh.com/recipes/good-card-" + "b" * 24)

        mock_crawler = MagicMock()
        mock_crawler.robots_parser.can_fetch.return_value = True
        mock_crawler.rate_limiter.wait_if_needed = MagicMock()

        scraped_good = _make_scraped_data(["chicken"])

        def _scrape_side_effect(url):
            if "bad-card" in url:
                raise Exception("simulated parse failure")
            return scraped_good

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler), \
             patch("src.services.catalog_service.scrape_recipe", side_effect=_scrape_side_effect):
            count = catalog_service.enrich_next_cards(db_session, limit=10)

        assert count == 2
        db_session.refresh(card1)
        assert card1.ingredient_keys == []
        db_session.refresh(card2)
        assert card2.ingredient_keys == ["chicken"]

    def test_robots_disallow_stops_batch_leaves_remaining_null(self, db_session):
        """When robots.txt disallows a card URL, the batch stops and remaining cards stay NULL."""
        card1 = _make_null_card(db_session, slug="allowed-card",
                                recipe_url="https://www.hellofresh.com/recipes/allowed-" + "a" * 24)
        card2 = _make_null_card(db_session, slug="disallowed-card",
                                recipe_url="https://www.hellofresh.com/recipes/disallowed-" + "b" * 24)
        card3 = _make_null_card(db_session, slug="after-disallow",
                                recipe_url="https://www.hellofresh.com/recipes/after-" + "c" * 24)

        # Give card1 two collection memberships so it sorts first;
        # card2 gets one; card3 gets zero
        coll1 = _seed_collection(db_session, slug="coll-one")
        coll2 = _seed_collection(db_session, slug="coll-two")
        _add_card_to_collection(db_session, card1, coll1, 0)
        _add_card_to_collection(db_session, card1, coll2, 0)
        _add_card_to_collection(db_session, card2, coll1, 1)

        mock_crawler = MagicMock()
        scraped = _make_scraped_data(["broccoli"])

        def _can_fetch(url):
            return "disallowed" not in url

        mock_crawler.robots_parser.can_fetch.side_effect = _can_fetch
        mock_crawler.rate_limiter.wait_if_needed = MagicMock()

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler), \
             patch("src.services.catalog_service.scrape_recipe", return_value=scraped):
            count = catalog_service.enrich_next_cards(db_session, limit=10)

        # card1 enriched (most popular, allowed); card2 disallowed → batch stops
        assert count == 1
        db_session.refresh(card1)
        assert card1.ingredient_keys == ["broccoli"]
        db_session.refresh(card2)
        assert card2.ingredient_keys is None  # disallowed, not updated
        db_session.refresh(card3)
        assert card3.ingredient_keys is None  # never reached

    def test_no_recipe_row_created(self, db_session):
        """enrich_next_cards must not create any Recipe rows."""
        from src.db.models.recipe import Recipe as RecipeModel
        _make_null_card(db_session, slug="enrich-no-recipe",
                        recipe_url="https://www.hellofresh.com/recipes/enrich-no-recipe-" + "a" * 24)

        mock_crawler = MagicMock()
        mock_crawler.robots_parser.can_fetch.return_value = True
        mock_crawler.rate_limiter.wait_if_needed = MagicMock()

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler), \
             patch("src.services.catalog_service.scrape_recipe", return_value=_make_scraped_data(["chicken"])):
            catalog_service.enrich_next_cards(db_session, limit=5)

        assert db_session.query(RecipeModel).count() == 0

    def test_returns_zero_when_no_null_cards(self, db_session):
        """Returns 0 immediately when all cards already have ingredient_keys set."""
        card = SourceRecipeCard(
            source_type=HELLOFRESH_SOURCE,
            external_id="e" * 24,
            name="Pre-enriched",
            recipe_url="https://www.hellofresh.com/recipes/pre-enriched-" + "a" * 24,
            ingredient_keys=["beef"],
        )
        db_session.add(card)
        db_session.commit()

        mock_crawler = MagicMock()
        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            count = catalog_service.enrich_next_cards(db_session, limit=5)

        assert count == 0
        mock_crawler.robots_parser.can_fetch.assert_not_called()

    def test_keys_are_sorted_across_all_ingredients(self, db_session):
        """ingredient_keys is the sorted union of keys from all ingredient strings."""
        _make_null_card(db_session, slug="multi-ing",
                        recipe_url="https://www.hellofresh.com/recipes/multi-ing-" + "a" * 24)

        mock_crawler = MagicMock()
        mock_crawler.robots_parser.can_fetch.return_value = True
        mock_crawler.rate_limiter.wait_if_needed = MagicMock()

        scraped = _make_scraped_data(["broccoli florets", "chicken breast", "salt"])

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler), \
             patch("src.services.catalog_service.scrape_recipe", return_value=scraped):
            catalog_service.enrich_next_cards(db_session, limit=5)

        card = db_session.query(SourceRecipeCard).filter_by(name="Recipe for multi-ing").first()
        assert card.ingredient_keys == sorted(card.ingredient_keys)
        assert "broccoli" in card.ingredient_keys
        assert "chicken" in card.ingredient_keys


# ---------------------------------------------------------------------------
# card_enrichment_worker
# ---------------------------------------------------------------------------


class TestCardEnrichmentWorker:
    @pytest.mark.asyncio
    async def test_worker_calls_enrich_with_configured_batch_size(self, monkeypatch):
        """Worker calls enrich_next_cards with the configured batch size."""
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("CATALOG_ENRICH_INTERVAL_SECONDS", "1")
        monkeypatch.setenv("CATALOG_ENRICH_BATCH_SIZE", "7")
        get_settings.cache_clear()

        call_args = []

        def _mock_enrich(session, limit):
            call_args.append(limit)
            return 0

        mock_session_factory = MagicMock()
        mock_session_ctx = MagicMock()
        mock_session_factory.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.services.catalog_service.get_session_factory", return_value=mock_session_factory), \
             patch("src.services.catalog_service.enrich_next_cards", side_effect=_mock_enrich), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = asyncio.CancelledError()
            try:
                await catalog_service.card_enrichment_worker()
            except asyncio.CancelledError:
                pass

        assert call_args and call_args[0] == 7

    @pytest.mark.asyncio
    async def test_worker_logs_enriched_count(self, monkeypatch, caplog):
        """Worker logs 'enriched N card(s)' after each pass."""
        import logging
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("CATALOG_ENRICH_INTERVAL_SECONDS", "1")
        monkeypatch.setenv("CATALOG_ENRICH_BATCH_SIZE", "5")
        get_settings.cache_clear()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.services.catalog_service.get_session_factory", return_value=mock_session_factory), \
             patch("src.services.catalog_service.enrich_next_cards", return_value=3), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             caplog.at_level(logging.INFO, logger="src.services.catalog_service"):
            mock_sleep.side_effect = asyncio.CancelledError()
            try:
                await catalog_service.card_enrichment_worker()
            except asyncio.CancelledError:
                pass

        assert any("enriched 3 card(s)" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_worker_survives_exception_from_enrich(self, monkeypatch, caplog):
        """An exception from enrich_next_cards is logged and the worker continues."""
        import logging
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("CATALOG_ENRICH_INTERVAL_SECONDS", "1")
        monkeypatch.setenv("CATALOG_ENRICH_BATCH_SIZE", "5")
        get_settings.cache_clear()

        call_count = [0]

        def _failing_enrich(session, limit):
            call_count[0] += 1
            raise RuntimeError("simulated enrichment failure")

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        sleep_count = [0]

        async def _counting_sleep(seconds):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise asyncio.CancelledError()

        with patch("src.services.catalog_service.get_session_factory", return_value=mock_session_factory), \
             patch("src.services.catalog_service.enrich_next_cards", side_effect=_failing_enrich), \
             patch("asyncio.sleep", side_effect=_counting_sleep), \
             caplog.at_level(logging.ERROR, logger="src.services.catalog_service"):
            try:
                await catalog_service.card_enrichment_worker()
            except asyncio.CancelledError:
                pass

        # Worker completed at least two iterations despite errors
        assert call_count[0] >= 2
        assert any("Card enrichment iteration failed" in record.message for record in caplog.records)


class TestCardEnrichmentWorkerLifespan:
    @pytest.mark.asyncio
    async def test_interval_zero_starts_no_worker(self, monkeypatch):
        """When CATALOG_ENRICH_INTERVAL_SECONDS=0, lifespan does not start a worker task."""
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("CATALOG_ENRICH_INTERVAL_SECONDS", "0")
        get_settings.cache_clear()

        # Track whether the enrichment coroutine was actually started
        enrich_started = []

        async def _mock_enrich_worker():
            enrich_started.append(True)
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                raise

        async def _mock_bg_worker():
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                raise

        with patch("src.main.card_enrichment_worker", _mock_enrich_worker), \
             patch("src.main.background_task_worker", _mock_bg_worker), \
             patch("src.main.init_engine"), \
             patch("src.main._ensure_schema"), \
             patch("src.main._ensure_seed_data"), \
             patch("src.main.prune_unpersisted_recipes", return_value=0), \
             patch("src.main.get_session_factory") as mock_sf:
            mock_sf.return_value.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_sf.return_value.return_value.__exit__ = MagicMock(return_value=False)

            from src.main import app, lifespan
            async with lifespan(app):
                # Give the event loop a chance to run any pending coroutines
                await asyncio.sleep(0)

        # card_enrichment_worker was never scheduled
        assert not enrich_started
