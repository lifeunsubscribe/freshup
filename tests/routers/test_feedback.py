"""
Integration tests for the feedback endpoints.

- POST /feedback stores a note from any signed-in user
- GET /feedback lists them, newest first, for coordinators only
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base, get_db
from src.db import models  # noqa: F401  (registers every table)
from src.db.models.feedback import Feedback
from src.db.models.user import User, UserRole
from src.routers import feedback as feedback_module
from src.services.auth_service import hash_password, create_access_token

TEST_DATABASE_URL = "sqlite:///:memory:"

app = FastAPI(title="FreshUp", version="0.1.0")
app.include_router(feedback_module.router)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
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


def _user(db_session, name, role):
    user = User(
        id=uuid4(),
        name=name,
        email=f"{name.lower()}@example.com",
        hashed_password=hash_password("password"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def member(db_session):
    return _user(db_session, "Alex", UserRole.member.value)


@pytest.fixture
def coordinator(db_session):
    return _user(db_session, "Sarah", UserRole.coordinator.value)


class TestSendFeedback:
    def test_stores_the_note_with_who_sent_it_and_from_where(self, client, db_session, member):
        response = client.post(
            "/feedback",
            json={"message": "  The swap button is hard to find.  ", "page": "/plan/2026-11-15"},
            headers=_auth(member),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["message"] == "The swap button is hard to find."
        assert body["page"] == "/plan/2026-11-15"
        assert body["user_name"] == "Alex"
        stored = db_session.query(Feedback).one()
        assert stored.user_id == member.id
        assert stored.message == "The swap button is hard to find."

    def test_the_page_is_optional(self, client, member):
        response = client.post("/feedback", json={"message": "Nice."}, headers=_auth(member))

        assert response.status_code == 201
        assert response.json()["page"] is None

    @pytest.mark.parametrize("message", ["", "   ", "x" * 4001])
    def test_rejects_an_empty_or_oversized_note(self, client, db_session, member, message):
        response = client.post("/feedback", json={"message": message}, headers=_auth(member))

        assert response.status_code == 422
        assert db_session.query(Feedback).count() == 0

    def test_requires_sign_in(self, client):
        response = client.post("/feedback", json={"message": "Hello"})

        assert response.status_code in (401, 403)


class TestListFeedback:
    def test_coordinator_sees_every_note_newest_first(self, client, db_session, member, coordinator):
        now = datetime(2026, 11, 21, 12, 0, 0)
        db_session.add_all([
            Feedback(user_id=member.id, message="older", created_at=now - timedelta(hours=2)),
            Feedback(user_id=coordinator.id, message="newest", page="/", created_at=now),
            Feedback(user_id=member.id, message="middle", created_at=now - timedelta(hours=1)),
        ])
        db_session.commit()

        response = client.get("/feedback", headers=_auth(coordinator))

        assert response.status_code == 200
        notes = response.json()
        assert [n["message"] for n in notes] == ["newest", "middle", "older"]
        assert [n["user_name"] for n in notes] == ["Sarah", "Alex", "Alex"]

    def test_a_member_cannot_read_feedback(self, client, member):
        response = client.get("/feedback", headers=_auth(member))

        assert response.status_code == 403

    def test_requires_sign_in(self, client):
        assert client.get("/feedback").status_code in (401, 403)
