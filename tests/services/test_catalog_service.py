"""
Tests for catalog_service: seed, upsert_collection_page, get_collection, open_card,
enrich_next_cards, card_enrichment_worker.
"""

import asyncio
import logging
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
from src.schemas.scraper import ScrapedRecipeData
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
# seed_homechef_collections
# ---------------------------------------------------------------------------

HOMECHEF_SOURCE = "homechef_web"


class TestSeedHomechefCollections:
    def test_inserts_27_rows(self, db_session):
        count = catalog_service.seed_homechef_collections(db_session)
        assert count == 27
        rows = db_session.query(SourceCollection).filter_by(source_type=HOMECHEF_SOURCE).all()
        assert len(rows) == 27

    def test_includes_menu_collection(self, db_session):
        catalog_service.seed_homechef_collections(db_session)
        menu = db_session.query(SourceCollection).filter_by(
            source_type=HOMECHEF_SOURCE, slug="this-week"
        ).first()
        assert menu is not None
        assert menu.name == "This week at Home Chef"

    def test_menu_url_is_homechef_menu(self, db_session):
        from src.services.crawlers.homechef_crawler import HOMECHEF_MENU_URL
        catalog_service.seed_homechef_collections(db_session)
        menu = db_session.query(SourceCollection).filter_by(
            source_type=HOMECHEF_SOURCE, slug="this-week"
        ).first()
        assert menu.url == HOMECHEF_MENU_URL

    def test_category_url_uses_recipes_path(self, db_session):
        catalog_service.seed_homechef_collections(db_session)
        chicken = db_session.query(SourceCollection).filter_by(
            source_type=HOMECHEF_SOURCE, slug="chicken"
        ).first()
        assert chicken is not None
        assert chicken.url == "https://www.homechef.com/recipes/chicken"

    def test_last_fetched_at_is_null(self, db_session):
        catalog_service.seed_homechef_collections(db_session)
        rows = db_session.query(SourceCollection).filter_by(source_type=HOMECHEF_SOURCE).all()
        assert all(r.last_fetched_at is None for r in rows)

    def test_idempotent_second_call_inserts_zero(self, db_session):
        catalog_service.seed_homechef_collections(db_session)
        count2 = catalog_service.seed_homechef_collections(db_session)
        assert count2 == 0
        total = db_session.query(SourceCollection).filter_by(source_type=HOMECHEF_SOURCE).count()
        assert total == 27

    def test_no_network_call_made(self, db_session):
        # seed_homechef_collections must not make any HTTP requests
        import requests
        with patch.object(requests.Session, "get", side_effect=AssertionError("network call made")):
            catalog_service.seed_homechef_collections(db_session)


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


