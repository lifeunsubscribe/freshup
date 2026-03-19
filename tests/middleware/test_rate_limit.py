"""
Tests for rate limiting middleware with X-Forwarded-For support.

These tests verify that the rate limiter correctly handles proxy headers
to prevent rate limit bypass via header spoofing while supporting legitimate
proxy deployments.
"""

import pytest
from unittest.mock import Mock
from fastapi import Request

from src.middleware.rate_limit import get_client_ip_for_rate_limit, limiter


class TestGetClientIpForRateLimit:
    """
    Tests for get_client_ip_for_rate_limit() function.

    This function is the key function that slowapi uses to determine the client IP
    for rate limiting. It must correctly handle X-Forwarded-For headers based on
    the trust configuration to prevent bypass attacks.
    """

    def test_returns_direct_ip_when_no_forwarded_for_header(self, monkeypatch):
        """
        Test that direct connection IP is returned when no X-Forwarded-For header present.

        This is the most common case - direct client connections without a proxy.
        """
        # Mock settings: trust enabled (shouldn't matter since no header)
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = True
        mock_settings.trusted_proxies = "10.0.0.1"
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request without X-Forwarded-For header
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "203.0.113.45"
        request.headers = {}

        ip = get_client_ip_for_rate_limit(request)
        assert ip == "203.0.113.45"

    def test_ignores_forwarded_for_when_trust_disabled(self, monkeypatch):
        """
        Test that X-Forwarded-For is IGNORED when TRUST_X_FORWARDED_FOR=false.

        This is the secure default behavior - protects against header spoofing.
        Attackers cannot bypass rate limiting by adding X-Forwarded-For headers.
        """
        # Mock settings: trust DISABLED
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = False
        mock_settings.trusted_proxies = "10.0.0.1"
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request with X-Forwarded-For header
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "203.0.113.45"
        request.headers = {"X-Forwarded-For": "192.0.2.100"}

        ip = get_client_ip_for_rate_limit(request)
        # Should return direct IP, NOT the forwarded IP
        assert ip == "203.0.113.45"

    def test_ignores_forwarded_for_from_untrusted_proxy(self, monkeypatch):
        """
        Test that X-Forwarded-For is IGNORED when request comes from untrusted proxy.

        Even when TRUST_X_FORWARDED_FOR=true, only requests from explicitly
        trusted proxy IPs should have their headers honored. This prevents
        attackers from spoofing the header.
        """
        # Mock settings: trust enabled but only for 10.0.0.1
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = True
        mock_settings.trusted_proxies = "10.0.0.1"
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request from UNTRUSTED proxy (10.0.0.99 not in trusted list)
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.99"  # Untrusted proxy
        request.headers = {"X-Forwarded-For": "192.0.2.100"}

        ip = get_client_ip_for_rate_limit(request)
        # Should return proxy IP, NOT the forwarded IP
        assert ip == "10.0.0.99"

    def test_uses_forwarded_for_from_trusted_proxy(self, monkeypatch):
        """
        Test that X-Forwarded-For IS USED when trust enabled and proxy is trusted.

        This is the legitimate proxy use case - when behind a trusted reverse
        proxy (nginx, AWS ALB, etc.), we want the real client IP for rate limiting.
        """
        # Mock settings: trust enabled and proxy is trusted
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = True
        mock_settings.trusted_proxies = "10.0.0.1"
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request from TRUSTED proxy
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers = {"X-Forwarded-For": "192.0.2.100"}

        ip = get_client_ip_for_rate_limit(request)
        # Should return the forwarded IP (real client)
        assert ip == "192.0.2.100"

    def test_uses_forwarded_for_with_cidr_trusted_proxy(self, monkeypatch):
        """
        Test X-Forwarded-For with CIDR range in trusted proxy list.

        Supports configuring trusted proxies as network ranges (e.g., AWS VPC
        subnet) rather than individual IPs.
        """
        # Mock settings: trust enabled with CIDR range
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = True
        mock_settings.trusted_proxies = "10.0.0.0/24"
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request from proxy in trusted CIDR range
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.50"  # In 10.0.0.0/24 range
        request.headers = {"X-Forwarded-For": "192.0.2.100"}

        ip = get_client_ip_for_rate_limit(request)
        assert ip == "192.0.2.100"

    def test_uses_first_ip_from_multi_proxy_chain(self, monkeypatch):
        """
        Test that first IP is used when X-Forwarded-For contains multiple IPs.

        When requests pass through multiple proxies, X-Forwarded-For becomes
        a comma-separated list: "client, proxy1, proxy2". The first IP is the
        original client, which is what we want for rate limiting.
        """
        # Mock settings: trust enabled and proxy is trusted
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = True
        mock_settings.trusted_proxies = "10.0.0.1"
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request with multi-proxy X-Forwarded-For
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers = {"X-Forwarded-For": "192.0.2.100, 198.51.100.5, 203.0.113.10"}

        ip = get_client_ip_for_rate_limit(request)
        # Should return the first (original client) IP
        assert ip == "192.0.2.100"

    def test_returns_unknown_when_no_client_info(self, monkeypatch):
        """
        Test that "unknown" is returned when request has no client information.

        This prevents rate limiting bypass - requests with missing client info
        are grouped together as "unknown" and rate limited collectively rather
        than being allowed through without rate limiting.
        """
        # Mock settings
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = False
        mock_settings.trusted_proxies = ""
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request without client info
        request = Mock(spec=Request)
        request.client = None
        request.headers = {}

        ip = get_client_ip_for_rate_limit(request)
        assert ip == "unknown"

    def test_handles_empty_trusted_proxies_list(self, monkeypatch):
        """
        Test that empty TRUSTED_PROXIES means trust NO proxies (fail-secure).

        Even with TRUST_X_FORWARDED_FOR=true, an empty trusted proxy list
        should result in X-Forwarded-For being ignored. This is the fail-secure
        default configuration.
        """
        # Mock settings: trust enabled but NO trusted proxies
        mock_settings = Mock()
        mock_settings.trust_x_forwarded_for = True
        mock_settings.trusted_proxies = ""  # Empty list
        monkeypatch.setattr("src.services.audit_service.get_settings", lambda: mock_settings)

        # Create request with X-Forwarded-For
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.1"
        request.headers = {"X-Forwarded-For": "192.0.2.100"}

        ip = get_client_ip_for_rate_limit(request)
        # Should return direct IP (empty trusted list means trust NO proxies)
        assert ip == "10.0.0.1"


class TestLimiterConfiguration:
    """
    Tests for limiter configuration.

    Verifies that the limiter is properly configured to use the custom
    key function for IP extraction.
    """

    def test_limiter_uses_custom_key_function(self):
        """
        Test that limiter is configured with get_client_ip_for_rate_limit.

        This ensures that the rate limiter will respect the X-Forwarded-For
        configuration for all rate-limited endpoints.
        """
        assert limiter._key_func == get_client_ip_for_rate_limit
