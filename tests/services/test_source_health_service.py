"""
Tests for the source health check service.

Covers:
- HelloFresh check: healthy on full recipe, failing on scraper error or thin result
- Kitchen Sanctuary check: healthy on 200+item feed, failing on 403 or empty feed
- run_due_checks: skips recently checked sources, runs overdue / never-checked ones
- Worker loop: survives a check that raises
- _failing_since: returns first row of consecutive failing streak
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.db.database import Base
from src.db import models  # noqa: F401 — registers all tables with Base.metadata
from src.db.models.source_health import SourceHealthCheck
from src.services.source_health_service import (
    check_source,
    run_due_checks,
    latest_status,
    _failing_since,
    MONITORED_SOURCES,
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SOURCE_HEALTH_INTERVAL_HOURS", "24")
    monkeypatch.setenv(
        "SOURCE_HEALTH_CANARY_HELLOFRESH",
        "https://www.hellofresh.com/recipes/test-canary",
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# check_source — HelloFresh
# ---------------------------------------------------------------------------

class TestCheckSourceHelloFresh:
    def _make_scraped_data(self, title="Canary Recipe", ingredients=None, instructions=None):
        from src.schemas.scraper import ScrapedRecipeData
        return ScrapedRecipeData(
            source_url="https://www.hellofresh.com/recipes/test-canary",
            source_type="hellofresh_web",
            title=title,
            ingredients=ingredients if ingredients is not None else ["a", "b", "c", "d", "e"],
            instructions=instructions if instructions is not None else ["step1", "step2", "step3"],
        )

    def test_healthy_on_full_recipe(self):
        scraped = self._make_scraped_data()
        with patch("src.services.scraper_service.scrape_recipe", return_value=scraped):
            row = check_source("hellofresh_web")
        assert row.status == "healthy"
        assert row.import_mode == "link"
        assert row.detail is None
        assert row.source_type == "hellofresh_web"
        assert isinstance(row.duration_ms, int)

    def test_failing_when_scraper_raises(self):
        from src.services.scraper_service import ScraperError
        with patch(
            "src.services.scraper_service.scrape_recipe",
            side_effect=ScraperError("network timeout"),
        ):
            row = check_source("hellofresh_web")
        assert row.status == "failing"
        assert row.detail is not None
        assert row.import_mode == "link"

    def test_failing_when_too_few_ingredients(self):
        scraped = self._make_scraped_data(ingredients=["a", "b"])
        with patch("src.services.scraper_service.scrape_recipe", return_value=scraped):
            row = check_source("hellofresh_web")
        assert row.status == "failing"
        assert row.detail is not None
        assert "ingredients" in row.detail

    def test_failing_when_too_few_instructions(self):
        scraped = self._make_scraped_data(instructions=["step1"])
        with patch("src.services.scraper_service.scrape_recipe", return_value=scraped):
            row = check_source("hellofresh_web")
        assert row.status == "failing"
        assert "instructions" in row.detail

    def test_failing_when_no_title(self):
        scraped = self._make_scraped_data(title=None)
        with patch("src.services.scraper_service.scrape_recipe", return_value=scraped):
            row = check_source("hellofresh_web")
        assert row.status == "failing"

    def test_healthy_full_recipe_direct(self):
        from src.schemas.scraper import ScrapedRecipeData
        scraped = ScrapedRecipeData(
            source_url="https://www.hellofresh.com/recipes/test-canary",
            source_type="hellofresh_web",
            title="Good Recipe",
            ingredients=["a", "b", "c", "d", "e"],
            instructions=["step1", "step2", "step3"],
        )
        with patch("src.services.scraper_service.scrape_recipe", return_value=scraped):
            row = check_source("hellofresh_web")
        assert row.status == "healthy"
        assert row.detail is None

    def test_scraper_exception_yields_failing(self):
        from src.services.scraper_service import NetworkError
        with patch(
            "src.services.scraper_service.scrape_recipe",
            side_effect=NetworkError("connection refused"),
        ):
            row = check_source("hellofresh_web")
        assert row.status == "failing"
        assert row.detail is not None


# ---------------------------------------------------------------------------
# check_source — Kitchen Sanctuary
# ---------------------------------------------------------------------------

class TestCheckSourceKitchenSanctuary:
    def _mock_response(self, status_code=200, text="<rss><channel><item><title>Pie</title></item></channel></rss>"):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text
        return mock_resp

    def test_healthy_on_200_with_item(self):
        with patch("src.services.source_health_service.requests.get",
                   return_value=self._mock_response()):
            row = check_source("kitchen_sanctuary")
        assert row.status == "healthy"
        assert row.import_mode == "saved_page"
        assert row.detail is None

    def test_failing_on_403(self):
        with patch("src.services.source_health_service.requests.get",
                   return_value=self._mock_response(status_code=403, text="")):
            row = check_source("kitchen_sanctuary")
        assert row.status == "failing"
        assert "403" in row.detail

    def test_failing_on_empty_feed(self):
        with patch("src.services.source_health_service.requests.get",
                   return_value=self._mock_response(text="<rss><channel></channel></rss>")):
            row = check_source("kitchen_sanctuary")
        assert row.status == "failing"
        assert row.detail is not None

    def test_failing_on_timeout(self):
        import requests as req
        with patch("src.services.source_health_service.requests.get",
                   side_effect=req.exceptions.Timeout()):
            row = check_source("kitchen_sanctuary")
        assert row.status == "failing"

    def test_failing_on_connection_error(self):
        import requests as req
        with patch("src.services.source_health_service.requests.get",
                   side_effect=req.exceptions.ConnectionError("refused")):
            row = check_source("kitchen_sanctuary")
        assert row.status == "failing"


# ---------------------------------------------------------------------------
# run_due_checks — interval gate
# ---------------------------------------------------------------------------

class TestRunDueChecks:
    def _insert_check(self, db, source_type, checked_at, status="healthy"):
        row = SourceHealthCheck(
            source_type=source_type,
            checked_at=checked_at,
            status=status,
            import_mode="link",
            duration_ms=100,
        )
        db.add(row)
        db.commit()
        return row

    def test_skips_source_checked_1_hour_ago(self, db_session, monkeypatch):
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("SOURCE_HEALTH_INTERVAL_HOURS", "24")
        get_settings.cache_clear()

        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        self._insert_check(db_session, "hellofresh_web", recent)
        self._insert_check(db_session, "kitchen_sanctuary", recent)

        with patch("src.services.source_health_service.check_source") as mock_check:
            run_due_checks(db_session)
            mock_check.assert_not_called()

    def test_runs_source_checked_25_hours_ago(self, db_session, monkeypatch):
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("SOURCE_HEALTH_INTERVAL_HOURS", "24")
        get_settings.cache_clear()

        old = datetime.now(timezone.utc) - timedelta(hours=25)
        self._insert_check(db_session, "hellofresh_web", old)
        # kitchen_sanctuary not inserted — never checked

        healthy_row = SourceHealthCheck(
            source_type="x", checked_at=datetime.now(timezone.utc),
            status="healthy", import_mode="link", duration_ms=50,
        )

        with patch(
            "src.services.source_health_service.check_source",
            return_value=healthy_row,
        ) as mock_check:
            run_due_checks(db_session)

        called_sources = {call.args[0] for call in mock_check.call_args_list}
        assert "hellofresh_web" in called_sources
        assert "kitchen_sanctuary" in called_sources

    def test_runs_never_checked_source(self, db_session):
        # No rows at all — both sources should be checked
        healthy_row = SourceHealthCheck(
            source_type="x", checked_at=datetime.now(timezone.utc),
            status="healthy", import_mode="link", duration_ms=50,
        )
        with patch(
            "src.services.source_health_service.check_source",
            return_value=healthy_row,
        ) as mock_check:
            run_due_checks(db_session)

        assert mock_check.call_count == len(MONITORED_SOURCES)

    def test_survives_check_that_raises(self, db_session):
        """Worker loop must survive a check that raises; the loop should not propagate."""
        with patch(
            "src.services.source_health_service.check_source",
            side_effect=RuntimeError("unexpected failure"),
        ):
            # Should not raise
            run_due_checks(db_session)

    def test_saves_result_to_db(self, db_session, monkeypatch):
        from src.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("SOURCE_HEALTH_INTERVAL_HOURS", "0")
        get_settings.cache_clear()

        healthy_row = SourceHealthCheck(
            source_type="hellofresh_web",
            checked_at=datetime.now(timezone.utc),
            status="healthy",
            import_mode="link",
            duration_ms=50,
        )
        with patch(
            "src.services.source_health_service.check_source",
            return_value=healthy_row,
        ):
            run_due_checks(db_session)

        from sqlalchemy import select
        rows = list(db_session.execute(select(SourceHealthCheck)).scalars().all())
        assert any(r.source_type == "hellofresh_web" for r in rows)


# ---------------------------------------------------------------------------
# _failing_since
# ---------------------------------------------------------------------------

class TestFailingSince:
    def _row(self, status, checked_at):
        r = SourceHealthCheck(
            source_type="hellofresh_web",
            checked_at=checked_at,
            status=status,
            import_mode="link",
            duration_ms=10,
        )
        return r

    def test_returns_none_when_latest_is_healthy(self):
        t = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
        rows = [self._row("healthy", t)]
        assert _failing_since(rows) is None

    def test_returns_none_for_empty_list(self):
        assert _failing_since([]) is None

    def test_returns_first_failing_row(self):
        t0 = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 9, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
        # Newest first
        rows = [
            self._row("failing", t2),
            self._row("failing", t1),
            self._row("healthy", t0),
        ]
        result = _failing_since(rows)
        assert result == t1

    def test_single_failing_row(self):
        t = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
        rows = [self._row("failing", t)]
        assert _failing_since(rows) == t

    def test_all_failing_returns_oldest(self):
        t0 = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 9, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            self._row("failing", t2),
            self._row("failing", t1),
            self._row("failing", t0),
        ]
        assert _failing_since(rows) == t0

    def test_healthy_between_failing_streaks(self):
        """A healthy row breaks the streak; failing_since is the second streak's start."""
        t0 = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)
        # Newest first
        rows = [
            self._row("failing", t3),
            self._row("failing", t2),
            self._row("healthy", t1),
            self._row("failing", t0),
        ]
        # The streak starts at t2 (after the healthy at t1)
        assert _failing_since(rows) == t2


# ---------------------------------------------------------------------------
# latest_status
# ---------------------------------------------------------------------------

class TestLatestStatus:
    def test_never_checked_when_no_rows(self, db_session):
        result = latest_status(db_session)
        assert len(result) == len(MONITORED_SOURCES)
        for item in result:
            assert item.status == "never_checked"
            assert item.checked_at is None
            assert item.failing_since is None

    def test_returns_latest_row_per_source(self, db_session):
        t_old = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)

        for t in (t_old, t_new):
            db_session.add(SourceHealthCheck(
                source_type="hellofresh_web",
                checked_at=t,
                status="healthy",
                import_mode="link",
                duration_ms=100,
            ))
        db_session.commit()

        result = latest_status(db_session)
        hf = next(r for r in result if r.source_type == "hellofresh_web")
        assert hf.checked_at == t_new
        assert hf.status == "healthy"
