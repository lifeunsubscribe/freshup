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

from src.db.models.auth_audit_log import AuthAuditLog, AuthEventType


def _extract_client_ip(request: Request) -> Optional[str]:
    """
    Extract client IP address from request, handling proxy headers.

    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to direct client host.

    SECURITY WARNING: X-Forwarded-For can be spoofed by malicious clients.
    This function should ONLY be used behind a trusted reverse proxy (e.g., nginx,
    Apache, AWS ALB) that is configured to:
    1. Strip/replace X-Forwarded-For from incoming client requests
    2. Set X-Forwarded-For to the actual client IP

    If deployed without a properly configured proxy, clients can forge IP addresses
    in audit logs. For production deployments, ensure your reverse proxy is configured
    to sanitize these headers, or modify this function to only trust request.client.host.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string, or None if unavailable
    """
    # Check for proxy headers (X-Forwarded-For takes precedence)
    # SECURITY: Only safe when behind a trusted proxy that sanitizes this header
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2)
        # The first IP is the original client
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client host
    if request.client:
        return request.client.host

    return None


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
