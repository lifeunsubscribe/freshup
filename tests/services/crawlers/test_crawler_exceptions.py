"""
Unit tests for crawler exception hierarchy and wrapping.

Verifies that crawler exceptions properly abstract away requests library
exceptions to prevent leaky abstractions.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests.exceptions

from src.services.crawlers.hellofresh_crawler import HelloFreshCrawler
from src.services.crawlers.kitchen_sanctuary_crawler import KitchenSanctuaryCrawler
from src.services.crawlers.exceptions import (
    CrawlerError,
    CrawlerNetworkError,
    CrawlerParseError,
)


class TestCrawlerExceptionHierarchy:
    """Test the crawler exception hierarchy."""

    def test_exception_hierarchy(self):
        """Test that exceptions have correct inheritance."""
        # CrawlerNetworkError should be a subclass of CrawlerError
        assert issubclass(CrawlerNetworkError, CrawlerError)

        # CrawlerParseError should be a subclass of CrawlerError
        assert issubclass(CrawlerParseError, CrawlerError)

        # Both should be subclasses of Exception
        assert issubclass(CrawlerError, Exception)

    def test_exception_instantiation(self):
        """Test that exceptions can be instantiated with messages."""
        error = CrawlerNetworkError("Network error occurred")
        assert str(error) == "Network error occurred"
        assert isinstance(error, CrawlerError)
        assert isinstance(error, Exception)


class TestHelloFreshCrawlerExceptionWrapping:
    """Test that HelloFreshCrawler wraps exceptions properly."""

    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._discover_from_sitemap')
    def test_network_error_wrapping(self, mock_discover_sitemap, mock_robots_config):
        """Test that requests.exceptions.RequestException is wrapped in CrawlerNetworkError."""
        crawler = HelloFreshCrawler()

        # Mock sitemap strategy to fail with network error (will be caught and fallback attempted)
        mock_discover_sitemap.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # Mock the fallback pagination to also fail with network error
        with patch.object(crawler, '_discover_from_paginated_categories') as mock_paginated:
            mock_paginated.side_effect = requests.exceptions.ConnectionError("Connection failed")

            # Should raise CrawlerNetworkError, not requests.exceptions.ConnectionError
            with pytest.raises(CrawlerNetworkError) as exc_info:
                crawler.discover_recipe_urls()

            # Verify the error message contains context
            assert "Network error during URL discovery" in str(exc_info.value)

            # Verify original exception is chained
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, requests.exceptions.ConnectionError)

    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._discover_from_sitemap')
    def test_timeout_error_wrapping(self, mock_discover_sitemap, mock_robots_config):
        """Test that requests.exceptions.Timeout is wrapped in CrawlerNetworkError."""
        crawler = HelloFreshCrawler()

        # Mock sitemap strategy to fail with timeout (will be caught and fallback attempted)
        mock_discover_sitemap.side_effect = requests.exceptions.Timeout("Request timed out")

        # Mock the fallback pagination to also fail with timeout
        with patch.object(crawler, '_discover_from_paginated_categories') as mock_paginated:
            mock_paginated.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(CrawlerNetworkError) as exc_info:
                crawler.discover_recipe_urls()

            # Verify original exception is chained
            assert isinstance(exc_info.value.__cause__, requests.exceptions.Timeout)

    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._configure_from_robots_txt')
    @patch('defusedxml.ElementTree.fromstring')
    def test_parse_error_wrapping(self, mock_fromstring, mock_robots_config):
        """Test that ValueError from parsing is wrapped in CrawlerParseError."""
        crawler = HelloFreshCrawler()

        # Mock session.get to return valid response for both sitemap and fallback
        with patch.object(crawler.session, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"invalid xml"
            mock_response.text = "invalid html"  # Also mock .text for HTML parsing in fallback
            mock_get.return_value = mock_response

            # Mock XML parsing to raise ValueError for sitemap
            mock_fromstring.side_effect = ValueError("Invalid XML structure")

            # Mock robots.txt check
            crawler.robots_parser.can_fetch = MagicMock(return_value=True)

            # Mock HTML extraction to raise ValueError for fallback
            with patch.object(crawler, '_extract_recipe_urls_from_html') as mock_extract:
                mock_extract.side_effect = ValueError("Invalid HTML structure")

                # Should raise CrawlerParseError, not ValueError
                with pytest.raises(CrawlerParseError) as exc_info:
                    crawler.discover_recipe_urls()

                # Verify the error message contains context
                assert "Parse error during URL discovery" in str(exc_info.value)

                # Verify original exception is chained
                assert exc_info.value.__cause__ is not None
                assert isinstance(exc_info.value.__cause__, ValueError)

    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._discover_from_sitemap')
    def test_unexpected_error_wrapping(self, mock_discover_sitemap, mock_robots_config):
        """Test that unexpected exceptions are wrapped in base CrawlerError."""
        crawler = HelloFreshCrawler()

        # Mock sitemap strategy to fail with unexpected error (will be caught and fallback attempted)
        mock_discover_sitemap.side_effect = RuntimeError("Unexpected runtime error")

        # Mock the fallback pagination to also fail with unexpected error
        with patch.object(crawler, '_discover_from_paginated_categories') as mock_paginated:
            mock_paginated.side_effect = RuntimeError("Unexpected runtime error")

            # Should raise CrawlerError (base class), not RuntimeError
            with pytest.raises(CrawlerError) as exc_info:
                crawler.discover_recipe_urls()

            # Verify it's not a subclass (should be base CrawlerError)
            assert type(exc_info.value) == CrawlerError

            # Verify the error message contains context
            assert "Unexpected error during URL discovery" in str(exc_info.value)

            # Verify original exception is chained
            assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestKitchenSanctuaryCrawlerExceptionWrapping:
    """Test that KitchenSanctuaryCrawler wraps exceptions properly."""

    @patch('src.services.crawlers.kitchen_sanctuary_crawler.KitchenSanctuaryCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.kitchen_sanctuary_crawler.KitchenSanctuaryCrawler._discover_from_sitemap')
    def test_network_error_wrapping(self, mock_discover_sitemap, mock_robots_config):
        """Test that requests.exceptions.RequestException is wrapped in CrawlerNetworkError."""
        crawler = KitchenSanctuaryCrawler()

        # Mock sitemap strategy to raise network error
        mock_discover_sitemap.side_effect = requests.exceptions.HTTPError("404 Not Found")

        # Should raise CrawlerNetworkError, not requests.exceptions.HTTPError
        with pytest.raises(CrawlerNetworkError) as exc_info:
            crawler.discover_recipe_urls()

        # Verify the error message contains context
        assert "Network error during URL discovery" in str(exc_info.value)

        # Verify original exception is chained
        assert isinstance(exc_info.value.__cause__, requests.exceptions.HTTPError)

    @patch('src.services.crawlers.kitchen_sanctuary_crawler.KitchenSanctuaryCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.kitchen_sanctuary_crawler.KitchenSanctuaryCrawler._discover_from_sitemap')
    def test_parse_error_wrapping(self, mock_discover_sitemap, mock_robots_config):
        """Test that ValueError from parsing is wrapped in CrawlerParseError."""
        crawler = KitchenSanctuaryCrawler()

        # Mock sitemap strategy to raise parse error
        mock_discover_sitemap.side_effect = ValueError("Malformed XML")

        # Should raise CrawlerParseError
        with pytest.raises(CrawlerParseError) as exc_info:
            crawler.discover_recipe_urls()

        assert "Parse error during URL discovery" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)

    @patch('src.services.crawlers.kitchen_sanctuary_crawler.KitchenSanctuaryCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.kitchen_sanctuary_crawler.KitchenSanctuaryCrawler._discover_from_sitemap')
    def test_unexpected_error_wrapping(self, mock_discover_sitemap, mock_robots_config):
        """Test that unexpected exceptions are wrapped in base CrawlerError."""
        crawler = KitchenSanctuaryCrawler()

        # Mock sitemap strategy to raise unexpected error
        mock_discover_sitemap.side_effect = RuntimeError("Unexpected runtime error")

        # Should raise CrawlerError (base class), not RuntimeError
        with pytest.raises(CrawlerError) as exc_info:
            crawler.discover_recipe_urls()

        # Verify it's not a subclass (should be base CrawlerError)
        assert type(exc_info.value) == CrawlerError

        # Verify the error message contains context
        assert "Unexpected error during URL discovery" in str(exc_info.value)

        # Verify original exception is chained
        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestNoLeakyAbstractions:
    """Test that requests.exceptions never leak to consumers."""

    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._configure_from_robots_txt')
    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._discover_from_sitemap')
    def test_discover_urls_never_raises_requests_exception(self, mock_discover_sitemap, mock_robots_config):
        """Test that discover_recipe_urls never raises requests.exceptions.*"""
        crawler = HelloFreshCrawler()

        # Try various requests exceptions
        exceptions_to_test = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.HTTPError("HTTP Error"),
            requests.exceptions.RequestException("Generic error"),
        ]

        for exc in exceptions_to_test:
            # Mock sitemap strategy to fail
            mock_discover_sitemap.side_effect = exc

            # Mock fallback to also fail
            with patch.object(crawler, '_discover_from_paginated_categories') as mock_paginated:
                mock_paginated.side_effect = exc

                # Should raise CrawlerNetworkError, not the original requests exception
                with pytest.raises(CrawlerNetworkError):
                    crawler.discover_recipe_urls()

                # Explicitly verify it does NOT raise requests.exceptions
                try:
                    crawler.discover_recipe_urls()
                except requests.exceptions.RequestException:
                    pytest.fail("discover_recipe_urls() leaked a requests.exceptions.RequestException")
                except CrawlerNetworkError:
                    # This is expected
                    pass
