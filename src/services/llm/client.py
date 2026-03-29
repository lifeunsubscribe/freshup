"""
LLM client abstraction layer for FreshUp.

Provides a model-agnostic interface for LLM operations with structured output
validation and automatic retry logic for malformed responses.

Per ADR-003: LLMs handle natural language interpretation tasks (receipt parsing,
recipe photo parsing, voice commands). All state management and business logic
remains deterministic Python code.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Type

import httpx
from pydantic import BaseModel, ValidationError

from src.config import get_settings
from src.services.llm.exceptions import LLMUnavailableError, LLMResponseError

logger = logging.getLogger(__name__)

# Generic type for Pydantic response schemas
T = TypeVar('T', bound=BaseModel)


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.

    Defines the interface all LLM providers must implement, enabling
    provider swapping without code changes (e.g., Ollama → OpenAI).
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> T:
        """
        Generate a structured completion from the LLM.

        Args:
            prompt: The user prompt/query
            system_prompt: System-level instructions for the LLM
            response_schema: Pydantic model class defining expected response structure

        Returns:
            Validated instance of response_schema populated with LLM output

        Raises:
            LLMUnavailableError: If the LLM service is unreachable
            LLMResponseError: If response validation fails after all retries
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the LLM service is available and responding.

        Returns:
            True if service is healthy, False otherwise

        Note:
            Does not raise exceptions - returns False for any error condition
        """
        pass


class OllamaClient(LLMClient):
    """
    Ollama HTTP client implementation.

    Communicates with a local Ollama server via HTTP API for inference.
    Configured via settings: ollama_base_url, ollama_model.

    Timeout configuration:
    - Connect timeout: 5s (fail fast if Ollama is down)
    - Read timeout: 120s (allow time for model inference)

    Retry behavior:
    - On validation failure, retries up to 2 times (3 total attempts)
    - Appends validation error to prompt as correction context
    - Raises LLMResponseError after exhausting retries
    """

    # Maximum number of retries on validation failure
    MAX_RETRIES = 2

    def __init__(self):
        """Initialize OllamaClient with configuration from settings."""
        settings = get_settings()
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model

        # Configure httpx client with specified timeouts
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=5.0,  # Connect timeout: 5 seconds
                read=120.0,   # Read timeout: 120 seconds
            ),
        )

    async def complete(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> T:
        """
        Generate a structured completion from Ollama.

        Implements retry logic with correction context:
        1. Send prompt to Ollama with JSON format request
        2. Parse response as JSON and validate against schema
        3. On validation failure: append error to prompt and retry (up to MAX_RETRIES)
        4. Raise LLMResponseError if all retries exhausted

        Args:
            prompt: The user prompt/query
            system_prompt: System-level instructions for the LLM
            response_schema: Pydantic model class defining expected response structure

        Returns:
            Validated instance of response_schema populated with LLM output

        Raises:
            LLMUnavailableError: If Ollama is unreachable (connection refused, timeout)
            LLMResponseError: If response validation fails after all retries
        """
        # Track validation errors across retries for debugging
        validation_errors: list[str] = []
        current_prompt = prompt

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Request JSON-formatted response from Ollama
                response = await self.client.post(
                    "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": current_prompt,
                        "system": system_prompt,
                        "stream": False,
                        "format": "json",  # Instruct Ollama to return valid JSON
                    },
                )

                # Check HTTP status
                response.raise_for_status()

                # Extract response text from Ollama's response format
                ollama_response = response.json()
                response_text = ollama_response.get("response", "")

                # Parse and validate against schema
                try:
                    # Parse JSON response
                    response_data = json.loads(response_text)

                    # Validate against Pydantic schema
                    validated = response_schema.model_validate(response_data)

                    # Success! Return validated response
                    logger.info(
                        "LLM completion successful",
                        extra={
                            "model": self.model,
                            "attempt": attempt + 1,
                            "schema": response_schema.__name__,
                        },
                    )
                    return validated

                except (json.JSONDecodeError, ValidationError) as e:
                    # Response validation failed
                    error_msg = f"Validation error: {str(e)}"
                    validation_errors.append(error_msg)

                    logger.warning(
                        "LLM response validation failed",
                        extra={
                            "model": self.model,
                            "attempt": attempt + 1,
                            "error": error_msg,
                            "response_preview": response_text[:200],
                        },
                    )

                    # If we have retries left, append correction context and retry
                    if attempt < self.MAX_RETRIES:
                        # Build correction prompt with validation error
                        correction_context = (
                            f"\n\nPrevious response failed validation: {error_msg}\n"
                            f"Please provide a valid JSON response matching the required schema."
                        )
                        current_prompt = prompt + correction_context
                        continue  # Retry with corrected prompt

                    # No retries left - raise error
                    raise LLMResponseError(
                        f"Response validation failed after {self.MAX_RETRIES + 1} attempts",
                        response=response_text,
                        validation_errors=validation_errors,
                    )

            except httpx.ConnectError as e:
                # Connection refused - Ollama likely not running
                raise LLMUnavailableError(
                    f"Failed to connect to Ollama at {self.base_url}: {str(e)}"
                ) from e

            except httpx.TimeoutException as e:
                # Request timeout
                raise LLMUnavailableError(
                    f"Request to Ollama timed out: {str(e)}"
                ) from e

            except httpx.HTTPStatusError as e:
                # HTTP error response (4xx, 5xx)
                raise LLMUnavailableError(
                    f"Ollama returned error status {e.response.status_code}: {str(e)}"
                ) from e

        # Should never reach here due to raise inside loop, but for type safety
        raise LLMResponseError(
            f"Unexpected error: exhausted retries without resolution",
            validation_errors=validation_errors,
        )

    async def is_available(self) -> bool:
        """
        Check if Ollama is available and responding.

        Attempts to fetch the list of available models from /api/tags endpoint.
        This is a lightweight health check that verifies both connectivity and
        that Ollama is properly initialized.

        Returns:
            True if Ollama is healthy and responding, False otherwise

        Note:
            Never raises exceptions - returns False for any error condition
        """
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.debug(
                "Ollama availability check failed",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
            )
            return False

    async def close(self):
        """Close the underlying HTTP client. Should be called on shutdown."""
        await self.client.aclose()

    async def __aenter__(self):
        """Support async context manager protocol."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure client is closed when exiting async context."""
        await self.close()
