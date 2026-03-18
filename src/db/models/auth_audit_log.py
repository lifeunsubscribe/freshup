from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, JSON, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class AuthEventType(str, PyEnum):
    """Types of authentication events that can be audited."""
    registration = "registration"
    login_success = "login_success"
    login_failure = "login_failure"
    logout = "logout"
    token_refresh = "token_refresh"
    profile_update = "profile_update"
    password_change = "password_change"


class AuthAuditLog(Base):
    """
    Audit log for authentication and authorization events.

    Tracks all authentication-related activities for security monitoring,
    compliance, and debugging. Follows OWASP logging best practices:
    - Logs both successful and failed authentication attempts
    - Includes contextual information (IP, user agent) for threat detection
    - Never stores sensitive data (passwords, tokens)
    - Immutable records (no updates, only inserts)

    Use cases:
    - Detect brute force attacks (multiple failed logins from same IP)
    - Track unauthorized access attempts
    - Audit trail for compliance requirements
    - Debug authentication issues
    """
    __tablename__ = "auth_audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # User context (nullable for failed login attempts where user doesn't exist)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Request context for security analysis
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Additional metadata (flexible JSON field for future extensibility)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationship to user (for successful events)
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
