"""
Unit tests for sanitization utilities.

Tests PII redaction patterns and message sanitization to ensure
sensitive data is properly removed from exception messages.
"""

import pytest

from src.utils.sanitize import (
    sanitize_exception_message,
    sanitize_llm_response_preview,
    PIIPatterns,
)


class TestPIIPatterns:
    """Test PII pattern matching for various sensitive data types."""

    def test_email_pattern_matches_standard_email(self):
        """Email pattern should match standard email addresses."""
        text = "Contact user@example.com for help"
        match = PIIPatterns.EMAIL.search(text)
        assert match is not None
        assert match.group() == "user@example.com"

    def test_email_pattern_matches_complex_email(self):
        """Email pattern should match complex email addresses."""
        text = "Error for john.doe+receipts@company.co.uk"
        match = PIIPatterns.EMAIL.search(text)
        assert match is not None
        assert match.group() == "john.doe+receipts@company.co.uk"

    def test_phone_pattern_matches_us_formats(self):
        """Phone pattern should match various US phone number formats."""
        test_cases = [
            "(123) 456-7890",
            "123-456-7890",
            "123.456.7890",
            "1234567890",
            "+1-123-456-7890",
            "+1 (123) 456-7890",
        ]
        for phone in test_cases:
            text = f"Call us at {phone} for support"
            match = PIIPatterns.PHONE.search(text)
            assert match is not None, f"Failed to match: {phone}"

    def test_credit_card_pattern_matches_formats(self):
        """Credit card pattern should match various card number formats."""
        test_cases = [
            "1234-5678-9012-3456",
            "1234 5678 9012 3456",
            "1234567890123456",
        ]
        for card in test_cases:
            text = f"Card ending in {card}"
            match = PIIPatterns.CREDIT_CARD.search(text)
            assert match is not None, f"Failed to match: {card}"

    def test_ssn_pattern_matches_formats(self):
        """SSN pattern should match SSN format with dashes only.

        Note: Pattern intentionally requires dashes to reduce false positives
        from 9-digit transaction IDs and order numbers common in receipts.
        """
        # Should match: SSN with dashes
        text_with_dashes = "SSN: 123-45-6789"
        match = PIIPatterns.SSN.search(text_with_dashes)
        assert match is not None, "Failed to match SSN with dashes"

        # Should NOT match: SSN without dashes (to avoid false positives)
        text_without_dashes = "Order: 123456789"
        match = PIIPatterns.SSN.search(text_without_dashes)
        assert match is None, "Should not match 9-digit number without dashes"

    def test_address_pattern_matches_street_addresses(self):
        """Address pattern should match common street address formats."""
        test_cases = [
            "123 Main Street",
            "456 Oak Avenue",
            "789 Elm Road",
            "1234 Maple Boulevard",
            "5 Park Lane",
            "67 River Drive",
        ]
        for address in test_cases:
            match = PIIPatterns.ADDRESS.search(address)
            assert match is not None, f"Failed to match: {address}"

    def test_zip_code_pattern_matches_formats(self):
        """ZIP code pattern should match US ZIP code formats."""
        test_cases = [
            "12345",
            "12345-6789",
        ]
        for zip_code in test_cases:
            text = f"Location: {zip_code}"
            match = PIIPatterns.ZIP_CODE.search(text)
            assert match is not None, f"Failed to match: {zip_code}"

    def test_zip_code_pattern_excludes_url_paths(self):
        """ZIP code pattern should NOT match 5-digit numbers in URL paths.

        Per Issue #409: URL path segments should not be redacted as ZIP codes
        to avoid false positives in error messages containing URLs.
        """
        # Should NOT match: 5-digit numbers in URL paths
        test_cases = [
            "http://api.example.com/users/12345",
            "https://example.com/orders/98765/items",
            "GET /products/54321",
            "https://example.com/zip/12345",
            "/api/v1/resource/11111",
        ]
        for url in test_cases:
            match = PIIPatterns.ZIP_CODE.search(url)
            assert match is None, f"Should not match URL path in: {url}"

    def test_zip_code_pattern_excludes_ports(self):
        """ZIP code pattern should NOT match port numbers.

        Existing behavior: port numbers should not be redacted as ZIP codes.
        """
        test_cases = [
            "http://localhost:11434/api/generate",
            "connect to 127.0.0.1:54321",
            "server:12345",
        ]
        for text in test_cases:
            match = PIIPatterns.ZIP_CODE.search(text)
            assert match is None, f"Should not match port in: {text}"

    def test_zip_code_pattern_excludes_query_params(self):
        """ZIP code pattern should NOT match 5-digit numbers in query parameters.

        Per Issue #425 (deferred from PR #424): Query parameter values should not
        be redacted as ZIP codes to avoid false positives in error messages
        containing URLs with numeric parameters.

        This applies to ALL query parameters, even those named 'zip', because:
        1. Query params are more likely to contain IDs than actual ZIP codes
        2. The parameter name already provides context (e.g., '?zip=' reveals intent)
        3. Avoiding false positives in URLs is more important than redacting
           ZIP codes from query strings in error messages
        """
        # Should NOT match: 5-digit numbers in query parameter values
        test_cases = [
            "http://api.example.com/search?user_id=12345",
            "https://example.com/orders?order_id=98765&status=pending",
            "GET /products?page=54321",
            "https://store.com/items?zip=90210",  # Even explicit zip params
            "http://example.com/api?limit=10&offset=12345&sort=desc",
            "?postal_code=94102",
            "url=/search?location_id=12345",
        ]
        for url in test_cases:
            match = PIIPatterns.ZIP_CODE.search(url)
            assert match is None, f"Should not match query param in: {url}"


