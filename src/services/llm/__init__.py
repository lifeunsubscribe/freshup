"""
LLM service module for FreshUp.

Provides model-agnostic LLM client abstraction with structured output validation
and automatic retry logic for malformed responses.

Usage:
    from src.services.llm import OllamaClient, LLMUnavailableError, LLMResponseError

    # Create client
    client = OllamaClient()

    # Generate structured completion
    try:
        result = await client.complete(
            prompt="Parse this receipt: ...",
            system_prompt="You are a receipt parser...",
            response_schema=ReceiptData,
        )
    except LLMUnavailableError:
        # Handle service unavailable
        pass
    except LLMResponseError:
        # Handle validation failure
        pass
    finally:
        await client.close()
"""

from src.services.llm.client import LLMClient, OllamaClient
from src.services.llm.exceptions import (
    LLMError,
    LLMUnavailableError,
    LLMResponseError,
)

__all__ = [
    "LLMClient",
    "OllamaClient",
    "LLMError",
    "LLMUnavailableError",
    "LLMResponseError",
]
