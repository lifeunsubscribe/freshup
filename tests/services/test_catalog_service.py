"""
Tests for catalog_service: seed, upsert_collection_page, and get_collection.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.schemas.catalog import CollectionCard, CollectionChild, CollectionPage
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


# ---------------------------------------------------------------------------
# get_collection
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_returns_none_for_unknown_slug(self, db_session):
        result = catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "no-such-slug")
        assert result is None

    def test_calls_fetch_collection_on_null_fetched_at(self, db_session):
        _seed_collection(db_session)
        page = _make_page(n_cards=3, n_children=2)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            result = catalog_service.get_collection(db_session, HELLOFRESH_SOURCE, "vegetarian-recipes")

        mock_crawler.fetch_collection.assert_called_once_with("vegetarian-recipes")
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
