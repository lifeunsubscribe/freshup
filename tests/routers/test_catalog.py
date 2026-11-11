"""
Integration tests for catalog endpoints.

Tests cover:
- GET /catalog/{source}/collections: list top-level collections with optional seeding
- GET /catalog/{source}/collections/{slug}: collection detail with fetch-on-demand
- Staleness / ?fresh param behaviour
- Error cases: unknown slug, fetch failure (with/without stored cards)
- Member (non-coordinator) access
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.db import models
from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.db.models.user import User, UserRole
from src.services.auth_service import hash_password, create_access_token
from src.schemas.catalog import CollectionCard, CollectionChild, CollectionPage
from src.schemas.import_service import ImportResult, ImportStatus
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError
from src.routers import catalog as catalog_router_module

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.middleware.rate_limit import limiter

TEST_DATABASE_URL = "sqlite:///:memory:"
HELLOFRESH_SOURCE = "hellofresh_web"

# Minimal test app
app = FastAPI(title="FreshUp", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(catalog_router_module.router)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")
    monkeypatch.setenv("CATALOG_REFRESH_HOURS", "24")
    get_settings.cache_clear()
    limiter.reset()


@pytest.fixture
def db_session():
    _ = models  # register all models
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


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def member_user(db_session):
    user = User(
        id=uuid4(),
        email="member@example.com",
        hashed_password=hash_password("testpassword123"),
        name="Member User",
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def coordinator_user(db_session):
    user = User(
        id=uuid4(),
        email="coordinator@example.com",
        hashed_password=hash_password("testpassword123"),
        name="Coordinator User",
        role=UserRole.coordinator.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_headers(member_user):
    token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def coordinator_headers(coordinator_user):
    token = create_access_token({"sub": str(coordinator_user.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page(slug: str = "vegetarian-recipes", n_cards: int = 3, n_children: int = 2) -> CollectionPage:
    cards = [
        CollectionCard(
            external_id=f"id{i:024x}",
            name=f"Recipe {i}",
            image_url=f"https://img.hellofresh.com/image/recipe{i}.jpg",
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


SAMPLE_SITEMAP = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.hellofresh.com/recipes/vegetarian-recipes</loc></url>
  <url><loc>https://www.hellofresh.com/recipes/pasta-recipes</loc></url>
</urlset>
"""


def _mock_seed(monkeypatch, db_session, slugs=("vegetarian-recipes", "pasta-recipes")):
    """Directly insert seed rows without hitting the network."""
    from src.services import catalog_service

    def fake_seed(db):
        for slug in slugs:
            db.add(SourceCollection(
                source_type=HELLOFRESH_SOURCE,
                slug=slug,
                name=catalog_service._slug_to_name(slug),
                url=f"https://www.hellofresh.com/recipes/{slug}",
                last_fetched_at=None,
                parent_slug=None,
            ))
        db.commit()
        return len(slugs)

    monkeypatch.setattr("src.routers.catalog.catalog_service.seed_hellofresh_collections", fake_seed)


# ---------------------------------------------------------------------------
# List collections
# ---------------------------------------------------------------------------


