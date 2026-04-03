"""
Unit tests for LLM client abstraction layer.

Tests cover:
- Successful completion with valid response
- Malformed JSON response
- Validation error with successful retry
- Validation error exhausting retries
- Connection timeout
- Connection refused
- Health check success and failure

All tests mock httpx.AsyncClient entirely - no real HTTP calls are made.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from pydantic import BaseModel, Field

from src.services.llm import OllamaClient, LLMUnavailableError, LLMResponseError


# Test schema for validation
class TestReceipt(BaseModel):
    """Sample Pydantic schema for testing structured output."""
    store_name: str = Field(..., description="Name of the store")
    total: float = Field(..., description="Total purchase amount")
    items: list[str] = Field(default_factory=list, description="List of items purchased")


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")

    get_settings.cache_clear()


@pytest.fixture
def mock_httpx_client():
    """
    Create a mock httpx.AsyncClient for testing.

    Returns a mock that can be configured per-test to simulate different
    Ollama API responses and error conditions.
    """
    mock = AsyncMock(spec=httpx.AsyncClient)
    mock.aclose = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_complete_success(mock_httpx_client):
    """Test successful completion with valid JSON response."""
    # Mock successful Ollama response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": json.dumps({
            "store_name": "Costco",
            "total": 142.37,
            "items": ["bananas", "milk", "eggs"]
        })
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    # Patch httpx.AsyncClient to return our mock
    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        result = await client.complete(
            prompt="Parse this receipt",
            system_prompt="You are a receipt parser",
            response_schema=TestReceipt,
        )

        # Verify result
        assert isinstance(result, TestReceipt)
        assert result.store_name == "Costco"
        assert result.total == 142.37
        assert result.items == ["bananas", "milk", "eggs"]

        # Verify API was called correctly
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "/api/generate"
        assert call_args[1]["json"]["model"] == "llama3.1:8b"
        assert call_args[1]["json"]["prompt"] == "Parse this receipt"
        assert call_args[1]["json"]["system"] == "You are a receipt parser"
        assert call_args[1]["json"]["stream"] is False
        assert call_args[1]["json"]["format"] == "json"


@pytest.mark.asyncio
async def test_complete_malformed_json(mock_httpx_client):
    """Test handling of malformed JSON response that exhausts retries."""
    # Mock Ollama returning invalid JSON on all attempts
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "This is not valid JSON at all"
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMResponseError) as exc_info:
            await client.complete(
                prompt="Parse this receipt",
                system_prompt="You are a receipt parser",
                response_schema=TestReceipt,
            )

        # Verify error details
        error = exc_info.value
        assert "3 attempts" in str(error)  # MAX_RETRIES=2 means 3 total attempts
        assert error.response == "This is not valid JSON at all"
        assert len(error.validation_errors) == 3  # One error per attempt

        # Verify retry behavior - should have been called 3 times (initial + 2 retries)
        assert mock_httpx_client.post.call_count == 3


@pytest.mark.asyncio
async def test_complete_validation_error_with_retry_success(mock_httpx_client):
    """Test validation error on first attempt, success on retry."""
    # First call returns invalid schema
    invalid_response = MagicMock()
    invalid_response.status_code = 200
    invalid_response.json.return_value = {
        "response": json.dumps({
            "store_name": "Costco",
            # Missing required 'total' field
            "items": ["bananas"]
        })
    }

    # Second call returns valid schema
    valid_response = MagicMock()
    valid_response.status_code = 200
    valid_response.json.return_value = {
        "response": json.dumps({
            "store_name": "Costco",
            "total": 5.99,
            "items": ["bananas"]
        })
    }

    # Configure mock to return different responses on successive calls
    mock_httpx_client.post = AsyncMock(side_effect=[invalid_response, valid_response])

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        result = await client.complete(
            prompt="Parse this receipt",
            system_prompt="You are a receipt parser",
            response_schema=TestReceipt,
        )

        # Verify success on retry
        assert isinstance(result, TestReceipt)
        assert result.store_name == "Costco"
        assert result.total == 5.99

        # Verify retry happened - called twice
        assert mock_httpx_client.post.call_count == 2

        # Verify second call included correction context
        second_call_args = mock_httpx_client.post.call_args_list[1]
        second_prompt = second_call_args[1]["json"]["prompt"]
        assert "Parse this receipt" in second_prompt
        assert "Previous response failed validation" in second_prompt


@pytest.mark.asyncio
async def test_complete_validation_exhausts_retries(mock_httpx_client):
    """Test validation error on all retry attempts."""
    # All calls return schema with missing required field
    invalid_response = MagicMock()
    invalid_response.status_code = 200
    invalid_response.json.return_value = {
        "response": json.dumps({
            "store_name": "Costco",
            # Missing required 'total' field - will always fail validation
        })
    }
    mock_httpx_client.post = AsyncMock(return_value=invalid_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMResponseError) as exc_info:
            await client.complete(
                prompt="Parse this receipt",
                system_prompt="You are a receipt parser",
                response_schema=TestReceipt,
            )

        # Verify error details
        error = exc_info.value
        assert "3 attempts" in str(error)
        assert len(error.validation_errors) == 3

        # All validation errors should mention missing field
        for validation_error in error.validation_errors:
            assert "total" in validation_error.lower() or "required" in validation_error.lower()


@pytest.mark.asyncio
async def test_complete_connection_timeout(mock_httpx_client):
    """Test handling of connection timeout."""
    # Simulate timeout on connection
    mock_httpx_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connect timeout"))

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMUnavailableError) as exc_info:
            await client.complete(
                prompt="Parse this receipt",
                system_prompt="You are a receipt parser",
                response_schema=TestReceipt,
            )

        # Verify error message mentions timeout
        assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_complete_connection_refused(mock_httpx_client):
    """Test handling of connection refused (Ollama not running)."""
    # Simulate connection refused
    mock_httpx_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMUnavailableError) as exc_info:
            await client.complete(
                prompt="Parse this receipt",
                system_prompt="You are a receipt parser",
                response_schema=TestReceipt,
            )

        # Verify error message mentions connection failure
        assert "connect" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_complete_http_error_status(mock_httpx_client):
    """Test handling of HTTP error status codes (4xx, 5xx)."""
    # Simulate 500 Internal Server Error
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error",
        request=MagicMock(),
        response=mock_response,
    )
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMUnavailableError) as exc_info:
            await client.complete(
                prompt="Parse this receipt",
                system_prompt="You are a receipt parser",
                response_schema=TestReceipt,
            )

        # Verify error message mentions status code
        assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_is_available_success(mock_httpx_client):
    """Test health check returns True when Ollama is available."""
    # Mock successful health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        result = await client.is_available()

        assert result is True
        mock_httpx_client.get.assert_called_once_with("/api/tags")


@pytest.mark.asyncio
async def test_is_available_connection_refused(mock_httpx_client):
    """Test health check returns False when Ollama is unreachable."""
    # Simulate connection refused
    mock_httpx_client.get = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        result = await client.is_available()

        # Should return False, not raise exception
        assert result is False


@pytest.mark.asyncio
async def test_is_available_timeout(mock_httpx_client):
    """Test health check returns False on timeout."""
    # Simulate timeout
    mock_httpx_client.get = AsyncMock(
        side_effect=httpx.TimeoutException("Timeout")
    )

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        result = await client.is_available()

        # Should return False, not raise exception
        assert result is False


@pytest.mark.asyncio
async def test_is_available_http_error(mock_httpx_client):
    """Test health check returns False on HTTP error status."""
    # Simulate 503 Service Unavailable
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=MagicMock(),
        response=mock_response,
    )
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        result = await client.is_available()

        # Should return False, not raise exception
        assert result is False


@pytest.mark.asyncio
async def test_client_timeout_configuration(mock_httpx_client):
    """Test that httpx client is configured with correct timeouts."""
    with patch("src.services.llm.client.httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value = mock_httpx_client

        client = OllamaClient()

        # Verify AsyncClient was instantiated with correct timeout config
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]

        assert "timeout" in call_kwargs
        timeout = call_kwargs["timeout"]
        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 5.0
        assert timeout.read == 120.0


@pytest.mark.asyncio
async def test_async_context_manager(mock_httpx_client):
    """Test that OllamaClient supports async context manager protocol."""
    mock_httpx_client.aclose = AsyncMock()

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        async with OllamaClient() as client:
            assert client is not None

        # Verify client was closed on exit
        mock_httpx_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_close_method(mock_httpx_client):
    """Test explicit close method."""
    mock_httpx_client.aclose = AsyncMock()

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()
        await client.close()

        # Verify underlying httpx client was closed
        mock_httpx_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_validation_error_sanitizes_pii(mock_httpx_client):
    """
    Test that validation errors containing PII are sanitized.

    Per Issue #377: LLM responses may contain receipt data with PII
    (emails, phone numbers, addresses) that should be redacted from
    exception messages to prevent data leaks through error reporting systems.
    """
    # Simulate LLM response with PII in validation error
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        # Missing required field, validation error will include this input
        "response": json.dumps({
            "store_name": "Costco - 123 Main Street, San Francisco, CA 94102",
            "items": ["Contact: user@example.com, (555) 123-4567"]
            # Missing required "total" field - will cause validation error
        })
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMResponseError) as exc_info:
            await client.complete(
                prompt="Parse receipt",
                system_prompt="Parse receipts",
                response_schema=TestReceipt,
            )

        error = exc_info.value

        # Verify PII is redacted from error message
        error_str = str(error)
        assert "user@example.com" not in error_str
        assert "(555) 123-4567" not in error_str
        assert "123 Main Street" not in error_str
        assert "94102" not in error_str

        # Verify redaction labels are present in either the main message or validation errors
        all_error_text = error_str + " ".join(error.validation_errors)
        assert "[EMAIL_REDACTED]" in all_error_text or "[PHONE_REDACTED]" in all_error_text or "[ADDRESS_REDACTED]" in all_error_text or "[ZIP_REDACTED]" in all_error_text

        # Verify response field is also sanitized
        assert error.response is not None
        assert "user@example.com" not in error.response
        assert "(555) 123-4567" not in error.response
        # Response should have redaction markers
        assert "[EMAIL_REDACTED]" in error.response or "[PHONE_REDACTED]" in error.response or "[ADDRESS_REDACTED]" in error.response or "[ZIP_REDACTED]" in error.response


@pytest.mark.asyncio
async def test_validation_error_list_sanitizes_pii(mock_httpx_client):
    """
    Test that individual validation errors in the list are sanitized.

    Each validation error message may contain input_value with PII.
    """
    # Create response that will fail validation with PII in the data
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": json.dumps({
            "store_name": "Store at john.doe@example.com",
            "total": "invalid",  # Wrong type - will cause validation error
            "items": []
        })
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)

    with patch("src.services.llm.client.httpx.AsyncClient", return_value=mock_httpx_client):
        client = OllamaClient()

        with pytest.raises(LLMResponseError) as exc_info:
            await client.complete(
                prompt="Parse receipt",
                system_prompt="Parse receipts",
                response_schema=TestReceipt,
            )

        error = exc_info.value

        # Verify each validation error is sanitized
        for validation_error in error.validation_errors:
            assert "john.doe@example.com" not in validation_error
            # Should have redaction markers or be truncated
            assert "[" in validation_error  # Contains some redaction marker