class TestSanitizeExceptionMessage:
    """Test exception message sanitization."""

    def test_sanitize_none_message(self):
        """None input should return empty string."""
        result = sanitize_exception_message(None)
        assert result == ""

    def test_sanitize_empty_message(self):
        """Empty message should remain empty."""
        result = sanitize_exception_message("")
        assert result == ""

    def test_sanitize_message_without_pii(self):
        """Message without PII should remain unchanged."""
        message = "Database connection failed"
        result = sanitize_exception_message(message)
        assert result == message

    def test_sanitize_email_in_message(self):
        """Email addresses should be redacted."""
        message = "Failed to send notification to user@example.com"
        result = sanitize_exception_message(message)
        assert "user@example.com" not in result
        assert "[EMAIL_REDACTED]" in result
        assert "Failed to send notification to" in result

    def test_sanitize_phone_in_message(self):
        """Phone numbers should be redacted."""
        message = "Contact failed for (555) 123-4567"
        result = sanitize_exception_message(message)
        assert "(555) 123-4567" not in result
        assert "[PHONE_REDACTED]" in result

    def test_sanitize_credit_card_in_message(self):
        """Credit card numbers should be redacted."""
        message = "Payment failed for card 1234-5678-9012-3456"
        result = sanitize_exception_message(message)
        assert "1234-5678-9012-3456" not in result
        assert "[CARD_REDACTED]" in result

    def test_sanitize_ssn_in_message(self):
        """SSNs should be redacted."""
        message = "Identity verification failed for 123-45-6789"
        result = sanitize_exception_message(message)
        assert "123-45-6789" not in result
        assert "[SSN_REDACTED]" in result

    def test_sanitize_address_in_message(self):
        """Street addresses should be redacted."""
        message = "Delivery failed to 123 Main Street"
        result = sanitize_exception_message(message)
        assert "123 Main Street" not in result
        assert "[ADDRESS_REDACTED]" in result

    def test_sanitize_zip_code_in_message(self):
        """ZIP codes should be redacted."""
        message = "Invalid location: 90210"
        result = sanitize_exception_message(message)
        assert "90210" not in result
        assert "[ZIP_REDACTED]" in result

    def test_sanitize_multiple_pii_types(self):
        """Multiple PII types should all be redacted."""
        message = "Failed for user@example.com at 123 Main Street, 90210, phone (555) 123-4567"
        result = sanitize_exception_message(message)
        assert "user@example.com" not in result
        assert "123 Main Street" not in result
        assert "90210" not in result
        assert "(555) 123-4567" not in result
        assert "[EMAIL_REDACTED]" in result
        assert "[ADDRESS_REDACTED]" in result
        assert "[ZIP_REDACTED]" in result
        assert "[PHONE_REDACTED]" in result

    def test_sanitize_truncates_long_messages(self):
        """Long messages should be truncated."""
        long_message = "Error: " + ("x" * 600)
        result = sanitize_exception_message(long_message, max_length=500)
        assert len(result) > 500  # Includes truncation notice
        assert "[TRUNCATED" in result
        assert "107 chars]" in result

    def test_sanitize_preserves_error_context(self):
        """Sanitization should preserve enough context for debugging."""
        message = "ValidationError: field 'email' contains invalid value user@example.com"
        result = sanitize_exception_message(message)
        assert "ValidationError" in result
        assert "field 'email'" in result
        assert "invalid value" in result
        assert "user@example.com" not in result

    def test_sanitize_receipt_validation_error(self):
        """Receipt validation errors should be sanitized."""
        # Simulate a Pydantic validation error with receipt data
        message = (
            "Validation error: 1 validation error for ReceiptParseResult\n"
            "line_items -> 0 -> item_name\n"
            "  Field required [type=missing, input_value={'quantity': 2, 'price': 5.99, "
            "'store': 'Costco', 'address': '123 Main St, 90210'}, input_type=dict]"
        )
        result = sanitize_exception_message(message)
        assert "Validation error" in result
        assert "123 Main St" not in result
        assert "90210" not in result
        assert "[ADDRESS_REDACTED]" in result or "[ZIP_REDACTED]" in result

    def test_sanitize_custom_max_length(self):
        """Custom max_length parameter should be respected."""
        message = "Error: " + ("x" * 200)
        result = sanitize_exception_message(message, max_length=100)
        assert "[TRUNCATED" in result
        # Check that the truncation happened around 100 chars
        assert len(result) < 150  # Some buffer for truncation message