class TestListCollections:
    def test_seeds_on_first_call_and_returns_collections(self, client, db_session, member_headers, monkeypatch):
        _mock_seed(monkeypatch, db_session)
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        slugs = {d["slug"] for d in data}
        assert slugs == {"vegetarian-recipes", "pasta-recipes"}

    def test_returns_sorted_by_name(self, client, db_session, member_headers, monkeypatch):
        _mock_seed(monkeypatch, db_session, slugs=("zucchini-recipes", "apple-recipes", "mango-recipes"))
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 200
        names = [d["name"] for d in response.json()]
        assert names == sorted(names)

    def test_does_not_seed_when_rows_exist(self, client, db_session, member_headers, monkeypatch):
        from src.services import catalog_service

        # Pre-seed directly
        db_session.add(SourceCollection(
            source_type=HELLOFRESH_SOURCE,
            slug="existing-slug",
            name="Existing",
            url="https://www.hellofresh.com/recipes/existing-slug",
            last_fetched_at=None,
            parent_slug=None,
        ))
        db_session.commit()

        seed_called = []

        def fake_seed(db):
            seed_called.append(True)
            return 0

        monkeypatch.setattr("src.routers.catalog.catalog_service.seed_hellofresh_collections", fake_seed)

        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 200
        assert not seed_called

    def test_unknown_source_returns_404(self, client, member_headers):
        response = client.get("/catalog/unknown_source/collections", headers=member_headers)
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, client):
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections")
        assert response.status_code == 401

    def test_member_can_call_list(self, client, db_session, member_headers, monkeypatch):
        _mock_seed(monkeypatch, db_session)
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 200

    def test_seed_network_error_returns_400(self, client, db_session, member_headers, monkeypatch):
        monkeypatch.setattr(
            "src.routers.catalog.catalog_service.seed_hellofresh_collections",
            lambda db: (_ for _ in ()).throw(CrawlerNetworkError("unreachable")),
        )
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 400

    def test_seed_parse_error_returns_400(self, client, db_session, member_headers, monkeypatch):
        monkeypatch.setattr(
            "src.routers.catalog.catalog_service.seed_hellofresh_collections",
            lambda db: (_ for _ in ()).throw(CrawlerParseError("bad xml")),
        )
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 400

    def test_includes_card_count(self, client, db_session, member_headers, monkeypatch):
        _mock_seed(monkeypatch, db_session)
        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 200
        for item in response.json():
            assert "card_count" in item
            assert item["card_count"] == 0  # not yet fetched

    def test_seed_integrity_error_rolls_back_and_returns_200(self, client, db_session, member_headers, monkeypatch):
        """Concurrent seed race: IntegrityError is caught, session rolled back, endpoint still returns 200."""
        from sqlalchemy.exc import IntegrityError

        def fake_seed_raises(db):
            raise IntegrityError("UNIQUE constraint", {}, Exception("unique violation"))

        monkeypatch.setattr("src.routers.catalog.catalog_service.seed_hellofresh_collections", fake_seed_raises)

        response = client.get(f"/catalog/{HELLOFRESH_SOURCE}/collections", headers=member_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Detail — fetch on demand
# ---------------------------------------------------------------------------


class TestCollectionDetail:
    def _pre_seed_collection(self, db_session, slug="vegetarian-recipes", fetched_hours_ago=None):
        last = None
        if fetched_hours_ago is not None:
            last = datetime.now(timezone.utc) - timedelta(hours=fetched_hours_ago)
        coll = SourceCollection(
            source_type=HELLOFRESH_SOURCE,
            slug=slug,
            name="Vegetarian Recipes",
            url=f"https://www.hellofresh.com/recipes/{slug}",
            last_fetched_at=last,
            parent_slug=None,
        )
        db_session.add(coll)
        db_session.commit()
        return coll

    def test_calls_fetch_on_never_fetched(self, client, db_session, member_headers):
        self._pre_seed_collection(db_session)
        page = _make_page(n_cards=3, n_children=2)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        assert response.status_code == 200
        mock_crawler.fetch_collection.assert_called_once_with("vegetarian-recipes")
        data = response.json()
        assert len(data["cards"]) == 3
        assert len(data["children"]) == 2

    def test_no_fetch_when_fresh(self, client, db_session, member_headers):
        """Collection fetched 1 hour ago is not stale and not re-fetched."""
        self._pre_seed_collection(db_session, fetched_hours_ago=1)

        mock_crawler = MagicMock()

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        mock_crawler.fetch_collection.assert_not_called()
        assert response.status_code == 200

    def test_fetches_when_stale(self, client, db_session, member_headers):
        """Collection fetched 25 hours ago (beyond default 24h) is re-fetched."""
        self._pre_seed_collection(db_session, fetched_hours_ago=25)
        page = _make_page(n_cards=1, n_children=0)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        mock_crawler.fetch_collection.assert_called_once()
        assert response.status_code == 200

    def test_fresh_false_never_fetches(self, client, db_session, member_headers):
        """?fresh=false skips the fetch even when last_fetched_at is null."""
        self._pre_seed_collection(db_session)  # never fetched

        mock_crawler = MagicMock()

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes?fresh=false",
                headers=member_headers,
            )

        mock_crawler.fetch_collection.assert_not_called()
        assert response.status_code == 200

    def test_fresh_true_always_fetches(self, client, db_session, member_headers):
        """?fresh=true forces fetch even when recently fetched."""
        self._pre_seed_collection(db_session, fetched_hours_ago=0)  # just fetched
        page = _make_page(n_cards=1, n_children=0)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes?fresh=true",
                headers=member_headers,
            )

        mock_crawler.fetch_collection.assert_called_once()
        assert response.status_code == 200

    def test_unknown_source_returns_404(self, client, member_headers):
        response = client.get(
            "/catalog/unknown_source/collections/some-slug",
            headers=member_headers,
        )
        assert response.status_code == 404

    def test_unknown_slug_returns_404(self, client, member_headers):
        response = client.get(
            f"/catalog/{HELLOFRESH_SOURCE}/collections/no-such-slug",
            headers=member_headers,
        )
        assert response.status_code == 404

    def test_fetch_failure_with_stored_cards_returns_200_with_error(
        self, client, db_session, member_headers
    ):
        """Fetch fails but stored cards exist → HTTP 200 with fetch_error field."""
        from src.services import catalog_service as svc

        coll = self._pre_seed_collection(db_session, fetched_hours_ago=25)
        # Pre-store cards
        page = _make_page(n_cards=2, n_children=0)
        svc.upsert_collection_page(db_session, page)
        # Make stale again after upsert
        coll.last_fetched_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db_session.commit()

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.side_effect = CrawlerNetworkError("timed out")

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["fetch_error"] is not None
        assert len(data["cards"]) == 2

    def test_fetch_failure_without_stored_cards_returns_400(
        self, client, db_session, member_headers
    ):
        """Fetch fails and no cards stored → HTTP 400."""
        self._pre_seed_collection(db_session)  # never fetched, no cards

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.side_effect = CrawlerNetworkError("refused")

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        assert response.status_code == 400

    def test_member_can_call_detail(self, client, db_session, member_headers):
        self._pre_seed_collection(db_session, fetched_hours_ago=1)
        response = client.get(
            f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
            headers=member_headers,
        )
        assert response.status_code == 200

    def test_coordinator_can_call_detail(self, client, db_session, coordinator_headers):
        self._pre_seed_collection(db_session, fetched_hours_ago=1)
        response = client.get(
            f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
            headers=coordinator_headers,
        )
        assert response.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        response = client.get(
            f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes"
        )
        assert response.status_code == 401

    def test_response_includes_all_card_fields(self, client, db_session, member_headers):
        self._pre_seed_collection(db_session)
        page = _make_page(n_cards=1, n_children=0)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        assert response.status_code == 200
        card = response.json()["cards"][0]
        for field in ("id", "name", "image_url", "recipe_url", "is_persisted"):
            assert field in card
        assert card["is_persisted"] is False  # not yet imported

    def test_children_returned_in_detail(self, client, db_session, member_headers):
        self._pre_seed_collection(db_session)
        page = _make_page(n_cards=0, n_children=2)

        mock_crawler = MagicMock()
        mock_crawler.fetch_collection.return_value = page

        with patch("src.services.catalog_service._make_crawler", return_value=mock_crawler):
            response = client.get(
                f"/catalog/{HELLOFRESH_SOURCE}/collections/vegetarian-recipes",
                headers=member_headers,
            )

        assert response.status_code == 200
        children = response.json()["children"]
        assert len(children) == 2
        slugs = {c["slug"] for c in children}
        assert slugs == {"child-0", "child-1"}


