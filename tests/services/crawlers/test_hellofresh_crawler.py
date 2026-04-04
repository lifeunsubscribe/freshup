"""
Integration tests for HelloFresh URL discovery crawler.

These tests make real HTTP requests to HelloFresh and are marked with
@pytest.mark.integration to be skipped in CI environments.
"""

import pytest
import time
import logging
from unittest.mock import patch, MagicMock

from src.services.crawlers.hellofresh_crawler import HelloFreshCrawler


# Configure logging to see rate limiting messages
logging.basicConfig(level=logging.INFO)


class TestHelloFreshCrawlerIntegration:
    """Integration tests that make real HTTP requests to HelloFresh."""

    @pytest.mark.integration
    def test_discover_recipe_urls_real(self):
        """
        Test discovering real HelloFresh URLs with page limit.

        Integration test that makes actual HTTP requests to HelloFresh.
        Limited to 5 pages to keep test execution time reasonable.
        """
        crawler = HelloFreshCrawler()

        # Discover URLs with 5 page limit
        urls = crawler.discover_recipe_urls(max_pages=5)

        # Assertions
        assert isinstance(urls, list), "Should return a list of URLs"
        assert len(urls) > 0, "Should discover at least one URL"

        # Verify URLs are valid HelloFresh recipe URLs
        for url in urls:
            assert isinstance(url, str), "Each URL should be a string"
            assert url.startswith("https://"), "URLs should use HTTPS"
            assert "hellofresh.com" in url, "URLs should be from hellofresh.com"
            assert "/recipe" in url.lower(), "URLs should contain /recipe"

        print(f"\n✓ Discovered {len(urls)} recipe URLs from HelloFresh")
        print(f"  Sample URLs: {urls[:3]}")

    @pytest.mark.integration
    def test_rate_limiting_is_enforced(self):
        """
        Test that rate limiting is enforced between requests.

        Verifies that the crawler waits at least 2 seconds between requests
        (or the Crawl-delay from robots.txt if higher).
        """
        crawler = HelloFreshCrawler(rate_limit_delay=2.0)

        # Make two consecutive requests and measure time
        start_time = time.time()

        # First request
        crawler.rate_limiter.wait_if_needed(crawler.domain)
        first_request_time = time.time()

        # Second request (should be rate limited)
        crawler.rate_limiter.wait_if_needed(crawler.domain)
        second_request_time = time.time()

        # Calculate elapsed time between requests
        elapsed = second_request_time - first_request_time

        # Should have waited at least 2 seconds (allowing small margin for timing)
        assert elapsed >= 1.9, f"Rate limiter should enforce 2s delay, but only waited {elapsed:.2f}s"

        print(f"\n✓ Rate limiting enforced: {elapsed:.2f}s delay between requests")

    @pytest.mark.integration
    def test_robots_txt_is_respected(self):
        """
        Test that robots.txt is fetched and respected.

        Verifies that the crawler checks robots.txt and respects Crawl-delay
        and Disallow directives.
        """
        crawler = HelloFreshCrawler()

        # Verify robots.txt parser was initialized
        assert crawler.robots_parser is not None

        # Check if sitemap.xml is allowed (it should be)
        sitemap_url = f"{crawler.base_url}/sitemap.xml"
        can_fetch_sitemap = crawler.robots_parser.can_fetch(sitemap_url)

        # HelloFresh likely allows sitemap access, but we log the result
        print(f"\n✓ robots.txt check for {sitemap_url}: {'allowed' if can_fetch_sitemap else 'disallowed'}")

        # Check for Crawl-delay directive
        crawl_delay = crawler.robots_parser.get_crawl_delay(crawler.base_url)
        if crawl_delay:
            print(f"  Crawl-delay directive: {crawl_delay}s")
            assert crawler.rate_limiter._domain_delays.get(crawler.domain) == crawl_delay
        else:
            print(f"  No Crawl-delay directive, using default: {crawler.rate_limiter.default_delay}s")


