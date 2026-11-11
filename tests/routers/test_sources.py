"""
Integration tests for GET /sources/health.

Covers:
- Returns both sources for an authenticated member
- A source with no rows reports 'never_checked'
- failing_since is the first row of the consecutive failing streak
- Unauthenticated request returns 401
"""

import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.db.database import Base, get_db
from src.db import models  # noqa: F401 — registers all tables with Base.metadata
from src.db.models.user import User, UserRole
from src.db.models.source_health import SourceHealthCheck
from src.services.auth_service import hash_password, create_access_token
from src.routers import sources as sources_module

TEST_DATABASE_URL = "sqlite:///:memory:"

app = FastAPI(title="FreshUp", version="0.1.0")
app.include_router(sources_module.router)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")
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


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def member_token(db_session):
    user = User(
        id=uuid4(),
        name="Test Member",
        email="member@example.com",
        hashed_password=hash_password("password"),
        role=UserRole.member.value,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token({"sub": str(user.id)})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _insert_check(db, source_type, checked_at, status="healthy"):
    row = SourceHealthCheck(
        source_type=source_type,
        checked_at=checked_at,
        status=status,
        import_mode="link" if source_type == "hellofresh_web" else "saved_page",
        duration_ms=120,
    )
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# GET /sources/health
# ---------------------------------------------------------------------------

class TestGetSourceHealth:
    def test_returns_both_sources_for_member(self, client, member_token, db_session):
        t = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        _insert_check(db_session, "hellofresh_web", t)
        _insert_check(db_session, "kitchen_sanctuary", t, status="healthy")

        resp = client.get("/sources/health", headers=_auth(member_token))
        assert resp.status_code == 200
        data = resp.json()
        source_types = {item["source_type"] for item in data}
        assert "hellofresh_web" in source_types
        assert "kitchen_sanctuary" in source_types

    def test_never_checked_when_no_rows(self, client, member_token):
        resp = client.get("/sources/health", headers=_auth(member_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert item["status"] == "never_checked"
            assert item["checked_at"] is None

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/sources/health")
        assert resp.status_code == 401

    def test_failing_since_is_first_consecutive_failing(self, client, member_token, db_session):
        t0 = datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)

        _insert_check(db_session, "hellofresh_web", t0, status="healthy")
        _insert_check(db_session, "hellofresh_web", t1, status="failing")
        _insert_check(db_session, "hellofresh_web", t2, status="failing")

        resp = client.get("/sources/health", headers=_auth(member_token))
        assert resp.status_code == 200
        data = resp.json()
        hf = next(item for item in data if item["source_type"] == "hellofresh_web")
        assert hf["status"] == "failing"
        # failing_since should be t1 (first of the consecutive failing streak)
        assert hf["failing_since"] is not None
        failing_since_dt = datetime.fromisoformat(hf["failing_since"].replace("Z", "+00:00"))
        assert failing_since_dt.year == 2026
        assert failing_since_dt.month == 11
        assert failing_since_dt.day == 9

    def test_failing_since_null_when_healthy(self, client, member_token, db_session):
        t = datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc)
        _insert_check(db_session, "hellofresh_web", t, status="healthy")

        resp = client.get("/sources/health", headers=_auth(member_token))
        assert resp.status_code == 200
        data = resp.json()
        hf = next(item for item in data if item["source_type"] == "hellofresh_web")
        assert hf["status"] == "healthy"
        assert hf["failing_since"] is None

    def test_import_mode_in_response(self, client, member_token, db_session):
        t = datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc)
        _insert_check(db_session, "kitchen_sanctuary", t)

        resp = client.get("/sources/health", headers=_auth(member_token))
        assert resp.status_code == 200
        data = resp.json()
        ks = next(item for item in data if item["source_type"] == "kitchen_sanctuary")
        assert ks["import_mode"] == "saved_page"
