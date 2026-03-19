"""
Audit logging service for FreshUp authentication events.

Provides centralized functions for logging authentication and authorization events
to the audit log table. All authentication-related routes should use these functions
to ensure consistent audit trail.

Transaction Semantics:
    These functions add audit log entries to the database session but DO NOT commit.
    The calling code is responsible for committing the transaction.

    - For successful operations: Add audit log before db.commit() so both commit
      atomically together. This ensures the operation and its audit log are consistent.

    - For failed operations: Add audit log, commit it independently, then raise the
      exception. This is intentionally NOT atomic - the audit log commits separately
      to ensure failures are always logged, even if the main operation is rolled back.

    This design prevents orphaned audit entries for successful operations (where the
    main operation might fail after an independent audit commit), while guaranteeing
    that security-relevant failures are always captured in the audit trail.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import Request
import ipaddress
import logging

from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType
from src.config import get_settings

logger = logging.getLogger(__name__)


def _is_trusted_proxy(ip: str, trusted_proxies: str) -> bool:
    """
    Check if an IP address is in the trusted proxy list.

    Args:
        ip: IP address to check
        trusted_proxies: Comma-separated list of IPs/CIDR ranges

    Returns:
        True if IP is trusted, False otherwise
    """
    if not trusted_proxies.strip():
        # Empty/whitespace-only list means trust NO proxies (fail-secure default)
        # This prevents X-Forwarded-For header spoofing when misconfigured
        return False

    try:
        ip_addr = ipaddress.ip_address(ip)
    except ValueError:
        return False

    for trusted in trusted_proxies.split(","):
        trusted = trusted.strip()
        if not trusted:
            continue

        try:
            # Try as network (CIDR notation)
            if "/" in trusted:
                network = ipaddress.ip_network(trusted, strict=False)
                if ip_addr in network:
                    return True
            else:
                # Try as individual IP
                if ip_addr == ipaddress.ip_address(trusted):
                    return True
        except ValueError:
            # Invalid IP/network in config, log and skip it
            logger.warning(
                "Invalid proxy configuration entry '%s' in TRUSTED_PROXIES - skipping",
                trusted
            )
            continue

    return False


def _extract_client_ip(request: Request) -> Optional[str]:
    """
    Extract client IP address from request with proxy trust enforcement.

    This function implements secure X-Forwarded-For header handling. By default,
    X-Forwarded-For headers are NOT trusted (secure by default). They are only
    used when:
    1. TRUST_X_FORWARDED_FOR=true in configuration, AND
    2. The request comes from a trusted proxy IP (configured via TRUSTED_PROXIES)

    When trust conditions are not met, falls back to the direct connection IP
    (request.client.host), which cannot be spoofed.

    Configuration:
        TRUST_X_FORWARDED_FOR: Enable X-Forwarded-For trust (default: false)
        TRUSTED_PROXIES: Comma-separated IPs/CIDR ranges (e.g., "10.0.0.1,192.168.1.0/24")

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string, or None if unavailable
    """
    settings = get_settings()

    # Get the direct connection IP (always available, cannot be spoofed)
    direct_ip = request.client.host if request.client else None

    # Only check X-Forwarded-For if trust is explicitly enabled
    if settings.trust_x_forwarded_for:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for and direct_ip:
            # Verify the request comes from a trusted proxy
            if _is_trusted_proxy(direct_ip, settings.trusted_proxies):
                # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2)
                # The first IP is the original client
                return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP (secure default)
    return direct_ip


def _extract_user_agent(request: Request) -> Optional[str]:
    """
    Extract User-Agent string from request headers.

    Args:
        request: FastAPI request object

    Returns:
        User-Agent string, or None if unavailable
    """
    return request.headers.get("User-Agent")


def log_registration(
    db: Session,
    user_id: Optional[UUID],
    email: str,
    request: Request,
    success: bool = True,
    failure_reason: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a user registration event.

    Args:
        db: Database session
        user_id: ID of the newly created user (None if registration failed)
        email: Email address used for registration
        request: FastAPI request object for extracting IP and user agent
        success: Whether registration succeeded
        failure_reason: Optional reason for failure (e.g., "email_already_exists")
        metadata: Optional additional context

    Returns:
        Created AuthAuditLog record
    """
    audit_log = AuthAuditLog(
        user_id=user_id if success else None,
        email=email,
        event_type=AuthEventType.registration.value,
        success=success,
        failure_reason=failure_reason,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=metadata
    )
    db.add(audit_log)
    return audit_log


def log_login_attempt(
    db: Session,
    email: str,
    request: Request,
    success: bool,
    user_id: Optional[UUID] = None,
    failure_reason: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a login attempt (successful or failed).

    Args:
        db: Database session
        email: Email address used for login attempt
        request: FastAPI request object for extracting IP and user agent
        success: Whether login succeeded
        user_id: ID of the user (only for successful logins)
        failure_reason: Reason for failure (e.g., "invalid_credentials", "user_not_found")
        metadata: Optional additional context

    Returns:
        Created AuthAuditLog record
    """
    audit_log = AuthAuditLog(
        user_id=user_id,
        email=email,
        event_type=AuthEventType.login_success.value if success else AuthEventType.login_failure.value,
        success=success,
        failure_reason=failure_reason,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=metadata
    )
    db.add(audit_log)
    return audit_log


def log_logout(
    db: Session,
    user_id: UUID,
    email: str,
    request: Request,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a user logout event.

    Args:
        db: Database session
        user_id: ID of the user logging out
        email: Email of the user logging out
        request: FastAPI request object for extracting IP and user agent
        metadata: Optional additional context

    Returns:
        Created AuthAuditLog record
    """
    audit_log = AuthAuditLog(
        user_id=user_id,
        email=email,
        event_type=AuthEventType.logout.value,
        success=True,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=metadata
    )
    db.add(audit_log)
    return audit_log


def log_profile_update(
    db: Session,
    user_id: UUID,
    email: str,
    request: Request,
    fields_updated: list[str],
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a user profile update event.

    Args:
        db: Database session
        user_id: ID of the user updating their profile
        email: Email of the user
        request: FastAPI request object for extracting IP and user agent
        fields_updated: List of field names that were updated
        metadata: Optional additional context

    Returns:
        Created AuthAuditLog record
    """
    # Include fields_updated in metadata for detailed audit trail
    audit_metadata = {**(metadata or {}), "fields_updated": fields_updated}

    audit_log = AuthAuditLog(
        user_id=user_id,
        email=email,
        event_type=AuthEventType.profile_update.value,
        success=True,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=audit_metadata
    )
    db.add(audit_log)
    return audit_log
