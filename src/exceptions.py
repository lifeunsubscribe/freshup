"""
Domain exception hierarchy for service layer operations.

Provides abstraction over HTTP-specific exceptions to maintain separation
of concerns between the service layer and HTTP transport layer (FastAPI).
This prevents the service layer from being coupled to HTTP/web framework
details, making the code more testable and portable.

Pattern:
    - Service layer raises domain exceptions (ValidationError, NotFoundError, etc.)
    - Router layer catches domain exceptions and converts them to HTTPException
    - Each exception includes an http_status_code for router conversion convenience

Example:
    Service layer:
        if not item:
            raise NotFoundError("Item not found")

    Router layer:
        try:
            result = service_function()
        except DomainException as e:
            raise HTTPException(status_code=e.http_status_code, detail=str(e))
"""

from typing import Optional


class DomainException(Exception):
    """
    Base exception for all service layer domain errors.

    Use this as the catch-all when handling service operations,
    or catch specific subclasses for finer-grained error handling.

    Attributes:
        http_status_code: HTTP status code to use when converting to HTTPException
        message: Human-readable error description
    """

    http_status_code: int = 500  # Default to internal server error

    def __init__(self, message: str):
        """
        Initialize DomainException with error message.

        Args:
            message: Human-readable error description
        """
        self.message = message
        super().__init__(message)


class ValidationError(DomainException):
    """
    Raised when input validation fails.

    Indicates that the request contains invalid data that fails business
    rule validation or data integrity constraints.

    HTTP Status: 422 Unprocessable Entity
    """

    http_status_code = 422


class NotFoundError(DomainException):
    """
    Raised when a requested resource doesn't exist.

    Indicates that the requested entity (user, item, task, etc.) was not
    found in the database or is not accessible to the requesting user.

    HTTP Status: 404 Not Found
    """

    http_status_code = 404


class ConflictError(DomainException):
    """
    Raised when an operation conflicts with existing state.

    Indicates that the request cannot be completed due to a conflict with
    the current state of the resource (e.g., duplicate entry, concurrent
    modification).

    HTTP Status: 409 Conflict
    """

    http_status_code = 409


class UnauthorizedError(DomainException):
    """
    Raised when access to a resource is denied.

    Indicates that the user is authenticated but does not have permission
    to access the requested resource (authorization failure).

    HTTP Status: 401 Unauthorized

    Note: This is semantically 403 Forbidden, but we use 401 to match
    existing API conventions in this codebase.
    """

    http_status_code = 401
