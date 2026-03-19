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


def _sanitize_metadata(metadata: Optional[dict]) -> Optional[dict]:
    """
    Remove PII (email addresses) from metadata before storing in audit logs.

    This function recursively removes any keys containing 'email' from the metadata
    dictionary to comply with data minimization principles. Email addresses are
    considered PII and should not be stored in audit logs where they could be
    exposed to unauthorized personnel.

    Args:
        metadata: Optional metadata dictionary that may contain PII

    Returns:
        Sanitized metadata dict with email keys removed, or None if input was None

    Examples:
        >>> _sanitize_metadata({"user_id": "123", "email": "user@example.com"})
        {"user_id": "123"}

        >>> _sanitize_metadata({"original_email": "a@b.com", "target_email": "c@d.com"})
        {}

        >>> _sanitize_metadata(None)
        None
    """
    if metadata is None:
        return None

    # Create a new dict with only non-email keys
    sanitized = {}
    for key, value in metadata.items():
        # Skip any key containing 'email' (case-insensitive)
        if 'email' not in key.lower():
            # If value is a dict, recursively sanitize it
            if isinstance(value, dict):
                sanitized[key] = _sanitize_metadata(value)
            # If value is a list, sanitize each item
            elif isinstance(value, list):
                sanitized_list = []
                for item in value:
                    if isinstance(item, dict):
                        sanitized_item = _sanitize_metadata(item)
                        if sanitized_item is not None:
                            sanitized_list.append(sanitized_item)
                    else:
                        sanitized_list.append(item)
                if sanitized_list:
                    sanitized[key] = sanitized_list
            else:
                sanitized[key] = value

    return sanitized if sanitized else None


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
        request: FastAPI request object for extracting IP and user agent
        success: Whether registration succeeded
        failure_reason: Optional reason for failure (e.g., "email_already_exists")
        metadata: Optional additional context (PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
    """
    audit_log = AuthAuditLog(
        user_id=user_id if success else None,
        event_type=AuthEventType.registration.value,
        success=success,
        failure_reason=failure_reason,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(metadata)
    )
    db.add(audit_log)
    return audit_log


def log_login_attempt(
    db: Session,
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
        request: FastAPI request object for extracting IP and user agent
        success: Whether login succeeded
        user_id: ID of the user (only for successful logins)
        failure_reason: Reason for failure (e.g., "invalid_credentials", "user_not_found")
        metadata: Optional additional context (PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
    """
    audit_log = AuthAuditLog(
        user_id=user_id,
        event_type=AuthEventType.login_success.value if success else AuthEventType.login_failure.value,
        success=success,
        failure_reason=failure_reason,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(metadata)
    )
    db.add(audit_log)
    return audit_log


def log_logout(
    db: Session,
    user_id: UUID,
    request: Request,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a user logout event.

    Args:
        db: Database session
        user_id: ID of the user logging out
        request: FastAPI request object for extracting IP and user agent
        metadata: Optional additional context (PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
    """
    audit_log = AuthAuditLog(
        user_id=user_id,
        event_type=AuthEventType.logout.value,
        success=True,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(metadata)
    )
    db.add(audit_log)
    return audit_log


def log_profile_update(
    db: Session,
    user_id: UUID,
    request: Request,
    fields_updated: list[str],
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a user profile update event.

    Args:
        db: Database session
        user_id: ID of the user updating their profile
        request: FastAPI request object for extracting IP and user agent
        fields_updated: List of field names that were updated
        metadata: Optional additional context (PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
    """
    # Include fields_updated in metadata for detailed audit trail
    audit_metadata = {**(metadata or {}), "fields_updated": fields_updated}

    audit_log = AuthAuditLog(
        user_id=user_id,
        event_type=AuthEventType.profile_update.value,
        success=True,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(audit_metadata)
    )
    db.add(audit_log)
    return audit_log


def log_user_switch(
    db: Session,
    original_user_id: UUID,
    target_user_id: UUID,
    request: Request,
    success: bool = True,
    failure_reason: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a user switch/impersonation event.

    Records when a user switches their session to impersonate another user
    (e.g., on shared household devices). This is a security-sensitive operation
    that requires audit logging per OWASP guidelines.

    Args:
        db: Database session
        original_user_id: ID of the user initiating the switch
        target_user_id: ID of the user being switched to
        request: FastAPI request object for extracting IP and user agent
        success: Whether the switch succeeded
        failure_reason: Optional reason for failure (e.g., "different_household", "user_not_found")
        metadata: Optional additional context (PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
        The metadata will have email addresses removed if present.
    """
    # Include switch context in metadata for detailed audit trail
    audit_metadata = {
        **(metadata or {}),
        "original_user_id": str(original_user_id),
        "target_user_id": str(target_user_id)
    }

    audit_log = AuthAuditLog(
        user_id=original_user_id,  # Log against the user initiating the switch
        event_type=AuthEventType.user_switch.value,
        success=success,
        failure_reason=failure_reason,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(audit_metadata)
    )
    db.add(audit_log)
    return audit_log


def log_password_change(
    db: Session,
    user_id: UUID,
    request: Request,
    success: bool = True,
    failure_reason: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log a password change event.

    Password changes are security-sensitive operations that must be audited
    per OWASP guidelines. This helps detect unauthorized password changes
    and provides an audit trail for security investigations.

    Args:
        db: Database session
        user_id: ID of the user changing their password
        request: FastAPI request object for extracting IP and user agent
        success: Whether the password change succeeded
        failure_reason: Optional reason for failure (e.g., "invalid_old_password")
        metadata: Optional additional context (NEVER include passwords; PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
    """
    audit_log = AuthAuditLog(
        user_id=user_id,
        event_type=AuthEventType.password_change.value,
        success=success,
        failure_reason=failure_reason,
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(metadata)
    )
    db.add(audit_log)
    return audit_log


def log_authorization_failure(
    db: Session,
    user_id: UUID,
    request: Request,
    resource: str,
    action: str,
    metadata: Optional[dict] = None
) -> AuthAuditLog:
    """
    Log an authorization failure event.

    Records when a user attempts to access a resource or perform an action
    they are not authorized for. This helps detect privilege escalation
    attempts and unauthorized access patterns.

    Args:
        db: Database session
        user_id: ID of the user attempting the action
        request: FastAPI request object for extracting IP and user agent
        resource: Resource being accessed (e.g., "meal_plan", "user_profile")
        action: Action being attempted (e.g., "update", "delete", "read")
        metadata: Optional additional context (PII will be sanitized)

    Returns:
        Created AuthAuditLog record

    Privacy Note:
        Email addresses are NOT stored. Use user_id to look up user details.
    """
    # Include authorization context in metadata for detailed audit trail
    audit_metadata = {
        **(metadata or {}),
        "resource": resource,
        "action": action
    }

    audit_log = AuthAuditLog(
        user_id=user_id,
        event_type=AuthEventType.authorization_failure.value,
        success=False,  # Authorization failures are always unsuccessful
        failure_reason=f"unauthorized_access: {action} on {resource}",
        ip_address=_extract_client_ip(request),
        user_agent=_extract_user_agent(request),
        event_metadata=_sanitize_metadata(audit_metadata)
    )
    db.add(audit_log)
    return audit_log