class TestSanitizeLLMResponsePreview:
    """Test LLM response preview sanitization."""

    def test_sanitize_empty_response(self):
        """Empty response should return placeholder."""
        result = sanitize_llm_response_preview("")
        assert result == "[EMPTY_RESPONSE]"

    def test_sanitize_short_response(self):
        """Short response should be truncated and wrapped."""
        response = '{"store": "Costco", "items": []}'
        result = sanitize_llm_response_preview(response, preview_length=50)
        assert "[LLM_RESPONSE_REDACTED:" in result
        assert "chars, starts with:" in result
        assert len(response) > 0

    def test_sanitize_response_with_pii(self):
        """Response with PII should have PII redacted in preview."""
        response = '{"customer": "user@example.com", "phone": "(555) 123-4567"}'
        result = sanitize_llm_response_preview(response, preview_length=100)
        # PII should be redacted in the preview
        assert "user@example.com" not in result
        assert "(555) 123-4567" not in result

    def test_sanitize_response_shows_character_count(self):
        """Preview should show the character count of original response."""
        response = "x" * 500
        result = sanitize_llm_response_preview(response, preview_length=50)
        assert "500 chars" in result

    def test_sanitize_response_respects_preview_length(self):
        """Preview should respect the preview_length parameter."""
        response = '{"data": "' + ("x" * 500) + '"}'
        result = sanitize_llm_response_preview(response, preview_length=30)
        # The preview portion should be limited
        # Full result will be longer due to wrapper text
        assert "[LLM_RESPONSE_REDACTED:" in result


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_receipt_parsing_validation_error_sanitized(self):
        """
        Simulate a receipt parsing validation error with PII.

        This tests the real-world scenario where a receipt contains
        customer name, address, and payment info that gets embedded
        in a Pydantic validation error message.
        """
        # Simulate Pydantic error with receipt data
        error_message = (
            "1 validation error for ReceiptParseResult\n"
            "receipt_date\n"
            "  Input should be a valid date [type=date_type, "
            "input_value='CUSTOMER: John Doe\\n123 Main Street\\nSan Francisco, CA 94102\\n"
            "Card ending in 1234', input_type=str]"
        )

        result = sanitize_exception_message(error_message)

        # Verify PII is redacted (address and ZIP code patterns will catch street/ZIP)
        assert "123 Main Street" not in result
        assert "94102" not in result
        # Person names are not currently redacted as they're too difficult to pattern match
        # The main goal is to redact contact info (email, phone, address, payment data)

        # Verify redaction markers are present
        assert "[ADDRESS_REDACTED]" in result or "[ZIP_REDACTED]" in result

        # Verify context is preserved
        assert "validation error" in result
        assert "ReceiptParseResult" in result

    def test_llm_unavailable_error_with_url_sanitized(self):
        """
        Test that connection errors don't leak sensitive data.

        While URLs typically don't contain PII, error messages
        might include request bodies or headers.
        """
        error_message = (
            "Failed to connect to Ollama: Connection refused [Errno 61] "
            "connecting to http://localhost:11434/api/generate"
        )

        result = sanitize_exception_message(error_message)

        # Should preserve error type and URL
        assert "Failed to connect" in result
        assert "Connection refused" in result
        # URL should be preserved (no PII)
        assert "localhost:11434" in result

    def test_database_error_with_user_data_sanitized(self):
        """
        Test that database errors with user data are sanitized.

        Database errors might include SQL with embedded user data.
        """
        error_message = (
            "IntegrityError: duplicate key value violates unique constraint "
            '"users_email_key"\nDETAIL: Key (email)=(user@example.com) already exists.'
        )

        result = sanitize_exception_message(error_message)

        # Verify email is redacted
        assert "user@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

        # Verify context is preserved
        assert "IntegrityError" in result
        assert "duplicate key" in result

    def test_api_error_with_url_path_not_redacted(self):
        """
        Test that API errors with URLs don't have path segments redacted.

        Per Issue #409: URL path segments should not be redacted as ZIP codes.
        This ensures error messages with URLs remain useful for debugging.
        """
        # Test case 1: REST API error with numeric ID in path
        error_message = (
            "Failed to fetch user: GET http://api.example.com/users/12345 "
            "returned 404 Not Found"
        )
        result = sanitize_exception_message(error_message)

        # URL path should NOT be redacted
        assert "/users/12345" in result
        assert "[ZIP_REDACTED]" not in result
        assert "api.example.com" in result

        # Test case 2: Error with both URL and actual ZIP code
        error_message_mixed = (
            "API error for user at 90210: "
            "GET https://example.com/orders/98765 failed"
        )
        result_mixed = sanitize_exception_message(error_message_mixed)

        # URL path should NOT be redacted
        assert "/orders/98765" in result_mixed
        # But actual ZIP code SHOULD be redacted
        assert "90210" not in result_mixed
        assert "[ZIP_REDACTED]" in result_mixed

    def test_api_error_with_query_params_not_redacted(self):
        """
        Test that API errors with query parameters don't have values redacted.

        Per Issue #425 (deferred from PR #424): Query parameter values should not
        be redacted as ZIP codes to avoid false positives in error messages.
        This is the real-world use case that motivated this issue.
        """
        # Test case 1: API error with user_id query parameter (the reported issue)
        error_message = (
            "Failed to fetch user: GET http://api.example.com/users?user_id=12345 "
            "returned 500 Internal Server Error"
        )
        result = sanitize_exception_message(error_message)

        # Query parameter should NOT be redacted
        assert "?user_id=12345" in result
        assert "[ZIP_REDACTED]" not in result

        # Test case 2: Multiple query parameters with numeric values
        error_message_multi = (
            "Request failed: GET https://api.example.com/orders?"
            "order_id=98765&user_id=12345&page=54321"
        )
        result_multi = sanitize_exception_message(error_message_multi)

        # Query parameters should NOT be redacted
        assert "order_id=98765" in result_multi
        assert "user_id=12345" in result_multi
        assert "page=54321" in result_multi
        assert "[ZIP_REDACTED]" not in result_multi

        # Test case 3: Combined URL with path, query params, AND actual ZIP code
        error_message_combined = (
            "API request failed for location 94102: "
            "GET https://api.example.com/stores/12345?user_id=67890&limit=10"
        )
        result_combined = sanitize_exception_message(error_message_combined)

        # URL path and query params should NOT be redacted
        assert "/stores/12345" in result_combined
        assert "user_id=67890" in result_combined
        # But the standalone ZIP code SHOULD be redacted
        assert "94102" not in result_combined
        assert "[ZIP_REDACTED]" in result_combined
