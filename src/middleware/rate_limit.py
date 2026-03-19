"""
Rate limiting middleware for FreshUp API endpoints.

Uses slowapi (FastAPI-compatible rate limiting library) to protect
security-sensitive endpoints from abuse and brute force attacks.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


# Rate limiter instance configured with IP-based key function
# Uses in-memory storage suitable for single-instance deployment
limiter = Limiter(key_func=get_remote_address)


def get_limiter() -> Limiter:
    """
    Get the application rate limiter instance.

    Returns:
        Limiter: Configured slowapi Limiter instance
    """
    return limiter
