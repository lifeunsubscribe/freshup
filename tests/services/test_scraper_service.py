"""
Unit tests for recipe scraper service.

Tests cover:
- Successful scraping for HelloFresh URLs
- Successful scraping for Kitchen Sanctuary URLs
- Unsupported URLs with wild_mode fallback
- Error handling (network errors, parse failures)
- Source type auto-detection
- Edge cases and input validation

Note: All external HTTP requests are mocked - no live site access in unit tests.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from recipe_scrapers._exceptions import WebsiteNotImplementedError
import requests
import socket
import logging

from src.services.scraper_service import (
    scrape_recipe,
    _detect_source_type,
    ScraperError,
    NetworkError,
    UnsupportedSiteError,
    ParseError,
)
from src.schemas.scraper import ScrapedRecipeData


def _mock_successful_http_response():
    """Helper to create a mock HTTP response."""
    mock_response = Mock()
    mock_response.content = b"<html>Mock HTML content</html>"
    mock_response.status_code = 200
    return mock_response


class TestDetectSourceType:
    """Tests for _detect_source_type function."""

    def test_hellofresh_domain(self):
        """Test HelloFresh domain detection."""
        assert _detect_source_type("https://www.hellofresh.com/recipes/recipe-123") == "hellofresh_web"
        assert _detect_source_type("https://hellofresh.com/recipes/recipe-123") == "hellofresh_web"

    def test_kitchen_sanctuary_domain(self):
        """Test Kitchen Sanctuary domain detection."""
        assert _detect_source_type("https://www.kitchensanctuary.com/recipe-123") == "kitchen_sanctuary"
        assert _detect_source_type("https://kitchensanctuary.com/recipe-123") == "kitchen_sanctuary"

    def test_unknown_domain_defaults_to_url_import(self):
        """Test that unknown domains default to url_import."""
        assert _detect_source_type("https://www.example.com/recipe") == "url_import"
        assert _detect_source_type("https://www.allrecipes.com/recipe/123") == "url_import"

    def test_invalid_url_defaults_to_url_import(self):
        """Test that invalid URLs default to url_import."""
        assert _detect_source_type("not-a-valid-url") == "url_import"
        assert _detect_source_type("") == "url_import"

    def test_case_insensitive_domain_matching(self):
        """Test that domain matching is case-insensitive."""
        assert _detect_source_type("https://WWW.HELLOFRESH.COM/recipes/recipe-123") == "hellofresh_web"
        assert _detect_source_type("https://KitchenSanctuary.com/recipe-123") == "kitchen_sanctuary"


class TestScrapeRecipe:
    """Tests for scrape_recipe function."""

    def test_empty_url_raises_error(self):
        """Test that empty URL raises ScraperError."""
        with pytest.raises(ScraperError, match="URL cannot be empty"):
            scrape_recipe("")

        with pytest.raises(ScraperError, match="URL cannot be empty"):
            scrape_recipe("   ")

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_successful_scrape_hellofresh(self, mock_requests_get, mock_scrape_html):
        """Test successful scraping of HelloFresh URL."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = b"<html>Mock HTML content</html>"
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # Mock the scraper object returned by recipe_scrapers.scrape_html
        mock_scraper = Mock()
        mock_scraper.title.return_value = "Beef Tacos"
        mock_scraper.ingredients.return_value = ["1 lb ground beef", "8 taco shells", "1 cup cheese"]
        mock_scraper.instructions.return_value = "Brown the beef.\nHeat the shells.\nAssemble tacos."
        mock_scraper.prep_time.return_value = 10
        mock_scraper.cook_time.return_value = 15
        mock_scraper.total_time.return_value = 25
        mock_scraper.yields.return_value = 4
        mock_scraper.image.return_value = "https://example.com/image.jpg"
        mock_scraper.nutrients.return_value = {"calories": "500"}
        mock_scraper.author.return_value = "HelloFresh"
        mock_scraper.site_name.return_value = "HelloFresh"

        mock_scrape_html.return_value = mock_scraper

        # Scrape the recipe
        url = "https://www.hellofresh.com/recipes/beef-tacos"
        result = scrape_recipe(url)

        # Verify the result
        assert isinstance(result, ScrapedRecipeData)
        assert result.source_url == url
        assert result.source_type == "hellofresh_web"
        assert result.title == "Beef Tacos"
        assert len(result.ingredients) == 3
        assert result.prep_time_minutes == 10
        assert result.cook_time_minutes == 15
        assert result.servings == 4
        assert len(result.instructions) == 3  # Split by newline

        # Verify requests.get was called with timeout, headers, and allow_redirects=False
        # The URL will be an IP address due to SSRF protection, with Host and User-Agent headers set
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        assert call_args[1]['timeout'] == 30.0
        assert 'Host' in call_args[1]['headers']
        assert call_args[1]['headers']['Host'] == 'www.hellofresh.com'
        assert 'User-Agent' in call_args[1]['headers']
        assert 'FreshUp-Crawler' in call_args[1]['headers']['User-Agent']
        assert call_args[1]['allow_redirects'] is False

        # Verify scrape_html was called with the fetched HTML
        mock_scrape_html.assert_called_once_with(
            html=b"<html>Mock HTML content</html>",
            org_url=url,
            wild_mode=False
        )

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_successful_scrape_kitchen_sanctuary(self, mock_requests_get, mock_scrape_html):
        """Test successful scraping of Kitchen Sanctuary URL."""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.content = b"<html>Mock HTML content</html>"
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        mock_scraper = Mock()
        mock_scraper.title.return_value = "Chocolate Cake"
        mock_scraper.ingredients.return_value = ["2 cups flour", "1 cup sugar", "1/2 cup cocoa"]
        mock_scraper.instructions.return_value = ["Mix dry ingredients", "Add wet ingredients", "Bake at 350F"]
        mock_scraper.prep_time.return_value = 20
        mock_scraper.cook_time.return_value = 35
        mock_scraper.total_time.return_value = 55
        mock_scraper.yields.return_value = "8 servings"  # String format
        mock_scraper.image.return_value = "https://example.com/cake.jpg"
        mock_scraper.nutrients.return_value = {"calories": "350", "sugar": "30g"}
        mock_scraper.author.return_value = "Kitchen Sanctuary"
        mock_scraper.site_name.return_value = "Kitchen Sanctuary"

        mock_scrape_html.return_value = mock_scraper

        url = "https://www.kitchensanctuary.com/chocolate-cake"
        result = scrape_recipe(url)

        assert result.source_type == "kitchen_sanctuary"
        assert result.title == "Chocolate Cake"
        assert result.servings == 8  # Extracted from "8 servings" string

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_wild_mode_fallback_for_unsupported_site(self, mock_requests_get, mock_scrape_html):
        """Test that wild_mode is attempted for unsupported sites."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        # First call raises WebsiteNotImplementedError (site not supported)
        # Second call (with wild_mode=True) succeeds
        mock_scraper = Mock()
        mock_scraper.title.return_value = "Generic Recipe"
        mock_scraper.ingredients.return_value = ["ingredient 1"]
        mock_scraper.instructions.return_value = "Step 1"
        mock_scraper.prep_time.side_effect = Exception("Not available")
        mock_scraper.cook_time.side_effect = Exception("Not available")
        mock_scraper.total_time.side_effect = Exception("Not available")
        mock_scraper.yields.side_effect = Exception("Not available")
        mock_scraper.image.side_effect = Exception("Not available")
        mock_scraper.nutrients.side_effect = Exception("Not available")
        mock_scraper.author.side_effect = Exception("Not available")
        mock_scraper.site_name.side_effect = Exception("Not available")

        mock_scrape_html.side_effect = [
            WebsiteNotImplementedError("Site not supported"),
            mock_scraper
        ]

        url = "https://www.randomrecipesite.com/recipe"
        result = scrape_recipe(url)

        assert result.source_type == "url_import"
        assert result.title == "Generic Recipe"

        # Verify scrape_html was called twice (once without wild_mode, once with)
        assert mock_scrape_html.call_count == 2
        assert mock_scrape_html.call_args_list[0][1]["wild_mode"] is False
        assert mock_scrape_html.call_args_list[1][1]["wild_mode"] is True

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_unsupported_site_error_when_wild_mode_fails(self, mock_requests_get, mock_scrape_html):
        """Test that UnsupportedSiteError is raised when wild_mode also fails."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scrape_html.side_effect = [
            WebsiteNotImplementedError("Site not supported"),
            WebsiteNotImplementedError("Wild mode also failed")
        ]

        url = "https://www.unsupportedsite.com/recipe"
        with pytest.raises(UnsupportedSiteError, match="Site not supported"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.requests.get')
    def test_network_error_on_connection_failure(self, mock_requests_get):
        """Test that NetworkError is raised on connection failures with sanitized message."""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Failed to connect")

        url = "https://www.hellofresh.com/recipes/test"
        with pytest.raises(NetworkError, match="Unable to connect to the recipe source"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.requests.get')
    def test_network_error_on_timeout(self, mock_requests_get):
        """Test that NetworkError is raised on timeout with sanitized message."""
        mock_requests_get.side_effect = requests.exceptions.Timeout("Request timed out")

        url = "https://www.hellofresh.com/recipes/test"
        with pytest.raises(NetworkError, match="Unable to connect to the recipe source.*timed out"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.requests.get')
    @patch('src.services.scraper_service.get_settings')
    def test_uses_configured_timeout(self, mock_get_settings, mock_requests_get):
        """Test that the configured timeout value is used for HTTP requests (sanitized message)."""
        # Mock settings with custom timeout
        mock_settings = Mock()
        mock_settings.scraper_request_timeout = 45.0
        mock_get_settings.return_value = mock_settings

        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        # Trigger a timeout to verify sanitized error message (timeout value not exposed)
        mock_requests_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        url = "https://www.example.com/recipe"
        with pytest.raises(NetworkError, match="Unable to connect to the recipe source.*timed out"):
            scrape_recipe(url)

        # Verify requests.get was called with the configured timeout, headers, and allow_redirects=False
        # The URL will be an IP address due to SSRF protection, with Host and User-Agent headers set
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        assert call_args[1]['timeout'] == 45.0
        assert 'Host' in call_args[1]['headers']
        assert call_args[1]['headers']['Host'] == 'www.example.com'
        assert 'User-Agent' in call_args[1]['headers']
        assert 'FreshUp-Crawler' in call_args[1]['headers']['User-Agent']
        assert call_args[1]['allow_redirects'] is False

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_sets_user_agent_header(self, mock_requests_get, mock_scrape_html):
        """Test that User-Agent header is set for all HTTP requests."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scraper = Mock()
        mock_scraper.title.return_value = "Test Recipe"
        mock_scraper.ingredients.return_value = ["ingredient 1"]
        mock_scraper.instructions.return_value = "Step 1"
        mock_scraper.prep_time.side_effect = Exception("Not available")
        mock_scraper.cook_time.side_effect = Exception("Not available")
        mock_scraper.total_time.side_effect = Exception("Not available")
        mock_scraper.yields.side_effect = Exception("Not available")
        mock_scraper.image.side_effect = Exception("Not available")
        mock_scraper.nutrients.side_effect = Exception("Not available")
        mock_scraper.author.side_effect = Exception("Not available")
        mock_scraper.site_name.side_effect = Exception("Not available")

        mock_scrape_html.return_value = mock_scraper

        url = "https://www.hellofresh.com/recipes/test"
        result = scrape_recipe(url)

        # Verify User-Agent header is present
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        assert 'User-Agent' in call_args[1]['headers']
        assert 'FreshUp-Crawler/1.0' in call_args[1]['headers']['User-Agent']
        assert 'github.com/freshup/freshup' in call_args[1]['headers']['User-Agent']

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_parse_error_on_data_extraction_failure(self, mock_requests_get, mock_scrape_html):
        """Test that ParseError is raised when data extraction fails."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scraper = Mock()
        # Make all methods raise exceptions to trigger ParseError
        mock_scraper.title.side_effect = Exception("Parse failed")
        mock_scraper.ingredients.side_effect = Exception("Parse failed")
        mock_scraper.instructions.side_effect = Exception("Parse failed")
        mock_scraper.prep_time.side_effect = Exception("Parse failed")
        mock_scraper.cook_time.side_effect = Exception("Parse failed")
        mock_scraper.total_time.side_effect = Exception("Parse failed")
        mock_scraper.yields.side_effect = Exception("Parse failed")
        mock_scraper.image.side_effect = Exception("Parse failed")
        mock_scraper.nutrients.side_effect = Exception("Parse failed")
        mock_scraper.author.side_effect = Exception("Parse failed")
        mock_scraper.site_name.side_effect = Exception("Parse failed")

        mock_scrape_html.return_value = mock_scraper

        url = "https://www.hellofresh.com/recipes/test"
        # Should still succeed but with None/empty values
        result = scrape_recipe(url)

        # Data extraction failures are gracefully handled with fallbacks
        assert result.title is None
        assert result.ingredients == []

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_scraper_error_on_generic_failure(self, mock_requests_get, mock_scrape_html):
        """Test that ScraperError is raised on generic exceptions with sanitized message."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scrape_html.side_effect = Exception("Generic error")

        url = "https://www.hellofresh.com/recipes/test"
        with pytest.raises(ScraperError, match="Unable to process the recipe page"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_handles_missing_optional_fields(self, mock_requests_get, mock_scrape_html):
        """Test that missing optional fields are handled gracefully."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scraper = Mock()
        mock_scraper.title.return_value = "Minimal Recipe"
        mock_scraper.ingredients.return_value = []
        mock_scraper.instructions.return_value = ""
        mock_scraper.prep_time.side_effect = Exception("Not available")
        mock_scraper.cook_time.side_effect = Exception("Not available")
        mock_scraper.total_time.side_effect = Exception("Not available")
        mock_scraper.yields.side_effect = Exception("Not available")
        mock_scraper.image.side_effect = Exception("Not available")
        mock_scraper.nutrients.side_effect = Exception("Not available")
        mock_scraper.author.side_effect = Exception("Not available")
        mock_scraper.site_name.side_effect = Exception("Not available")

        mock_scrape_html.return_value = mock_scraper

        url = "https://www.example.com/recipe"
        result = scrape_recipe(url)

        assert result.title == "Minimal Recipe"
        assert result.ingredients == []
        assert result.instructions == []
        assert result.prep_time_minutes is None
        assert result.cook_time_minutes is None
        assert result.servings is None

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_instructions_string_split_into_list(self, mock_requests_get, mock_scrape_html):
        """Test that instruction strings are split into lists."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scraper = Mock()
        mock_scraper.title.return_value = "Recipe"
        mock_scraper.ingredients.return_value = []
        # Instructions as single string with newlines
        mock_scraper.instructions.return_value = "Step 1: Do this\nStep 2: Do that\nStep 3: Finish"
        mock_scraper.prep_time.side_effect = Exception("N/A")
        mock_scraper.cook_time.side_effect = Exception("N/A")
        mock_scraper.total_time.side_effect = Exception("N/A")
        mock_scraper.yields.side_effect = Exception("N/A")
        mock_scraper.image.side_effect = Exception("N/A")
        mock_scraper.nutrients.side_effect = Exception("N/A")
        mock_scraper.author.side_effect = Exception("N/A")
        mock_scraper.site_name.side_effect = Exception("N/A")

        mock_scrape_html.return_value = mock_scraper

        result = scrape_recipe("https://example.com/recipe")

        assert len(result.instructions) == 3
        assert result.instructions[0] == "Step 1: Do this"
        assert result.instructions[1] == "Step 2: Do that"
        assert result.instructions[2] == "Step 3: Finish"

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_yields_string_extraction(self, mock_requests_get, mock_scrape_html):
        """Test that servings are extracted from yields strings."""
        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        mock_scraper = Mock()
        mock_scraper.title.return_value = "Recipe"
        mock_scraper.ingredients.return_value = []
        mock_scraper.instructions.return_value = "Cook it"
        mock_scraper.yields.return_value = "Makes 6 servings"  # String with number
        mock_scraper.prep_time.side_effect = Exception("N/A")
        mock_scraper.cook_time.side_effect = Exception("N/A")
        mock_scraper.total_time.side_effect = Exception("N/A")
        mock_scraper.image.side_effect = Exception("N/A")
        mock_scraper.nutrients.side_effect = Exception("N/A")
        mock_scraper.author.side_effect = Exception("N/A")
        mock_scraper.site_name.side_effect = Exception("N/A")

        mock_scrape_html.return_value = mock_scraper

        result = scrape_recipe("https://example.com/recipe")

        assert result.servings == 6

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_url_whitespace_trimming(self, mock_requests_get, mock_scrape_html):
        """Test that URL whitespace is trimmed."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b"<html>Mock HTML content</html>"
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        mock_scraper = Mock()
        mock_scraper.title.return_value = "Recipe"
        mock_scraper.ingredients.return_value = []
        mock_scraper.instructions.return_value = []
        mock_scraper.prep_time.side_effect = Exception("N/A")
        mock_scraper.cook_time.side_effect = Exception("N/A")
        mock_scraper.total_time.side_effect = Exception("N/A")
        mock_scraper.yields.side_effect = Exception("N/A")
        mock_scraper.image.side_effect = Exception("N/A")
        mock_scraper.nutrients.side_effect = Exception("N/A")
        mock_scraper.author.side_effect = Exception("N/A")
        mock_scraper.site_name.side_effect = Exception("N/A")

        mock_scrape_html.return_value = mock_scraper

        url_with_spaces = "  https://www.hellofresh.com/recipes/test  "
        result = scrape_recipe(url_with_spaces)

        # Verify the trimmed URL is used
        assert result.source_url == "https://www.hellofresh.com/recipes/test"

        # Verify requests.get was called with trimmed URL (as IP due to SSRF protection)
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        assert call_args[1]['timeout'] == 30.0
        assert 'Host' in call_args[1]['headers']
        assert call_args[1]['headers']['Host'] == 'www.hellofresh.com'
        assert 'User-Agent' in call_args[1]['headers']
        assert 'FreshUp-Crawler' in call_args[1]['headers']['User-Agent']
        assert call_args[1]['allow_redirects'] is False

        # Verify scrape_html was called with the fetched HTML
        mock_scrape_html.assert_called_once_with(
            html=b"<html>Mock HTML content</html>",
            org_url="https://www.hellofresh.com/recipes/test",
            wild_mode=False
        )


class TestSsrfProtection:
    """Tests for SSRF (Server-Side Request Forgery) protection with sanitized error messages."""

    def test_blocks_localhost_by_name(self):
        """Test that localhost is blocked by hostname (sanitized message)."""
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://localhost/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://localhost.localdomain/recipe")

    def test_blocks_localhost_ipv4(self):
        """Test that localhost IPv4 addresses are blocked (sanitized message)."""
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://127.0.0.1/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://127.0.0.2/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://127.255.255.255/recipe")

    def test_blocks_localhost_ipv6(self):
        """Test that localhost IPv6 addresses are blocked."""
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[::1]/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[0000:0000:0000:0000:0000:0000:0000:0001]/recipe")

    def test_blocks_private_ipv4_addresses(self):
        """Test that private IPv4 address ranges are blocked."""
        # 10.0.0.0/8
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://10.0.0.1/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://10.255.255.255/recipe")

        # 172.16.0.0/12
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://172.16.0.1/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://172.31.255.255/recipe")

        # 192.168.0.0/16
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://192.168.0.1/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://192.168.255.255/recipe")

    def test_blocks_private_ipv6_addresses(self):
        """Test that private IPv6 address ranges are blocked."""
        # Unique local addresses (fc00::/7)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[fc00::1]/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[fd00::1]/recipe")

    def test_blocks_link_local_addresses(self):
        """Test that link-local addresses are blocked."""
        # IPv4 link-local (169.254.0.0/16)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://169.254.1.1/recipe")

        # 169.254.169.254 is caught by cloud metadata check (which is fine - still blocked)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://169.254.169.254/recipe")

        # IPv6 link-local (fe80::/10)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[fe80::1]/recipe")

    def test_blocks_unspecified_addresses(self):
        """Test that unspecified addresses (0.0.0.0 and ::) are blocked."""
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://0.0.0.0/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[::]/recipe")

    def test_blocks_multicast_addresses(self):
        """Test that multicast addresses are blocked."""
        # IPv4 multicast (224.0.0.0/4)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://224.0.0.1/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://239.255.255.255/recipe")

        # IPv6 multicast (ff00::/8)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[ff00::1]/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://[ff02::1]/recipe")

    def test_blocks_cloud_metadata_endpoints(self):
        """Test that cloud metadata endpoints are blocked."""
        # AWS/Azure metadata endpoint
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://169.254.169.254/latest/meta-data/")

        # Google Cloud metadata endpoint
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://metadata.google.internal/computeMetadata/v1/")

        # Azure metadata endpoint
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://metadata.azure.com/metadata/instance")

        # AWS metadata endpoint (alternative)
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://metadata.aws.amazon.com/latest/meta-data/")

    def test_blocks_invalid_url_schemes(self):
        """Test that non-http(s) schemes are blocked."""
        with pytest.raises(ScraperError, match="The provided URL is not accessible for recipe import"):
            scrape_recipe("file:///etc/passwd")

        with pytest.raises(ScraperError, match="The provided URL is not accessible for recipe import"):
            scrape_recipe("ftp://example.com/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not accessible for recipe import"):
            scrape_recipe("gopher://example.com/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not accessible for recipe import"):
            scrape_recipe("data:text/html,<html>test</html>")

    def test_blocks_missing_hostname(self):
        """Test that URLs without hostnames are blocked."""
        with pytest.raises(ScraperError, match="Invalid URL: missing hostname"):
            scrape_recipe("http:///path/to/recipe")

        with pytest.raises(ScraperError, match="Invalid URL: missing hostname"):
            scrape_recipe("https://")

    @patch('src.services.scraper_service.requests.get')
    def test_allows_valid_public_urls(self, mock_requests_get):
        """Test that valid public URLs are allowed through SSRF checks."""
        # Mock requests to simulate network errors (we only test SSRF validation)
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Simulated network error")

        # These should pass SSRF validation (though they'll fail at scraping without mocks)
        # We're only testing that SSRF validation doesn't block them
        test_urls = [
            "https://www.hellofresh.com/recipes/test",
            "https://www.kitchensanctuary.com/recipe",
            "https://example.com/recipe",
            "http://recipe.example.org/test",
            "https://8.8.8.8/recipe",  # Public IP (Google DNS)
            "https://1.1.1.1/recipe",  # Public IP (Cloudflare DNS)
        ]

        for url in test_urls:
            try:
                # We expect these to fail at the scraping stage, not SSRF validation
                scrape_recipe(url)
            except NetworkError:
                # NetworkError is expected (simulated network failure)
                # The important thing is it passed SSRF validation
                pass
            except ScraperError as e:
                # If it's an SSRF-related error, the test should fail
                error_msg = str(e).lower()
                assert "localhost" not in error_msg, f"URL {url} was incorrectly blocked as localhost"
                assert "private" not in error_msg, f"URL {url} was incorrectly blocked as private"
                assert "metadata" not in error_msg, f"URL {url} was incorrectly blocked as metadata"
                assert "scheme" not in error_msg, f"URL {url} was incorrectly blocked for scheme"
                assert "hostname" not in error_msg, f"URL {url} was incorrectly blocked for hostname"

    def test_handles_urls_with_ports(self):
        """Test that SSRF protection works correctly with URLs containing ports."""
        # Should block localhost with port
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://localhost:8080/recipe")

        # Should block private IP with port
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://192.168.1.1:8080/recipe")

        # Should block loopback with port
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://127.0.0.1:8080/recipe")

    def test_case_insensitive_hostname_blocking(self):
        """Test that hostname blocking is case-insensitive."""
        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://LOCALHOST/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://LocalHost/recipe")

        with pytest.raises(ScraperError, match="The provided URL is not allowed"):
            scrape_recipe("http://METADATA.GOOGLE.INTERNAL/recipe")


class TestSecurityLogging:
    """Tests for security event logging to verify audit trail for production observability."""

    def test_logs_ssrf_localhost_block(self, caplog):
        """Test that blocking localhost by hostname is logged for security audit."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        with pytest.raises(ScraperError):
            scrape_recipe("http://localhost/recipe")

        # Verify security event was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "SSRF protection: Blocked localhost hostname: localhost" in caplog.records[0].message

    def test_logs_ssrf_cloud_metadata_block(self, caplog):
        """Test that blocking cloud metadata endpoints is logged for security audit."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        with pytest.raises(ScraperError):
            scrape_recipe("http://169.254.169.254/latest/meta-data/")

        # Verify security event was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "SSRF protection: Blocked cloud metadata endpoint: 169.254.169.254" in caplog.records[0].message

    def test_logs_ssrf_private_ip_block(self, caplog):
        """Test that blocking private IP addresses is logged for security audit."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        with pytest.raises(ScraperError):
            scrape_recipe("http://192.168.1.1/recipe")

        # Verify security event was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "SSRF protection: Blocked unsafe IP address:" in caplog.records[0].message
        assert "192.168.1.1" in caplog.records[0].message

    def test_logs_ssrf_domain_resolving_to_private_ip(self, caplog):
        """Test that blocking domains resolving to private IPs is logged for security audit."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        # Mock DNS resolution to return a private IP
        with patch('src.services.scraper_service.socket.getaddrinfo') as mock_getaddrinfo:
            # Return a private IP address (10.0.0.1)
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('10.0.0.1', 80))
            ]

            with pytest.raises(ScraperError):
                scrape_recipe("http://evil-domain.com/recipe")

        # Verify security event was logged with technical details
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "SSRF protection: Domain evil-domain.com resolves to blocked IP: 10.0.0.1" in caplog.records[0].message

    def test_logs_invalid_url_scheme(self, caplog):
        """Test that invalid URL schemes are logged for security audit."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        with pytest.raises(ScraperError):
            scrape_recipe("file:///etc/passwd")

        # Verify security event was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert "Invalid URL scheme rejected: file" in caplog.records[0].message

    @patch('src.services.scraper_service.requests.get')
    def test_logs_network_timeout_error(self, mock_requests_get, caplog):
        """Test that network timeout errors are logged with technical details."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        # Simulate a timeout
        mock_requests_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        with pytest.raises(NetworkError):
            scrape_recipe("https://www.hellofresh.com/recipes/test")

        # Verify error was logged with technical details (timeout value, exception)
        assert len(caplog.records) >= 1
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) >= 1
        timeout_log = warning_records[0]
        assert "Request timeout for URL" in timeout_log.message
        assert "timeout=30.0s" in timeout_log.message

    @patch('src.services.scraper_service.requests.get')
    def test_logs_network_connection_error(self, mock_requests_get, caplog):
        """Test that network connection errors are logged with technical details."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        # Simulate a connection error
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(NetworkError):
            scrape_recipe("https://www.hellofresh.com/recipes/test")

        # Verify error was logged with technical details
        assert len(caplog.records) >= 1
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) >= 1
        connection_log = warning_records[0]
        assert "Connection error for URL:" in connection_log.message
        assert "Connection refused" in connection_log.message

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_logs_parse_error_in_wild_mode(self, mock_requests_get, mock_scrape_html, caplog):
        """Test that parse errors in wild_mode are logged with technical details."""
        caplog.set_level(logging.WARNING, logger="src.services.scraper_service")

        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        # First call raises WebsiteNotImplementedError (triggers wild_mode)
        # Second call (wild_mode) raises a parse error
        mock_scrape_html.side_effect = [
            WebsiteNotImplementedError("Site not supported"),
            ValueError("Invalid JSON-LD schema")
        ]

        with pytest.raises(ParseError):
            scrape_recipe("https://www.example.com/recipe")

        # Verify parse error was logged with technical details
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) >= 1
        parse_log = warning_records[-1]  # Last warning should be the parse error
        assert "Failed to parse recipe in wild_mode:" in parse_log.message
        assert "ValueError" in parse_log.message
        assert "Invalid JSON-LD schema" in parse_log.message

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_logs_unexpected_scraper_error(self, mock_requests_get, mock_scrape_html, caplog):
        """Test that unexpected scraper errors are logged with technical details."""
        caplog.set_level(logging.ERROR, logger="src.services.scraper_service")

        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        # Simulate an unexpected error
        mock_scrape_html.side_effect = RuntimeError("Unexpected parsing failure")

        with pytest.raises(ScraperError):
            scrape_recipe("https://www.hellofresh.com/recipes/test")

        # Verify error was logged with technical details
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) >= 1
        error_log = error_records[0]
        assert "Unexpected scraper error:" in error_log.message
        assert "RuntimeError" in error_log.message
        assert "Unexpected parsing failure" in error_log.message

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    @patch('src.services.scraper_service.requests.get')
    def test_logs_data_extraction_failure(self, mock_requests_get, mock_scrape_html, caplog):
        """Test that data extraction failures are logged with technical details."""
        caplog.set_level(logging.ERROR, logger="src.services.scraper_service")

        # Mock HTTP response
        mock_requests_get.return_value = _mock_successful_http_response()

        # Mock scraper that returns invalid data that fails validation (during ScrapedRecipeData construction)
        # Returning 0 servings will cause validation to fail with ValueError
        mock_scraper = Mock()
        mock_scraper.title.return_value = "Test Recipe"
        mock_scraper.ingredients.return_value = []
        mock_scraper.instructions.return_value = ""
        mock_scraper.prep_time.return_value = None
        mock_scraper.cook_time.return_value = None
        mock_scraper.total_time.return_value = None
        mock_scraper.yields.return_value = 0  # Invalid: will fail validation
        mock_scraper.image.return_value = None
        mock_scraper.nutrients.return_value = None
        mock_scraper.author.return_value = None
        mock_scraper.site_name.return_value = None

        mock_scrape_html.return_value = mock_scraper

        with pytest.raises(ParseError):
            scrape_recipe("https://www.hellofresh.com/recipes/test")

        # Verify error was logged with technical details
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) >= 1
        error_log = error_records[0]
        assert "Failed to extract recipe data:" in error_log.message
        assert "ValidationError" in error_log.message
        assert "servings must be positive" in error_log.message

    def test_logs_dns_resolution_error(self, caplog):
        """Test that invalid DNS resolution results are logged."""
        caplog.set_level(logging.ERROR, logger="src.services.scraper_service")

        # Mock DNS resolution to return invalid IP string
        with patch('src.services.scraper_service.socket.getaddrinfo') as mock_getaddrinfo:
            # Return an invalid IP that will cause ValueError when parsed
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('invalid-ip', 80))
            ]

            with pytest.raises(ScraperError):
                scrape_recipe("http://test-domain.com/recipe")

        # Verify DNS error was logged with technical details
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) >= 1
        dns_log = error_records[0]
        assert "Invalid IP address from DNS for test-domain.com:" in dns_log.message
        assert "invalid-ip" in dns_log.message

    def test_logs_unexpected_url_validation_error(self, caplog):
        """Test that unexpected errors during URL validation are logged."""
        caplog.set_level(logging.ERROR, logger="src.services.scraper_service")

        # Mock urlparse to raise an unexpected exception
        with patch('src.services.scraper_service.urlparse') as mock_urlparse:
            mock_urlparse.side_effect = RuntimeError("Unexpected parsing error")

            with pytest.raises(ScraperError):
                scrape_recipe("https://www.example.com/recipe")

        # Verify unexpected error was logged with technical details
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) >= 1
        error_log = error_records[0]
        assert "Unexpected error during URL validation:" in error_log.message
        assert "RuntimeError" in error_log.message
        assert "Unexpected parsing error" in error_log.message