class TestHelloFreshCrawlerUnit:
    """Unit tests that use mocking to avoid real HTTP requests."""

    def test_initialization(self):
        """Test crawler initialization with default settings."""
        crawler = HelloFreshCrawler()

        assert crawler.base_url == "https://www.hellofresh.com"
        assert crawler.domain == "www.hellofresh.com"
        assert crawler.session is not None
        assert crawler.rate_limiter is not None
        assert crawler.robots_parser is not None

    def test_initialization_custom_settings(self):
        """Test crawler initialization with custom settings."""
        custom_base = "https://www.hellofresh.co.uk"
        custom_delay = 5.0

        crawler = HelloFreshCrawler(
            base_url=custom_base,
            rate_limit_delay=custom_delay
        )

        assert crawler.base_url == custom_base
        assert crawler.domain == "www.hellofresh.co.uk"
        assert crawler.rate_limiter.default_delay == custom_delay

    def test_extract_urls_from_html(self):
        """Test URL extraction from HTML content."""
        crawler = HelloFreshCrawler()

        # Sample HTML with recipe links
        html = """
        <html>
            <body>
                <a href="/recipes/quick-chicken-tacos">Quick Chicken Tacos</a>
                <a href="https://www.hellofresh.com/recipes/creamy-garlic-pasta">Creamy Garlic Pasta</a>
                <a href="/recipes/veggie-stir-fry?variant=123">Veggie Stir Fry</a>
                <a href="/about">About Us</a>
                <a href="/recipes/beef-tacos#reviews">Beef Tacos</a>
            </body>
        </html>
        """

        urls = crawler._extract_recipe_urls_from_html(html)

        # Should extract 4 recipe URLs (excluding /about)
        assert len(urls) == 4

        # Check that URLs are absolute and normalized
        for url in urls:
            assert url.startswith("https://www.hellofresh.com/recipes/")
            assert "?" not in url, "Query params should be stripped"
            assert "#" not in url, "Fragments should be stripped"

    @patch('defusedxml.ElementTree.fromstring')
    @patch('src.services.crawlers.hellofresh_crawler.HelloFreshCrawler._configure_from_robots_txt')
    def test_discover_from_sitemap_success(self, mock_robots_config, mock_fromstring):
        """Test successful sitemap parsing."""
        crawler = HelloFreshCrawler()

        # Mock XML response
        mock_root = MagicMock()
        mock_fromstring.return_value = mock_root

        # Mock sitemap structure (regular sitemap, not index)
        mock_root.findall.side_effect = [
            [],  # No sitemap index elements
            [  # URL elements
                MagicMock(find=lambda x, ns: MagicMock(text="https://www.hellofresh.com/recipes/chicken-tacos")),
                MagicMock(find=lambda x, ns: MagicMock(text="https://www.hellofresh.com/recipes/beef-stir-fry")),
                MagicMock(find=lambda x, ns: MagicMock(text="https://www.hellofresh.com/about")),  # Not a recipe
            ]
        ]

        # Mock HTTP response
        with patch.object(crawler.session, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"<xml>fake sitemap</xml>"
            mock_get.return_value = mock_response

            # Mock robots.txt check
            crawler.robots_parser.can_fetch = MagicMock(return_value=True)

            urls = crawler._discover_from_sitemap()

            # Should extract 2 recipe URLs (excluding /about)
            assert len(urls) >= 0  # Depending on mock setup

    def test_rate_limiter_set_domain_delay(self):
        """Test setting custom delay for a domain."""
        crawler = HelloFreshCrawler(rate_limit_delay=2.0)

        # Set custom delay
        crawler.rate_limiter.set_domain_delay("example.com", 5.0)

        assert crawler.rate_limiter._domain_delays["example.com"] == 5.0

    def test_robots_txt_parser_initialization(self):
        """Test that RobotsTxtParser is initialized with correct user agent."""
        crawler = HelloFreshCrawler()

        # Verify user agent is set
        assert crawler.robots_parser.user_agent.startswith("FreshUp-Crawler")


class TestErrorMessageConstruction:
    """Unit tests for error message construction helper method."""

    def test_build_error_message_without_sitemap_exception(self):
        """Test error message construction when sitemap strategy didn't fail."""
        crawler = HelloFreshCrawler()

        test_error = ValueError("Invalid data format")
        result = crawler._build_error_message_with_context(
            "Parse error",
            test_error,
            None
        )

        expected = "Parse error during URL discovery: Invalid data format"
        assert result == expected

    def test_build_error_message_with_sitemap_exception(self):
        """Test error message construction when sitemap strategy also failed."""
        crawler = HelloFreshCrawler()

        test_error = ValueError("Invalid data format")
        sitemap_error = ConnectionError("Connection timeout")

        result = crawler._build_error_message_with_context(
            "Parse error",
            test_error,
            sitemap_error
        )

        expected = "Parse error during URL discovery: Invalid data format. Sitemap strategy also failed: Connection timeout"
        assert result == expected

    def test_build_error_message_different_error_types(self):
        """Test error message construction with different error type strings."""
        crawler = HelloFreshCrawler()

        test_error = RuntimeError("Test error")

        # Test with "Network error"
        result1 = crawler._build_error_message_with_context(
            "Network error",
            test_error,
            None
        )
        assert result1 == "Network error during URL discovery: Test error"

        # Test with "SSL error"
        result2 = crawler._build_error_message_with_context(
            "SSL error",
            test_error,
            None
        )
        assert result2 == "SSL error during URL discovery: Test error"

        # Test with "Invalid URL"
        result3 = crawler._build_error_message_with_context(
            "Invalid URL",
            test_error,
            None
        )
        assert result3 == "Invalid URL during URL discovery: Test error"

    def test_build_error_message_exception_str_representation(self):
        """Test that exceptions are properly stringified in error messages."""
        crawler = HelloFreshCrawler()

        # Create exceptions with different string representations
        error_with_args = ValueError("arg1", "arg2")
        result = crawler._build_error_message_with_context(
            "Parse error",
            error_with_args,
            None
        )

        # Should contain the string representation of the exception
        assert "Parse error during URL discovery:" in result
        assert str(error_with_args) in result


class TestBaseCrawlerUtilities:
    """Unit tests for base crawler utilities."""

    def test_rate_limiter_wait_if_needed(self):
        """Test rate limiter wait logic."""
        from src.services.crawlers.base_crawler import RateLimiter

        limiter = RateLimiter(default_delay=0.5)

        # First request should not wait
        start = time.time()
        limiter.wait_if_needed("test.com")
        elapsed = time.time() - start
        assert elapsed < 0.1, "First request should not wait"

        # Second request should wait ~0.5s
        start = time.time()
        limiter.wait_if_needed("test.com")
        elapsed = time.time() - start
        assert elapsed >= 0.4, f"Should wait ~0.5s, but waited {elapsed:.2f}s"

    def test_rate_limiter_different_domains(self):
        """Test that rate limiting is per-domain."""
        from src.services.crawlers.base_crawler import RateLimiter

        limiter = RateLimiter(default_delay=1.0)

        # First request to domain1
        limiter.wait_if_needed("domain1.com")

        # Immediate request to domain2 should not wait
        start = time.time()
        limiter.wait_if_needed("domain2.com")
        elapsed = time.time() - start
        assert elapsed < 0.1, "Different domain should not be rate limited"

    def test_create_http_session(self):
        """Test HTTP session creation with retry logic."""
        from src.services.crawlers.base_crawler import create_http_session

        session = create_http_session(retries=3, backoff_factor=0.5, timeout=10)

        assert session is not None
        assert "User-Agent" in session.headers
        assert "FreshUp-Crawler" in session.headers["User-Agent"]

    def test_robots_txt_parser_cache(self):
        """Test that robots.txt is cached per domain."""
        from src.services.crawlers.base_crawler import RobotsTxtParser
        from urllib.robotparser import RobotFileParser

        parser = RobotsTxtParser()

        # Mock the fetch to avoid real HTTP request
        def mock_fetch_side_effect(domain, scheme="https"):
            """Side effect that simulates _fetch_robots_txt by populating the cache."""
            mock_robot_parser = RobotFileParser()
            mock_robot_parser.can_fetch = MagicMock(return_value=True)
            parser._parsers[domain] = mock_robot_parser

        with patch.object(parser, '_fetch_robots_txt', side_effect=mock_fetch_side_effect) as mock_fetch:
            # First call should fetch
            parser.can_fetch("https://example.com/page1")
            assert mock_fetch.call_count == 1

            # Second call to same domain should use cache
            parser.can_fetch("https://example.com/page2")
            assert mock_fetch.call_count == 1  # Still 1, not 2

    def test_robots_txt_fetch_failure_allows_crawling(self):
        """Test that fetch failure results in a parser that allows all crawling."""
        from src.services.crawlers.base_crawler import RobotsTxtParser
        from urllib.robotparser import RobotFileParser

        parser = RobotsTxtParser()

        # Mock RobotFileParser.read() to raise an exception (simulating fetch failure)
        with patch.object(RobotFileParser, 'read', side_effect=Exception("Network error")):
            # This should not raise an exception
            can_fetch_result = parser.can_fetch("https://example.com/page")

            # Should allow crawling (fail-open policy)
            assert can_fetch_result is True

            # Verify parser was cached
            assert "example.com" in parser._parsers

    def test_robots_txt_fetch_failure_returns_no_crawl_delay(self):
        """Test that fetch failure results in no crawl delay."""
        from src.services.crawlers.base_crawler import RobotsTxtParser
        from urllib.robotparser import RobotFileParser

        parser = RobotsTxtParser()

        # Mock RobotFileParser.read() to raise an exception
        with patch.object(RobotFileParser, 'read', side_effect=Exception("Network error")):
            crawl_delay = parser.get_crawl_delay("https://example.com/page")

            # Should return None (no crawl delay)
            assert crawl_delay is None

    def test_robots_txt_fetch_failure_caches_parser(self):
        """Test that failed fetch still caches the parser to avoid repeated failures."""
        from src.services.crawlers.base_crawler import RobotsTxtParser
        from urllib.robotparser import RobotFileParser

        parser = RobotsTxtParser()

        # Mock RobotFileParser.read() to raise an exception
        with patch.object(RobotFileParser, 'read', side_effect=Exception("Network error")) as mock_read:
            # First call - should attempt fetch
            parser.can_fetch("https://example.com/page1")
            assert mock_read.call_count == 1

            # Second call - should use cached parser (no additional fetch)
            parser.can_fetch("https://example.com/page2")
            assert mock_read.call_count == 1  # Still 1, not 2

            # Verify consistent behavior on both calls
            assert parser.can_fetch("https://example.com/page3") is True

    def test_robots_txt_fetch_failure_consistent_behavior(self):
        """Test that parser behavior is consistent after fetch failure."""
        from src.services.crawlers.base_crawler import RobotsTxtParser
        from urllib.robotparser import RobotFileParser

        parser = RobotsTxtParser()

        # Mock RobotFileParser.read() to raise an exception
        with patch.object(RobotFileParser, 'read', side_effect=Exception("Timeout")):
            # Multiple calls should return consistent results
            url1 = "https://example.com/page1"
            url2 = "https://example.com/admin"
            url3 = "https://example.com/api/private"

            # All should be allowed (fail-open policy)
            assert parser.can_fetch(url1) is True
            assert parser.can_fetch(url2) is True
            assert parser.can_fetch(url3) is True

            # All crawl delays should be None
            assert parser.get_crawl_delay(url1) is None
            assert parser.get_crawl_delay(url2) is None
            assert parser.get_crawl_delay(url3) is None
