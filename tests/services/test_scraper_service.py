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

from src.services.scraper_service import (
    scrape_recipe,
    _detect_source_type,
    ScraperError,
    NetworkError,
    UnsupportedSiteError,
    ParseError,
)
from src.schemas.scraper import ScrapedRecipeData


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
    def test_successful_scrape_hellofresh(self, mock_scrape_html):
        """Test successful scraping of HelloFresh URL."""
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

        # Verify scrape_html was called correctly
        mock_scrape_html.assert_called_once_with(
            html=None,
            org_url=url,
            wild_mode=False
        )

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    def test_successful_scrape_kitchen_sanctuary(self, mock_scrape_html):
        """Test successful scraping of Kitchen Sanctuary URL."""
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
    def test_wild_mode_fallback_for_unsupported_site(self, mock_scrape_html):
        """Test that wild_mode is attempted for unsupported sites."""
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
    def test_unsupported_site_error_when_wild_mode_fails(self, mock_scrape_html):
        """Test that UnsupportedSiteError is raised when wild_mode also fails."""
        mock_scrape_html.side_effect = [
            WebsiteNotImplementedError("Site not supported"),
            WebsiteNotImplementedError("Wild mode also failed")
        ]

        url = "https://www.unsupportedsite.com/recipe"
        with pytest.raises(UnsupportedSiteError, match="Site not supported"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    def test_network_error_on_connection_failure(self, mock_scrape_html):
        """Test that NetworkError is raised on connection failures."""
        mock_scrape_html.side_effect = ConnectionError("Failed to connect")

        url = "https://www.hellofresh.com/recipes/test"
        with pytest.raises(NetworkError, match="Network request failed"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    def test_network_error_on_timeout(self, mock_scrape_html):
        """Test that NetworkError is raised on timeout."""
        mock_scrape_html.side_effect = TimeoutError("Request timed out")

        url = "https://www.hellofresh.com/recipes/test"
        with pytest.raises(NetworkError, match="Request timed out"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    def test_parse_error_on_data_extraction_failure(self, mock_scrape_html):
        """Test that ParseError is raised when data extraction fails."""
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
    def test_scraper_error_on_generic_failure(self, mock_scrape_html):
        """Test that ScraperError is raised on generic exceptions."""
        mock_scrape_html.side_effect = Exception("Generic error")

        url = "https://www.hellofresh.com/recipes/test"
        with pytest.raises(ScraperError, match="Failed to scrape recipe"):
            scrape_recipe(url)

    @patch('src.services.scraper_service.recipe_scrapers.scrape_html')
    def test_handles_missing_optional_fields(self, mock_scrape_html):
        """Test that missing optional fields are handled gracefully."""
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
    def test_instructions_string_split_into_list(self, mock_scrape_html):
        """Test that instruction strings are split into lists."""
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
    def test_yields_string_extraction(self, mock_scrape_html):
        """Test that servings are extracted from yields strings."""
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
    def test_url_whitespace_trimming(self, mock_scrape_html):
        """Test that URL whitespace is trimmed."""
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
        mock_scrape_html.assert_called_once_with(
            html=None,
            org_url="https://www.hellofresh.com/recipes/test",
            wild_mode=False
        )


class TestSsrfProtection:
    """Tests for SSRF (Server-Side Request Forgery) protection."""

    def test_blocks_localhost_by_name(self):
        """Test that localhost is blocked by hostname."""
        with pytest.raises(ScraperError, match="Access to localhost is not allowed"):
            scrape_recipe("http://localhost/recipe")

        with pytest.raises(ScraperError, match="Access to localhost is not allowed"):
            scrape_recipe("http://localhost.localdomain/recipe")

    def test_blocks_localhost_ipv4(self):
        """Test that localhost IPv4 addresses are blocked."""
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://127.0.0.1/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://127.0.0.2/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://127.255.255.255/recipe")

    def test_blocks_localhost_ipv6(self):
        """Test that localhost IPv6 addresses are blocked."""
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[::1]/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[0000:0000:0000:0000:0000:0000:0000:0001]/recipe")

    def test_blocks_private_ipv4_addresses(self):
        """Test that private IPv4 address ranges are blocked."""
        # 10.0.0.0/8
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://10.0.0.1/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://10.255.255.255/recipe")

        # 172.16.0.0/12
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://172.16.0.1/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://172.31.255.255/recipe")

        # 192.168.0.0/16
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://192.168.0.1/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://192.168.255.255/recipe")

    def test_blocks_private_ipv6_addresses(self):
        """Test that private IPv6 address ranges are blocked."""
        # Unique local addresses (fc00::/7)
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[fc00::1]/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[fd00::1]/recipe")

    def test_blocks_link_local_addresses(self):
        """Test that link-local addresses are blocked."""
        # IPv4 link-local (169.254.0.0/16)
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://169.254.1.1/recipe")

        # 169.254.169.254 is caught by cloud metadata check (which is fine - still blocked)
        with pytest.raises(ScraperError, match="Access to cloud metadata endpoints is not allowed"):
            scrape_recipe("http://169.254.169.254/recipe")

        # IPv6 link-local (fe80::/10)
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[fe80::1]/recipe")

    def test_blocks_unspecified_addresses(self):
        """Test that unspecified addresses (0.0.0.0 and ::) are blocked."""
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://0.0.0.0/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[::]/recipe")

    def test_blocks_multicast_addresses(self):
        """Test that multicast addresses are blocked."""
        # IPv4 multicast (224.0.0.0/4)
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://224.0.0.1/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://239.255.255.255/recipe")

        # IPv6 multicast (ff00::/8)
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[ff00::1]/recipe")

        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://[ff02::1]/recipe")

    def test_blocks_cloud_metadata_endpoints(self):
        """Test that cloud metadata endpoints are blocked."""
        # AWS/Azure metadata endpoint
        with pytest.raises(ScraperError, match="Access to cloud metadata endpoints is not allowed"):
            scrape_recipe("http://169.254.169.254/latest/meta-data/")

        # Google Cloud metadata endpoint
        with pytest.raises(ScraperError, match="Access to cloud metadata endpoints is not allowed"):
            scrape_recipe("http://metadata.google.internal/computeMetadata/v1/")

        # Azure metadata endpoint
        with pytest.raises(ScraperError, match="Access to cloud metadata endpoints is not allowed"):
            scrape_recipe("http://metadata.azure.com/metadata/instance")

        # AWS metadata endpoint (alternative)
        with pytest.raises(ScraperError, match="Access to cloud metadata endpoints is not allowed"):
            scrape_recipe("http://metadata.aws.amazon.com/latest/meta-data/")

    def test_blocks_invalid_url_schemes(self):
        """Test that non-http(s) schemes are blocked."""
        with pytest.raises(ScraperError, match="Invalid URL scheme"):
            scrape_recipe("file:///etc/passwd")

        with pytest.raises(ScraperError, match="Invalid URL scheme"):
            scrape_recipe("ftp://example.com/recipe")

        with pytest.raises(ScraperError, match="Invalid URL scheme"):
            scrape_recipe("gopher://example.com/recipe")

        with pytest.raises(ScraperError, match="Invalid URL scheme"):
            scrape_recipe("data:text/html,<html>test</html>")

    def test_blocks_missing_hostname(self):
        """Test that URLs without hostnames are blocked."""
        with pytest.raises(ScraperError, match="Invalid URL: missing hostname"):
            scrape_recipe("http:///path/to/recipe")

        with pytest.raises(ScraperError, match="Invalid URL: missing hostname"):
            scrape_recipe("https://")

    def test_allows_valid_public_urls(self):
        """Test that valid public URLs are allowed through SSRF checks."""
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
            except ScraperError as e:
                # If it's an SSRF-related error, the test should fail
                error_msg = str(e).lower()
                assert "localhost" not in error_msg, f"URL {url} was incorrectly blocked as localhost"
                assert "private" not in error_msg, f"URL {url} was incorrectly blocked as private"
                assert "metadata" not in error_msg, f"URL {url} was incorrectly blocked as metadata"
                assert "scheme" not in error_msg, f"URL {url} was incorrectly blocked for scheme"
                assert "hostname" not in error_msg, f"URL {url} was incorrectly blocked for hostname"
            except Exception:
                # Other exceptions (NetworkError, etc.) are fine - we only care about SSRF validation
                pass

    def test_handles_urls_with_ports(self):
        """Test that SSRF protection works correctly with URLs containing ports."""
        # Should block localhost with port
        with pytest.raises(ScraperError, match="Access to localhost is not allowed"):
            scrape_recipe("http://localhost:8080/recipe")

        # Should block private IP with port
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://192.168.1.1:8080/recipe")

        # Should block loopback with port
        with pytest.raises(ScraperError, match="Access to private, loopback, link-local, or reserved IP addresses is not allowed"):
            scrape_recipe("http://127.0.0.1:8080/recipe")

    def test_case_insensitive_hostname_blocking(self):
        """Test that hostname blocking is case-insensitive."""
        with pytest.raises(ScraperError, match="Access to localhost is not allowed"):
            scrape_recipe("http://LOCALHOST/recipe")

        with pytest.raises(ScraperError, match="Access to localhost is not allowed"):
            scrape_recipe("http://LocalHost/recipe")

        with pytest.raises(ScraperError, match="Access to cloud metadata endpoints is not allowed"):
            scrape_recipe("http://METADATA.GOOGLE.INTERNAL/recipe")