def _make_enrich_card(
    db,
    recipe_url: str = "https://www.hellofresh.com/recipes/test-{n}-aabbccdd1122334455667788",
    ingredient_keys=None,
    n: int = 0,
) -> SourceRecipeCard:
    """Insert a SourceRecipeCard suitable for enrichment tests."""
    card = SourceRecipeCard(
        source_type=HELLOFRESH_SOURCE,
        external_id=f"enrichtest{n:024x}",
        name=f"Enrich Test Recipe {n}",
        recipe_url=recipe_url.format(n=n),
        ingredient_keys=ingredient_keys,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _add_card_to_collection(db, card: SourceRecipeCard, collection: SourceCollection, position: int = 0) -> None:
    """Insert a SourceCollectionCard join row."""
    db.add(SourceCollectionCard(collection_id=collection.id, card_id=card.id, position=position))
    db.commit()


def _scraped(ingredients: list[str]) -> ScrapedRecipeData:
    """Build a minimal ScrapedRecipeData with the given ingredient strings."""
    return ScrapedRecipeData(
        source_url="https://www.hellofresh.com/recipes/dummy",
        source_type="hellofresh_web",
        ingredients=ingredients,
    )


def _mock_robots_rate(can_fetch=True):
    """Return (mock_robots_cls, mock_rate_cls) context managers that do nothing."""
    mock_rp = MagicMock()
    mock_rp.can_fetch.return_value = can_fetch
    mock_rl = MagicMock()
    mock_rl.wait_if_needed.return_value = None
    return mock_rp, mock_rl


class TestEnrichNextCards:
    def test_fills_null_cards(self, db_session):
        """enrich_next_cards populates ingredient_keys for NULL cards."""
        card = _make_enrich_card(db_session, n=0)
        assert card.ingredient_keys is None

        mock_rp, mock_rl = _mock_robots_rate()
        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch(
                "src.services.catalog_service.scrape_recipe",
                return_value=_scraped(["chicken breast", "broccoli"]),
            ),
        ):
            count = catalog_service.enrich_next_cards(db_session, limit=5)

        assert count == 1
        db_session.refresh(card)
        assert card.ingredient_keys is not None
        assert "chicken" in card.ingredient_keys
        assert "broccoli" in card.ingredient_keys
        assert card.ingredient_keys == sorted(card.ingredient_keys)

    def test_skips_cards_with_existing_keys(self, db_session):
        """Cards that already have ingredient_keys (including []) are not re-processed."""
        already = _make_enrich_card(db_session, n=0, ingredient_keys=["chicken"])
        null_card = _make_enrich_card(
            db_session,
            recipe_url="https://www.hellofresh.com/recipes/second-{n}-aabbccdd1122334455667788",
            n=1,
        )

        mock_rp, mock_rl = _mock_robots_rate()
        scrape_calls = []

        def tracking_scrape(url):
            scrape_calls.append(url)
            return _scraped(["salmon"])

        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch("src.services.catalog_service.scrape_recipe", side_effect=tracking_scrape),
        ):
            count = catalog_service.enrich_next_cards(db_session, limit=5)

        assert count == 1
        # Only the NULL card was scraped
        assert len(scrape_calls) == 1
        assert null_card.recipe_url in scrape_calls[0]
        # The already-enriched card is unchanged
        db_session.refresh(already)
        assert already.ingredient_keys == ["chicken"]

    def test_respects_limit(self, db_session):
        """enrich_next_cards processes at most `limit` cards."""
        for i in range(4):
            _make_enrich_card(
                db_session,
                recipe_url=f"https://www.hellofresh.com/recipes/limit-{i}-aabbccdd1122334455667788",
                n=i,
            )

        mock_rp, mock_rl = _mock_robots_rate()
        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch("src.services.catalog_service.scrape_recipe", return_value=_scraped([])),
        ):
            count = catalog_service.enrich_next_cards(db_session, limit=2)

        assert count == 2
        total_null = (
            db_session.query(SourceRecipeCard)
            .filter(SourceRecipeCard.ingredient_keys.is_(None))
            .count()
        )
        assert total_null == 2

    def test_parse_failure_stores_empty_list_and_continues(self, db_session):
        """A scrape/parse failure stores [] for that card and continues to the next."""
        bad_card = _make_enrich_card(
            db_session,
            recipe_url="https://www.hellofresh.com/recipes/bad-{n}-aabbccdd1122334455667788",
            n=0,
        )
        good_card = _make_enrich_card(
            db_session,
            recipe_url="https://www.hellofresh.com/recipes/good-{n}-aabbccdd1122334455667788",
            n=1,
        )

        mock_rp, mock_rl = _mock_robots_rate()

        def selective_scrape(url):
            if "bad" in url:
                raise ValueError("parse error")
            return _scraped(["salmon"])

        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch("src.services.catalog_service.scrape_recipe", side_effect=selective_scrape),
        ):
            count = catalog_service.enrich_next_cards(db_session, limit=5)

        assert count == 2
        db_session.refresh(bad_card)
        db_session.refresh(good_card)
        assert bad_card.ingredient_keys == []
        assert "salmon" in good_card.ingredient_keys

    def test_robots_disallow_stops_batch(self, db_session):
        """A robots.txt disallow raises CrawlerNetworkError and leaves the card NULL."""
        card = _make_enrich_card(db_session, n=0)

        mock_rp, mock_rl = _mock_robots_rate(can_fetch=False)
        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch("src.services.catalog_service.scrape_recipe") as mock_scrape,
        ):
            with pytest.raises(CrawlerNetworkError):
                catalog_service.enrich_next_cards(db_session, limit=5)

        mock_scrape.assert_not_called()
        db_session.refresh(card)
        assert card.ingredient_keys is None

    def test_no_recipe_row_created(self, db_session):
        """enrich_next_cards never creates Recipe rows."""
        _make_enrich_card(db_session, n=0)
        before = db_session.query(Recipe).count()

        mock_rp, mock_rl = _mock_robots_rate()
        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch("src.services.catalog_service.scrape_recipe", return_value=_scraped(["chicken"])),
        ):
            catalog_service.enrich_next_cards(db_session, limit=5)

        assert db_session.query(Recipe).count() == before

    def test_orders_by_collection_count_descending(self, db_session):
        """Cards in more collections are processed before cards in fewer."""
        coll_a = _seed_collection(db_session, slug="collection-a")
        coll_b = _seed_collection(db_session, slug="collection-b")

        single_coll_card = _make_enrich_card(
            db_session,
            recipe_url="https://www.hellofresh.com/recipes/single-{n}-aabbccdd1122334455667788",
            n=0,
        )
        two_coll_card = _make_enrich_card(
            db_session,
            recipe_url="https://www.hellofresh.com/recipes/two-{n}-aabbccdd1122334455667788",
            n=1,
        )

        _add_card_to_collection(db_session, single_coll_card, coll_a, position=0)
        _add_card_to_collection(db_session, two_coll_card, coll_a, position=1)
        _add_card_to_collection(db_session, two_coll_card, coll_b, position=0)

        scraped_order = []

        def tracking_scrape(url):
            scraped_order.append(url)
            return _scraped([])

        mock_rp, mock_rl = _mock_robots_rate()
        with (
            patch("src.services.catalog_service.RobotsTxtParser", return_value=mock_rp),
            patch("src.services.catalog_service.RateLimiter", return_value=mock_rl),
            patch("src.services.catalog_service.scrape_recipe", side_effect=tracking_scrape),
        ):
            catalog_service.enrich_next_cards(db_session, limit=2)

        assert len(scraped_order) == 2
        assert two_coll_card.recipe_url == scraped_order[0]


