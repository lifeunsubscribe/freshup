"""
Rate limiting middleware for FreshUp API endpoints.

Uses slowapi (FastAPI-compatible rate limiting library) to protect
security-sensitive endpoints from abuse and brute force attacks.

Supports distributed rate limiting via Redis for multi-instance deployments.
Falls back to in-memory storage if Redis is not configured.
"""

import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import Request
from slowapi import Limiter

from src.config import get_settings
from src.services.audit_service import _extract_client_ip

logger = logging.getLogger(__name__)

# Global limiter instance - initialized at module load
# Must be a valid Limiter at import time: auth.py uses @limiter.limit() decorators
limiter: Limiter = None  # type: ignore[assignment] — set by _init_limiter() below


def get_client_ip_for_rate_limit(request: Request) -> str:
    """
    Extract client IP address for rate limiting with proxy trust enforcement.

    This is a wrapper around _extract_client_ip() from audit_service, providing
    a compatible key function for slowapi's Limiter. It implements secure
    X-Forwarded-For header handling:

    - By default, X-Forwarded-For headers are NOT trusted (secure by default)
    - Headers are only used when TRUST_X_FORWARDED_FOR=true AND the request
      comes from a trusted proxy IP (configured via TRUSTED_PROXIES)
    - When trust conditions are not met, falls back to direct connection IP
    - If no IP can be determined (malformed requests), returns "unknown" to
      group such requests together for rate limiting (prevents bypass)

    This prevents rate limiting bypass via proxy header spoofing or missing client info.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string, or "unknown" if unavailable
    """
    ip = _extract_client_ip(request)
    # Never return None - use fallback to prevent rate limiting bypass
    # Grouping unknown IPs together is better than not rate limiting them
    return ip if ip else "unknown"


def _sanitize_redis_url(redis_url: str) -> str:
    """
    Sanitize Redis URL for logging by removing password.

    Args:
        redis_url: Full Redis URL potentially containing password

    Returns:
        str: Sanitized URL safe for logging
    """
    parsed = urlparse(redis_url)
    if parsed.port:
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path}"
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path}"


def _create_limiter() -> Limiter:
    """
    Create and configure the rate limiter instance.

    Attempts to use Redis for distributed rate limiting if redis_url is configured.
    Falls back to in-memory storage if Redis is not configured or connection fails.

    Returns:
        Limiter: Configured slowapi Limiter instance with Redis or in-memory storage
    """
    settings = get_settings()

    # Attempt Redis-backed distributed rate limiting
    if settings.redis_url:
        try:
            import redis

            # Test Redis connection with the configured pool settings
            # Use full pool configuration to validate all settings work correctly
            redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.redis_max_connections,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                socket_timeout=settings.redis_socket_timeout,
                socket_keepalive=settings.redis_socket_keepalive,
                health_check_interval=settings.redis_health_check_interval,
                retry_on_timeout=settings.redis_retry_on_timeout,
            )

            # Test Redis connection
            redis_client.ping()
            # Close test connection - Limiter will create its own connection pool
            redis_client.close()

            # Configure connection pool options for slowapi/limits storage
            # These options are passed through to redis.Redis via limits.storage.RedisStorage
            storage_options = {
                "max_connections": settings.redis_max_connections,
                "socket_connect_timeout": settings.redis_socket_connect_timeout,
                "socket_timeout": settings.redis_socket_timeout,
                "socket_keepalive": settings.redis_socket_keepalive,
                "health_check_interval": settings.redis_health_check_interval,
                "retry_on_timeout": settings.redis_retry_on_timeout,
                "encoding": "utf-8",
                "decode_responses": True,
            }

            logger.info(
                "Rate limiter initialized with Redis backend (distributed mode): %s "
                "(pool: max_connections=%d, socket_timeout=%.1fs, health_check_interval=%ds)",
                _sanitize_redis_url(settings.redis_url),
                settings.redis_max_connections,
                settings.redis_socket_timeout,
                settings.redis_health_check_interval,
            )

            return Limiter(
                key_func=get_client_ip_for_rate_limit,
                storage_uri=settings.redis_url,
                storage_options=storage_options,
            )

        except ImportError:
            logger.warning(
                "Redis library not installed. Rate limiter falling back to in-memory storage. "
                "Install redis package for distributed rate limiting: pip install redis"
            )
        except redis.exceptions.ConnectionError as e:
            logger.warning(
                "Failed to connect to Redis at %s: %s. "
                "Rate limiter falling back to in-memory storage. "
                "This is acceptable for single-instance deployments but will not work correctly "
                "for multi-instance deployments.",
                _sanitize_redis_url(settings.redis_url),
                str(e)
            )
        except redis.exceptions.RedisError as e:
            logger.warning(
                "Redis error during rate limiter initialization: %s. "
                "Rate limiter falling back to in-memory storage.",
                str(e)
            )
        except Exception as e:
            # Broad catch-all for unexpected errors during Redis initialization
            # (e.g., network issues, SSL errors, configuration problems)
            # This is acceptable here as a final fallback to ensure the app starts
            # even if Redis setup fails in an unexpected way
            logger.error(
                "Unexpected error initializing Redis rate limiter: %s. "
                "Rate limiter falling back to in-memory storage.",
                str(e)
            )

    # Fall back to in-memory storage
    logger.info(
        "Rate limiter initialized with in-memory storage (single-instance mode). "
        "For multi-instance deployments, configure REDIS_URL in environment."
    )
    return Limiter(key_func=get_client_ip_for_rate_limit)


def get_limiter() -> Limiter:
    """
    Get the application rate limiter instance.

    Returns:
        Limiter: Configured slowapi Limiter instance
    """
    return limiter


# Initialize at module load — must happen before auth.py imports this module,
# as @limiter.limit() decorators are evaluated at import time.
limiter = _create_limiter()
