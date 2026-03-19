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
    _extract_user_agent,
    _is_trusted_proxy
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


class TestTrustedProxyValidation:
    """Tests for trusted proxy IP validation."""

    def test_trusted_proxy_single_ip_match(self):
        """Match against single trusted IP."""
        assert _is_trusted_proxy("10.0.0.1", "10.0.0.1") is True

    def test_trusted_proxy_single_ip_no_match(self):
        """No match against single trusted IP."""
        assert _is_trusted_proxy("10.0.0.2", "10.0.0.1") is False

    def test_trusted_proxy_multiple_ips(self):
        """Match against multiple trusted IPs."""
        trusted = "10.0.0.1, 192.168.1.1, 172.16.0.1"
        assert _is_trusted_proxy("192.168.1.1", trusted) is True
        assert _is_trusted_proxy("10.0.0.99", trusted) is False

    def test_trusted_proxy_cidr_range(self):
        """Match against CIDR range."""
        assert _is_trusted_proxy("10.0.0.50", "10.0.0.0/24") is True
        assert _is_trusted_proxy("10.0.1.50", "10.0.0.0/24") is False

    def test_trusted_proxy_multiple_cidr_ranges(self):
        """Match against multiple CIDR ranges."""
        trusted = "10.0.0.0/24, 192.168.1.0/24"
        assert _is_trusted_proxy("10.0.0.100", trusted) is True
        assert _is_trusted_proxy("192.168.1.50", trusted) is True
        assert _is_trusted_proxy("172.16.0.1", trusted) is False

    def test_trusted_proxy_mixed_ip_and_cidr(self):
        """Match against mixed IPs and CIDR ranges."""
        trusted = "10.0.0.1, 192.168.1.0/24, 172.16.0.5"
        assert _is_trusted_proxy("10.0.0.1", trusted) is True
        assert _is_trusted_proxy("192.168.1.100", trusted) is True
        assert _is_trusted_proxy("172.16.0.5", trusted) is True
        assert _is_trusted_proxy("172.16.0.6", trusted) is False

    def test_trusted_proxy_empty_list_trusts_all(self):
        """Empty trusted list means trust all proxies."""
        assert _is_trusted_proxy("1.2.3.4", "") is True
        assert _is_trusted_proxy("10.0.0.1", "  ") is True

    def test_trusted_proxy_invalid_ip(self):
        """Invalid IP address returns False."""
        assert _is_trusted_proxy("not-an-ip", "10.0.0.0/24") is False

    def test_trusted_proxy_invalid_config(self):
        """Invalid entries in config are skipped."""
        trusted = "10.0.0.1, invalid-ip, 192.168.1.0/24"
        assert _is_trusted_proxy("10.0.0.1", trusted) is True
        assert _is_trusted_proxy("192.168.1.50", trusted) is True


class TestIPExtraction:
    """Tests for IP address extraction from request."""

    def test_extract_ip_from_client_no_trust(self, monkeypatch):
        """Extract IP from request.client when trust is disabled (default)."""
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "false")
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

        # Clear the settings cache
        from src.config import get_settings
        get_settings.cache_clear()

        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {}

        ip = _extract_client_ip(request)
        assert ip == "192.168.1.100"

    def test_extract_ip_ignores_forwarded_for_when_trust_disabled(self, monkeypatch):
        """Ignore X-Forwarded-For when trust is disabled (secure by default)."""
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "false")

        from src.config import get_settings
        get_settings.cache_clear()

        request = Mock()
        request.client = Mock()
        request.client.host = "10.0.0.1"  # Proxy IP
        request.headers = {
            "X-Forwarded-For": "203.0.113.42, 10.0.0.1"
        }

        ip = _extract_client_ip(request)
        # Should return proxy IP, not forwarded IP
        assert ip == "10.0.0.1"

    def test_extract_ip_from_forwarded_for_with_trust_enabled(self, monkeypatch):
        """Extract IP from X-Forwarded-For when trust is enabled and proxy is trusted."""
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")

        from src.config import get_settings
        get_settings.cache_clear()

        request = Mock()
        request.client = Mock()
        request.client.host = "10.0.0.1"  # Trusted proxy IP
        request.headers = {
            "X-Forwarded-For": "203.0.113.42, 10.0.0.1"
        }

        ip = _extract_client_ip(request)
        assert ip == "203.0.113.42"  # First IP is original client

    def test_extract_ip_ignores_forwarded_for_from_untrusted_proxy(self, monkeypatch):
        """Ignore X-Forwarded-For from untrusted proxy even when trust is enabled."""
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")  # Only trust this IP

        from src.config import get_settings
        get_settings.cache_clear()

        request = Mock()
        request.client = Mock()
        request.client.host = "10.0.0.99"  # Untrusted proxy IP
        request.headers = {
            "X-Forwarded-For": "203.0.113.42, 10.0.0.99"
        }

        ip = _extract_client_ip(request)
        # Should return direct connection IP, not forwarded IP
        assert ip == "10.0.0.99"

    def test_extract_ip_from_forwarded_for_with_cidr_trust(self, monkeypatch):
        """Extract IP from X-Forwarded-For when proxy is in trusted CIDR range."""
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/24")

        from src.config import get_settings
        get_settings.cache_clear()

        request = Mock()
        request.client = Mock()
        request.client.host = "10.0.0.50"  # In trusted CIDR range
        request.headers = {
            "X-Forwarded-For": "203.0.113.42"
        }

        ip = _extract_client_ip(request)
        assert ip == "203.0.113.42"

    def test_extract_ip_with_trust_enabled_empty_proxy_list(self, monkeypatch):
        """Trust all proxies when trust enabled with empty proxy list."""
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
        monkeypatch.setenv("TRUSTED_PROXIES", "")

        from src.config import get_settings
        get_settings.cache_clear()

        request = Mock()
        request.client = Mock()
        request.client.host = "1.2.3.4"  # Any proxy IP
        request.headers = {
            "X-Forwarded-For": "203.0.113.42"
        }

        ip = _extract_client_ip(request)
        assert ip == "203.0.113.42"

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
