"""
Custom exceptions for LLM client operations.

Provides specific error types for different failure modes to enable
targeted error handling and recovery strategies.
"""


class LLMError(Exception):
    """Base exception for all LLM-related errors."""
    pass


class LLMUnavailableError(LLMError):
    """
    Raised when the LLM service is unreachable.

    Covers scenarios like:
    - Connection refused (service not running)
    - Connection timeout
    - Network errors

    Indicates the issue is with availability, not response quality.
    """
    pass


class LLMResponseError(LLMError):
    """
    Raised when the LLM response fails validation after all retries.

    Indicates the LLM is available but unable to produce valid output
    conforming to the expected schema.

    Contains the original response and validation errors for debugging.
    """

    def __init__(self, message: str, response: str | None = None, validation_errors: list[str] | None = None):
        """
        Initialize LLMResponseError with context.

        Args:
            message: Human-readable error description
            response: The malformed response from the LLM (if available)
            validation_errors: List of validation error messages from retries
        """
        super().__init__(message)
        self.response = response
        self.validation_errors = validation_errors or []