# ---------------------------------------------------------------------------
# Open card
# ---------------------------------------------------------------------------


def _make_db_recipe(db, is_persisted=False) -> Recipe:
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


def _make_db_card(db, recipe_id=None) -> SourceRecipeCard:
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


def _success_result(recipe_id):
    return ImportResult(
        status=ImportStatus.success,
        recipe_id=recipe_id,
        warnings=[],
        error_message=None,
        source_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
    )


def _error_result():
    return ImportResult(
        status=ImportStatus.error,
        recipe_id=None,
        warnings=[],
        error_message="Scraping failed: connection refused",
        source_url="https://www.hellofresh.com/recipes/test-recipe-aabbccdd1122334455667788",
    )


class TestOpenCard:
    def test_unlinked_card_imports_and_returns_recipe_with_ingredients(
        self, client, db_session, member_headers
    ):
        """Opening an unlinked card calls import, links it, and returns a recipe with ingredients key."""
        recipe = _make_db_recipe(db_session)
        card = _make_db_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_success_result(recipe.id),
        ):
            response = client.post(f"/catalog/cards/{card.id}/open", headers=member_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(recipe.id)
        assert "ingredients" in data
        assert response.headers.get("x-freshup-imported") == "true"

    def test_opening_again_skips_import_and_returns_same_recipe_id(
        self, client, db_session, member_headers
    ):
        """Second open returns the already-linked recipe without calling import."""
        recipe = _make_db_recipe(db_session)
        card = _make_db_card(db_session, recipe_id=recipe.id)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
        ) as mock_import:
            response = client.post(f"/catalog/cards/{card.id}/open", headers=member_headers)

        mock_import.assert_not_called()
        assert response.status_code == 200
        assert response.json()["id"] == str(recipe.id)
        assert response.headers.get("x-freshup-imported") == "false"

    def test_import_error_returns_502_and_card_stays_unlinked(
        self, client, db_session, member_headers
    ):
        """Import error → 502; card.recipe_id remains None."""
        card = _make_db_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_error_result(),
        ):
            response = client.post(f"/catalog/cards/{card.id}/open", headers=member_headers)

        assert response.status_code == 502
        db_session.refresh(card)
        assert card.recipe_id is None

    def test_returned_recipe_has_is_persisted_false(
        self, client, db_session, member_headers
    ):
        """The opened recipe has is_persisted=False (browse cache semantics)."""
        recipe = _make_db_recipe(db_session, is_persisted=False)
        card = _make_db_card(db_session)

        with patch(
            "src.services.catalog_service.import_recipe_from_url",
            return_value=_success_result(recipe.id),
        ):
            response = client.post(f"/catalog/cards/{card.id}/open", headers=member_headers)

        assert response.status_code == 200
        assert response.json()["is_persisted"] is False

    def test_unknown_card_returns_404(self, client, member_headers):
        """Non-existent card_id → 404."""
        from uuid import uuid4
        response = client.post(f"/catalog/cards/{uuid4()}/open", headers=member_headers)
        assert response.status_code == 404

    def test_member_token_allowed(self, client, db_session, member_headers):
        """Member (non-coordinator) can open a card."""
        recipe = _make_db_recipe(db_session)
        card = _make_db_card(db_session, recipe_id=recipe.id)
        response = client.post(f"/catalog/cards/{card.id}/open", headers=member_headers)
        assert response.status_code == 200

    def test_unauthenticated_returns_401(self, client, db_session):
        """Missing auth token → 401."""
        card = _make_db_card(db_session)
        response = client.post(f"/catalog/cards/{card.id}/open")
        assert response.status_code == 401