# ---------------------------------------------------------------------------
# card_enrichment_worker
# ---------------------------------------------------------------------------


class TestCardEnrichmentWorker:
    async def test_worker_calls_enrich_with_configured_batch_size(self, monkeypatch, caplog):
        """Worker calls enrich_next_cards with catalog_enrich_batch_size each pass."""
        enrich_calls = []

        def mock_enrich(db, limit=5):
            enrich_calls.append(limit)
            return 2

        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        mock_settings = MagicMock()
        mock_settings.catalog_enrich_batch_size = 7
        mock_settings.catalog_enrich_interval_seconds = 300

        async def mock_sleep(_):
            raise asyncio.CancelledError()

        with (
            patch("src.services.catalog_service.get_settings", return_value=mock_settings),
            patch("src.services.catalog_service.get_session_factory", return_value=mock_factory),
            patch("src.services.catalog_service.enrich_next_cards", side_effect=mock_enrich),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await catalog_service.card_enrichment_worker()

        assert len(enrich_calls) == 1
        assert enrich_calls[0] == mock_settings.catalog_enrich_batch_size

    async def test_worker_logs_enriched_count(self, monkeypatch, caplog):
        """Worker logs 'enriched N card(s)' after each successful pass."""
        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        async def mock_sleep(_):
            raise asyncio.CancelledError()

        with (
            patch("src.services.catalog_service.get_session_factory", return_value=mock_factory),
            patch("src.services.catalog_service.enrich_next_cards", return_value=3),
            patch("asyncio.sleep", side_effect=mock_sleep),
            caplog.at_level(logging.INFO, logger="src.services.catalog_service"),
        ):
            with pytest.raises(asyncio.CancelledError):
                await catalog_service.card_enrichment_worker()

        assert any("enriched 3 card(s)" in r.message for r in caplog.records)

    async def test_worker_survives_exception_from_enrich(self, monkeypatch, caplog):
        """Worker catches exceptions from enrich_next_cards and continues the loop."""
        call_count = [0]

        def mock_enrich(db, limit=5):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("simulated enrich failure")
            return 1

        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        sleep_count = [0]

        async def mock_sleep(_):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise asyncio.CancelledError()

        with (
            patch("src.services.catalog_service.get_session_factory", return_value=mock_factory),
            patch("src.services.catalog_service.enrich_next_cards", side_effect=mock_enrich),
            patch("asyncio.sleep", side_effect=mock_sleep),
            caplog.at_level(logging.ERROR, logger="src.services.catalog_service"),
        ):
            with pytest.raises(asyncio.CancelledError):
                await catalog_service.card_enrichment_worker()

        # Worker ran two passes: first raised, second succeeded
        assert call_count[0] == 2
        assert any("Card enrichment worker error" in r.message for r in caplog.records)

    async def test_interval_zero_starts_no_worker(self, monkeypatch):
        """When catalog_enrich_interval_seconds=0, the lifespan skips the enrichment worker."""
        import src.main as main_module
        from src.main import app

        async def _noop_coro():
            pass

        with (
            patch.object(main_module, "init_engine"),
            patch.object(main_module, "_ensure_schema"),
            patch.object(main_module, "_ensure_seed_data"),
            patch.object(main_module, "prune_unpersisted_recipes", return_value=0),
            patch.object(main_module, "background_task_worker", return_value=_noop_coro()),
            patch.object(main_module, "get_session_factory") as mock_sf,
            patch.object(main_module, "settings") as mock_s,
            patch.object(main_module, "card_enrichment_worker") as mock_ew,
        ):
            mock_s.catalog_enrich_interval_seconds = 0
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_sf.return_value.return_value = mock_ctx

            async with main_module.lifespan(app):
                pass

        mock_ew.assert_not_called()
