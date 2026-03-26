"""
Integration tests for scraper endpoints.

Tests cover:
- POST /scraper/import-url: single URL import (any authenticated user)
- POST /scraper/import-batch: batch URL import (coordinator only)
- POST /scraper/discover/{source}: URL discovery (coordinator only)
- POST /scraper/discover-and-import/{source}: discover + import (coordinator only)
- GET /scraper/status: import statistics (any authenticated user)
- Authorization checks (coordinator vs member)
- Error handling and validation
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe, SourceType
from src.services.auth_service import hash_password, create_access_token
from src.schemas.import_service import ImportResult, ImportStatus, BatchImportResult

from fastapi import FastAPI
from src.routers import scraper as scraper_router

# Create a test app without lifespan
app = FastAPI(
    title="FreshUp",
    description="Privacy-first kitchen management system",
    version="0.1.0",
)

# Register the scraper router
app.include_router(scraper_router.router)

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


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def coordinator_user(db_session):
    """Create a coordinator test user."""
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
def member_user(db_session):
    """Create a member test user."""
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
def coordinator_headers(coordinator_user):
    """Generate authorization headers for coordinator user."""
    access_token = create_access_token({"sub": str(coordinator_user.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def member_headers(member_user):
    """Generate authorization headers for member user."""
    access_token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {access_token}"}


class TestImportUrl:
    """Test POST /scraper/import-url endpoint."""

    @patch("src.routers.scraper.import_recipe_from_url")
    def test_import_url_success_as_member(self, mock_import, client, member_headers, db_session):
        """Member can import a single URL successfully."""
        recipe_id = uuid4()
        mock_import.return_value = ImportResult(
            status=ImportStatus.success,
            recipe_id=recipe_id,
            warnings=[],
            error_message=None,
            source_url="https://www.hellofresh.com/recipes/test-recipe"
        )

        response = client.post(
            "/scraper/import-url",
            json={"url": "https://www.hellofresh.com/recipes/test-recipe"},
            headers=member_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["recipe_id"] == str(recipe_id)
        mock_import.assert_called_once()

    @patch("src.routers.scraper.import_recipe_from_url")
    def test_import_url_duplicate(self, mock_import, client, member_headers, db_session):
        """Import returns duplicate status for existing recipe."""
        recipe_id = uuid4()
        mock_import.return_value = ImportResult(
            status=ImportStatus.duplicate,
            recipe_id=recipe_id,
            warnings=[],
            error_message=None,
            source_url="https://www.hellofresh.com/recipes/test-recipe"
        )

        response = client.post(
            "/scraper/import-url",
            json={"url": "https://www.hellofresh.com/recipes/test-recipe"},
            headers=member_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "duplicate"
        assert data["recipe_id"] == str(recipe_id)

    def test_import_url_requires_auth(self, client):
        """Import URL requires authentication."""
        response = client.post(
            "/scraper/import-url",
            json={"url": "https://www.hellofresh.com/recipes/test-recipe"}
        )

        assert response.status_code == 401


class TestImportBatch:
    """Test POST /scraper/import-batch endpoint."""

    @patch("src.routers.scraper.import_batch")
    def test_import_batch_success_as_coordinator(self, mock_batch, client, coordinator_headers, db_session):
        """Coordinator can import batch URLs successfully."""
        mock_batch.return_value = BatchImportResult(
            total=3,
            imported=2,
            duplicates=1,
            errors=0,
            results=[]
        )

        response = client.post(
            "/scraper/import-batch",
            json={"urls": ["https://www.hellofresh.com/recipes/1", "https://www.hellofresh.com/recipes/2", "https://www.hellofresh.com/recipes/3"]},
            headers=coordinator_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["imported"] == 2
        assert data["duplicates"] == 1
        assert data["errors"] == 0

    def test_import_batch_forbidden_for_member(self, client, member_headers):
        """Member cannot import batch URLs (coordinator only)."""
        response = client.post(
            "/scraper/import-batch",
            json={"urls": ["https://www.hellofresh.com/recipes/1"]},
            headers=member_headers
        )

        assert response.status_code == 403
        assert "Coordinator role required" in response.json()["detail"]

    def test_import_batch_requires_auth(self, client):
        """Import batch requires authentication."""
        response = client.post(
            "/scraper/import-batch",
            json={"urls": ["https://www.hellofresh.com/recipes/1"]}
        )

        assert response.status_code == 401


class TestDiscover:
    """Test POST /scraper/discover/{source} endpoint."""

    @patch("src.routers.scraper.HelloFreshCrawler")
    def test_discover_hellofresh_success(self, mock_crawler_class, client, coordinator_headers):
        """Coordinator can discover HelloFresh URLs."""
        mock_crawler = MagicMock()
        mock_crawler.discover_recipe_urls.return_value = [
            "https://www.hellofresh.com/recipes/recipe-1",
            "https://www.hellofresh.com/recipes/recipe-2"
        ]
        mock_crawler_class.return_value = mock_crawler

        response = client.post(
            "/scraper/discover/hellofresh",
            headers=coordinator_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "hellofresh"
        assert data["count"] == 2
        assert len(data["urls"]) == 2

    @patch("src.routers.scraper.KitchenSanctuaryCrawler")
    def test_discover_kitchen_sanctuary_success(self, mock_crawler_class, client, coordinator_headers):
        """Coordinator can discover Kitchen Sanctuary URLs."""
        mock_crawler = MagicMock()
        mock_crawler.discover_recipe_urls.return_value = [
            "https://www.kitchensanctuary.com/recipe-1"
        ]
        mock_crawler_class.return_value = mock_crawler

        response = client.post(
            "/scraper/discover/kitchen_sanctuary",
            headers=coordinator_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "kitchen_sanctuary"
        assert data["count"] == 1

    def test_discover_forbidden_for_member(self, client, member_headers):
        """Member cannot discover URLs (coordinator only)."""
        response = client.post(
            "/scraper/discover/hellofresh",
            headers=member_headers
        )

        assert response.status_code == 403

    def test_discover_requires_auth(self, client):
        """Discover requires authentication."""
        response = client.post("/scraper/discover/hellofresh")
        assert response.status_code == 401

    def test_discover_invalid_source(self, client, coordinator_headers):
        """Invalid source returns 422."""
        response = client.post(
            "/scraper/discover/invalid_source",
            headers=coordinator_headers
        )

        assert response.status_code == 422

    @patch("src.routers.scraper.HelloFreshCrawler")
    def test_discover_with_max_pages_parameter(self, mock_crawler_class, client, coordinator_headers):
        """Max_pages parameter is passed to crawler."""
        mock_crawler = MagicMock()
        mock_crawler.discover_recipe_urls.return_value = [
            "https://www.hellofresh.com/recipes/recipe-1"
        ]
        mock_crawler_class.return_value = mock_crawler

        response = client.post(
            "/scraper/discover/hellofresh?max_pages=5",
            headers=coordinator_headers
        )

        assert response.status_code == 200
        # Verify that max_pages was passed to the crawler
        mock_crawler.discover_recipe_urls.assert_called_once_with(max_pages=5)


class TestDiscoverAndImport:
    """Test POST /scraper/discover-and-import/{source} endpoint."""

    @patch("src.routers.scraper.import_batch")
    @patch("src.routers.scraper.HelloFreshCrawler")
    def test_discover_and_import_success(self, mock_crawler_class, mock_batch, client, coordinator_headers, db_session):
        """Coordinator can discover and import recipes."""
        mock_crawler = MagicMock()
        mock_crawler.discover_recipe_urls.return_value = [
            f"https://www.hellofresh.com/recipes/recipe-{i}" for i in range(100)
        ]
        mock_crawler_class.return_value = mock_crawler

        mock_batch.return_value = BatchImportResult(
            total=50,
            imported=45,
            duplicates=3,
            errors=2,
            results=[]
        )

        response = client.post(
            "/scraper/discover-and-import/hellofresh",
            json={"max_recipes": 50},
            headers=coordinator_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50
        assert data["imported"] == 45

        # Verify that import_batch was called with limited URLs (50, not 100)
        mock_batch.assert_called_once()
        urls_arg = mock_batch.call_args[0][0]
        assert len(urls_arg) == 50

    def test_discover_and_import_forbidden_for_member(self, client, member_headers):
        """Member cannot discover and import (coordinator only)."""
        response = client.post(
            "/scraper/discover-and-import/hellofresh",
            headers=member_headers
        )

        assert response.status_code == 403

    def test_discover_and_import_requires_auth(self, client):
        """Discover-and-import requires authentication."""
        response = client.post("/scraper/discover-and-import/hellofresh")
        assert response.status_code == 401


class TestStatus:
    """Test GET /scraper/status endpoint."""

    def test_status_success(self, client, member_headers, db_session):
        """Any authenticated user can view import statistics."""
        # Create some test recipes
        recipe1 = Recipe(
            id=uuid4(),
            name="Recipe 1",
            source_type=SourceType.hellofresh_web.value,
            created_by=None,
            base_servings=4
        )
        recipe2 = Recipe(
            id=uuid4(),
            name="Recipe 2",
            source_type=SourceType.kitchen_sanctuary.value,
            created_by=None,
            base_servings=4
        )
        recipe3 = Recipe(
            id=uuid4(),
            name="Recipe 3",
            source_type=SourceType.hellofresh_web.value,
            created_by=None,
            base_servings=4
        )
        db_session.add_all([recipe1, recipe2, recipe3])
        db_session.commit()

        response = client.get("/scraper/status", headers=member_headers)

        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        stats = {item["source_type"]: item["count"] for item in data["stats"]}
        assert stats[SourceType.hellofresh_web.value] == 2
        assert stats[SourceType.kitchen_sanctuary.value] == 1

    def test_status_empty_database(self, client, member_headers, db_session):
        """Status returns empty stats when no recipes exist."""
        response = client.get("/scraper/status", headers=member_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["stats"] == []

    def test_status_requires_auth(self, client):
        """Status requires authentication."""
        response = client.get("/scraper/status")
        assert response.status_code == 401
