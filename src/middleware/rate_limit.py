"""
Rate limiting middleware for FreshUp API endpoints.

Uses slowapi (FastAPI-compatible rate limiting library) to protect
security-sensitive endpoints from abuse and brute force attacks.
"""

from typing import Optional
from fastapi import Request
from slowapi import Limiter

from src.services.audit_service import _extract_client_ip


def get_client_ip_for_rate_limit(request: Request) -> Optional[str]:
    """
    Extract client IP address for rate limiting with proxy trust enforcement.

    This is a wrapper around _extract_client_ip() from audit_service, providing
    a compatible key function for slowapi's Limiter. It implements secure
    X-Forwarded-For header handling:

    - By default, X-Forwarded-For headers are NOT trusted (secure by default)
    - Headers are only used when TRUST_X_FORWARDED_FOR=true AND the request
      comes from a trusted proxy IP (configured via TRUSTED_PROXIES)
    - When trust conditions are not met, falls back to direct connection IP

    This prevents rate limiting bypass via proxy header spoofing.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string, or None if unavailable
    """
    return _extract_client_ip(request)


# Rate limiter instance configured with proxy-aware IP-based key function
# Uses in-memory storage suitable for single-instance deployment
limiter = Limiter(key_func=get_client_ip_for_rate_limit)


def get_limiter() -> Limiter:
    """
    Get the application rate limiter instance.

    Returns:
        Limiter: Configured slowapi Limiter instance
    """
    return limiter
