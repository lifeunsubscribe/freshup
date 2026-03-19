"""
Unit tests for audit service.

Tests cover:
- log_registration: successful and failed registration logging
- log_login_attempt: successful and failed login logging
- log_profile_update: profile change tracking
- IP address and user agent extraction
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.db import models  # Import all models
from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType
from src.services.audit_service import (
    log_registration,
    log_login_attempt,
    log_profile_update,
    _extract_client_ip,
    _extract_user_agent
)


# Create an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "test")


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    _ = models  # Force import of all models

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
def mock_request():
    """Create a mock FastAPI Request object."""
    request = Mock()
    request.client = Mock()
    request.client.host = "192.168.1.100"
    request.headers = {
        "User-Agent": "Mozilla/5.0 (Test Browser)"
    }
    return request


class TestIPExtraction:
    """Tests for IP address extraction from request."""

    def test_extract_ip_from_client(self):
        """Extract IP from request.client when no proxy headers."""
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {}

        ip = _extract_client_ip(request)
        assert ip == "192.168.1.100"

    def test_extract_ip_from_forwarded_for(self):
        """Extract IP from X-Forwarded-For header (proxy)."""
        request = Mock()
        request.client = Mock()
        request.client.host = "10.0.0.1"  # Proxy IP
        request.headers = {
            "X-Forwarded-For": "203.0.113.42, 10.0.0.1"
        }

        ip = _extract_client_ip(request)
        assert ip == "203.0.113.42"  # First IP is original client

    def test_extract_ip_no_client(self):
        """Handle request with no client."""
        request = Mock()
        request.client = None
        request.headers = {}

        ip = _extract_client_ip(request)
        assert ip is None


class TestUserAgentExtraction:
    """Tests for User-Agent extraction from request."""

    def test_extract_user_agent(self):
        """Extract User-Agent from headers."""
        request = Mock()
        request.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }

        user_agent = _extract_user_agent(request)
        assert user_agent == "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

    def test_extract_user_agent_missing(self):
        """Handle missing User-Agent header."""
        request = Mock()
        request.headers = {}

        user_agent = _extract_user_agent(request)
        assert user_agent is None


class TestLogRegistration:
    """Tests for log_registration function."""

    def test_log_successful_registration(self, db_session, mock_request):
        """Log successful user registration."""
        user_id = uuid4()
        email = "newuser@example.com"

        log_entry = log_registration(
            db=db_session,
            user_id=user_id,
            email=email,
            request=mock_request,
            success=True,
            metadata={"role": "coordinator"}
        )

        assert log_entry.user_id == user_id
        assert log_entry.email == email
        assert log_entry.event_type == AuthEventType.registration.value
        assert log_entry.success is True
        assert log_entry.failure_reason is None
        assert log_entry.ip_address == "192.168.1.100"
        assert log_entry.user_agent == "Mozilla/5.0 (Test Browser)"
        assert log_entry.event_metadata == {"role": "coordinator"}

        # Verify it was persisted (need to commit since audit service no longer commits)
        db_session.commit()
        db_log = db_session.query(AuthAuditLog).filter_by(id=log_entry.id).first()
        assert db_log is not None
        assert db_log.email == email

    def test_log_failed_registration(self, db_session, mock_request):
        """Log failed registration attempt."""
        email = "duplicate@example.com"

        log_entry = log_registration(
            db=db_session,
            user_id=None,
            email=email,
            request=mock_request,
            success=False,
            failure_reason="email_already_exists"
        )

        assert log_entry.user_id is None
        assert log_entry.email == email
        assert log_entry.event_type == AuthEventType.registration.value
        assert log_entry.success is False
        assert log_entry.failure_reason == "email_already_exists"


class TestLogLoginAttempt:
    """Tests for log_login_attempt function."""

    def test_log_successful_login(self, db_session, mock_request):
        """Log successful login."""
        user_id = uuid4()
        email = "user@example.com"

        log_entry = log_login_attempt(
            db=db_session,
            email=email,
            request=mock_request,
            success=True,
            user_id=user_id
        )

        assert log_entry.user_id == user_id
        assert log_entry.email == email
        assert log_entry.event_type == AuthEventType.login_success.value
        assert log_entry.success is True
        assert log_entry.failure_reason is None

    def test_log_failed_login_invalid_password(self, db_session, mock_request):
        """Log failed login with invalid password."""
        user_id = uuid4()
        email = "user@example.com"

        log_entry = log_login_attempt(
            db=db_session,
            email=email,
            request=mock_request,
            success=False,
            user_id=user_id,
            failure_reason="invalid_credentials"
        )

        assert log_entry.user_id == user_id
        assert log_entry.email == email
        assert log_entry.event_type == AuthEventType.login_failure.value
        assert log_entry.success is False
        assert log_entry.failure_reason == "invalid_credentials"

    def test_log_failed_login_user_not_found(self, db_session, mock_request):
        """Log failed login when user doesn't exist."""
        email = "nonexistent@example.com"

        log_entry = log_login_attempt(
            db=db_session,
            email=email,
            request=mock_request,
            success=False,
            user_id=None,
            failure_reason="invalid_credentials"
        )

        assert log_entry.user_id is None
        assert log_entry.email == email
        assert log_entry.event_type == AuthEventType.login_failure.value
        assert log_entry.success is False


class TestLogProfileUpdate:
    """Tests for log_profile_update function."""

    def test_log_profile_update(self, db_session, mock_request):
        """Log user profile update."""
        user_id = uuid4()
        email = "user@example.com"
        fields_updated = ["name", "dietary_profile", "allergies"]

        log_entry = log_profile_update(
            db=db_session,
            user_id=user_id,
            email=email,
            request=mock_request,
            fields_updated=fields_updated
        )

        assert log_entry.user_id == user_id
        assert log_entry.email == email
        assert log_entry.event_type == AuthEventType.profile_update.value
        assert log_entry.success is True
        assert log_entry.event_metadata["fields_updated"] == fields_updated
