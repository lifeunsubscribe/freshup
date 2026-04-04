"""
HelloFresh URL discovery crawler.

Discovers recipe URLs from HelloFresh via sitemap.xml with paginated
category crawl fallback. Includes rate limiting and robots.txt compliance.
"""

import logging
import ssl
import requests.exceptions
import defusedxml.ElementTree as ET  # Use defusedxml for defense-in-depth XXE protection
from typing import Optional
from xml.etree.ElementTree import Element
from urllib.parse import urljoin, urlparse

from src.services.crawlers.base_crawler import (
    RateLimiter,
    RobotsTxtParser,
    create_http_session,
)
from src.services.crawlers.exceptions import CrawlerError, CrawlerNetworkError, CrawlerParseError


# Configure logging
logger = logging.getLogger(__name__)

# HelloFresh base URL
HELLOFRESH_BASE_URL = "https://www.hellofresh.com"


class HelloFreshCrawler:
    """
    Crawler for discovering HelloFresh recipe URLs.

    Uses a two-strategy approach:
    1. Primary: Parse sitemap.xml to extract recipe URLs
    2. Fallback: Crawl paginated recipe category pages

    Features:
    - Rate limiting (2s default, respects robots.txt Crawl-delay)
    - robots.txt compliance
    - HTTP retry logic with exponential backoff
    """

    def __init__(
        self,
        base_url: str = HELLOFRESH_BASE_URL,
        rate_limit_delay: float = 2.0,
    ):
        """
        Initialize HelloFresh crawler.

        Args:
            base_url: Base URL for HelloFresh (default: https://www.hellofresh.com)
            rate_limit_delay: Default delay between requests in seconds (default: 2.0)

        Raises:
            ValueError: If base_url is invalid or malformed
        """
        # Validate base_url
        if not base_url or not isinstance(base_url, str):
            raise ValueError("base_url must be a non-empty string")

        parsed = urlparse(base_url)
        if not parsed.scheme or parsed.scheme not in ['http', 'https']:
            raise ValueError(f"base_url must have http or https scheme, got: {base_url}")
        if not parsed.netloc:
            raise ValueError(f"base_url must include a valid domain, got: {base_url}")

        self.base_url = base_url.rstrip('/')
        self.domain = parsed.netloc

        # Initialize utilities
        self.session = create_http_session(retries=3, backoff_factor=0.5, timeout=10)
        self.rate_limiter = RateLimiter(default_delay=rate_limit_delay)
        self.robots_parser = RobotsTxtParser()

        # Check robots.txt and adjust rate limiting if needed
        self._configure_from_robots_txt()

    def _configure_from_robots_txt(self) -> None:
        """
        Configure crawler based on robots.txt directives.

        Checks for Crawl-delay directive and updates rate limiter accordingly.
        """
        crawl_delay = self.robots_parser.get_crawl_delay(self.base_url)
        if crawl_delay:
            self.rate_limiter.set_domain_delay(self.domain, crawl_delay)
            logger.info(f"Using Crawl-delay from robots.txt: {crawl_delay}s")

    def discover_recipe_urls(self, max_pages: Optional[int] = None) -> list[str]:
        """
        Discover recipe URLs from HelloFresh.

        Attempts to discover URLs using sitemap.xml first, falling back to
        paginated category crawling if sitemap is unavailable or fails.

        Exception Handling:
            This method uses standardized exception handling (aligned with KitchenSanctuaryCrawler):
            - InvalidURL -> CrawlerNetworkError
            - RequestException (Connection, Timeout, HTTP errors) -> CrawlerNetworkError
            - SSL/Certificate errors -> CrawlerNetworkError
            - Parsing errors (ValueError, UnicodeDecodeError) -> CrawlerParseError
            - I/O errors (OSError, IOError) -> CrawlerError
            - Programming errors (AttributeError, TypeError, etc.) propagate unchanged

        Args:
            max_pages: Maximum number of pages to crawl (for fallback strategy only).
                      None means no limit. Used primarily for testing.

        Returns:
            List of discovered recipe URLs

        Raises:
            CrawlerNetworkError: If network requests fail (connection, timeout, HTTP errors)
            CrawlerParseError: If parsing fails (malformed XML, invalid structure)
            CrawlerError: If unexpected errors occur

        Example:
            >>> crawler = HelloFreshCrawler()
            >>> urls = crawler.discover_recipe_urls(max_pages=5)
            >>> print(f"Discovered {len(urls)} recipe URLs")
        """
        logger.info("Starting HelloFresh recipe URL discovery")

        # Strategy 1: Try sitemap.xml first
        # Capture any exception from sitemap strategy to preserve debugging context
        sitemap_exception = None
        try:
            urls = self._discover_from_sitemap()
            if urls:
                logger.info(f"Discovered {len(urls)} URLs from sitemap.xml")
                return urls
            else:
                logger.warning("Sitemap.xml returned no URLs, trying fallback strategy")
        except (CrawlerNetworkError, CrawlerParseError):
            # Re-raise crawler exceptions as-is (already wrapped)
            raise
        except requests.exceptions.InvalidURL as e:
            # Wrap malformed URLs from external data at the public API boundary
            # This catches InvalidURL exceptions from external sitemaps - these are external data errors
            logger.exception(f"Sitemap strategy failed with invalid URL: {e}")
            raise CrawlerNetworkError(f"Invalid URL during URL discovery: {e}") from e
        except requests.exceptions.RequestException as e:
            # Actual network errors - log and try fallback
            # This catches all requests exceptions: ConnectionError, Timeout, HTTPError, etc.
            logger.warning(f"Sitemap strategy failed with network error: {e}, trying fallback strategy")
            # Don't raise yet - try fallback first, but preserve exception for chaining
            sitemap_exception = e
        except (ssl.SSLError, ssl.CertificateError) as e:
            # Catch SSL/TLS errors specifically - these are external network issues
            logger.warning(f"Sitemap strategy failed with SSL error: {e}, trying fallback strategy")
            sitemap_exception = e
        except (ValueError, UnicodeDecodeError, OSError, IOError) as e:
            # Catch specific external errors: parsing, encoding, I/O issues
            # Programming errors (AttributeError, TypeError, KeyError) will propagate
            logger.warning(f"Sitemap strategy failed with {type(e).__name__}: {e}, trying fallback strategy")
            # Don't raise yet - try fallback first, but preserve exception for chaining
            sitemap_exception = e

        # Strategy 2: Fallback to paginated category crawl
        try:
            urls = self._discover_from_paginated_categories(max_pages=max_pages)
            logger.info(f"Discovered {len(urls)} URLs from paginated categories")
            return urls
        except (CrawlerNetworkError, CrawlerParseError):
            # Re-raise crawler exceptions as-is (already wrapped)
            raise
        except requests.exceptions.InvalidURL as e:
            # Wrap malformed URLs from external data at the public API boundary
            logger.exception(f"Paginated category strategy failed with invalid URL: {e}")

            # Include context from sitemap failure if both strategies failed
            if sitemap_exception:
                error_msg = f"Invalid URL during URL discovery: {e}. Sitemap strategy also failed: {sitemap_exception}"
            else:
                error_msg = f"Invalid URL during URL discovery: {e}"
            raise CrawlerNetworkError(error_msg) from e
        except requests.exceptions.RequestException as e:
            # Wrap actual network errors at the public API boundary
            # This catches all requests exceptions: ConnectionError, Timeout, HTTPError, etc.
            # These are genuine network/transport issues, not programming bugs
            logger.exception(f"Paginated category strategy failed with network error: {e}")

            # Include context from sitemap failure if both strategies failed
            if sitemap_exception:
                error_msg = f"Network error during URL discovery: {e}. Sitemap strategy also failed: {sitemap_exception}"
            else:
                error_msg = f"Network error during URL discovery: {e}"
            raise CrawlerNetworkError(error_msg) from e
        except (ssl.SSLError, ssl.CertificateError) as e:
            # Wrap SSL/TLS errors at the public API boundary
            logger.exception(f"Paginated category strategy failed with SSL error: {e}")

            # Include context from sitemap failure if both strategies failed
            if sitemap_exception:
                error_msg = f"SSL error during URL discovery: {e}. Sitemap strategy also failed: {sitemap_exception}"
            else:
                error_msg = f"SSL error during URL discovery: {e}"
            raise CrawlerNetworkError(error_msg) from e
        except (ValueError, UnicodeDecodeError) as e:
            # Wrap parsing/encoding errors at the public API boundary
            logger.exception(f"Paginated category strategy failed with {type(e).__name__}: {e}")

            # Include context from sitemap failure if both strategies failed
            if sitemap_exception:
                error_msg = f"Parse error during URL discovery: {e}. Sitemap strategy also failed: {sitemap_exception}"
            else:
                error_msg = f"Parse error during URL discovery: {e}"
            raise CrawlerParseError(error_msg) from e
        except (OSError, IOError) as e:
            # Catch I/O errors specifically (network operations, file access)
            # These are external errors, not programming bugs
            logger.exception(f"Paginated category strategy failed with I/O error: {e}")

            # Include context from sitemap failure if both strategies failed
            if sitemap_exception:
                error_msg = f"I/O error during URL discovery: {e}. Sitemap strategy also failed: {sitemap_exception}"
            else:
                error_msg = f"I/O error during URL discovery: {e}"
            raise CrawlerError(error_msg) from e

    def _discover_from_sitemap(self) -> list[str]:
        """
        Discover recipe URLs from sitemap.xml.

        Parses the sitemap.xml file and extracts URLs containing '/recipes/'.

        Returns:
            List of recipe URLs found in sitemap

        Raises:
            Exception: If sitemap fetch or parsing fails
        """
        sitemap_url = urljoin(self.base_url, "/sitemap.xml")

        # Check robots.txt before fetching
        if not self.robots_parser.can_fetch(sitemap_url):
            raise Exception(f"robots.txt disallows access to {sitemap_url}")

        # Rate limit
        self.rate_limiter.wait_if_needed(self.domain)

        logger.info(f"Fetching sitemap from {sitemap_url}")
        response = self.session.get(sitemap_url, timeout=10)
        response.raise_for_status()

        # Parse XML with error handling for invalid/empty content
        try:
            if not response.content:
                raise ValueError("Sitemap response is empty")
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse sitemap XML from {sitemap_url}: {e}")
        except (UnicodeDecodeError, UnicodeError) as e:
            # Catch encoding errors specifically - these are external data issues
            raise ValueError(f"Encoding error processing sitemap from {sitemap_url}: {e}")

        # Handle sitemap index (sitemaps that link to other sitemaps)
        recipe_urls = []

        # Define sitemap XML namespace for parsing
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Check if this is a sitemap index (references other sitemaps)
        sitemap_elements = root.findall('.//ns:sitemap', namespace)

        if sitemap_elements:
            # This is a sitemap index, fetch recipe sitemap
            for sitemap_elem in sitemap_elements:
                loc = sitemap_elem.find('ns:loc', namespace)
                if loc is not None and loc.text and 'recipe' in loc.text.lower():
                    recipe_sitemap_url = loc.text
                    logger.info(f"Found recipe sitemap: {recipe_sitemap_url}")

                    # Fetch recipe sitemap
                    if self.robots_parser.can_fetch(recipe_sitemap_url):
                        self.rate_limiter.wait_if_needed(self.domain)
                        recipe_response = self.session.get(recipe_sitemap_url, timeout=10)
                        recipe_response.raise_for_status()

                        # Parse recipe sitemap with error handling
                        try:
                            if not recipe_response.content:
                                raise ValueError(f"Recipe sitemap response is empty: {recipe_sitemap_url}")
                            recipe_root = ET.fromstring(recipe_response.content)
                        except ET.ParseError as e:
                            raise ValueError(f"Failed to parse recipe sitemap XML from {recipe_sitemap_url}: {e}")
                        except (UnicodeDecodeError, UnicodeError) as e:
                            # Catch encoding errors specifically - these are external data issues
                            raise ValueError(f"Encoding error processing recipe sitemap from {recipe_sitemap_url}: {e}")
                        urls = self._extract_urls_from_sitemap(recipe_root, namespace)
                        recipe_urls.extend(urls)
                    else:
                        logger.warning(f"robots.txt disallows {recipe_sitemap_url}")
        else:
            # This is a regular sitemap, extract URLs directly
            recipe_urls = self._extract_urls_from_sitemap(root, namespace)

        # Remove duplicates that may occur when multiple sub-sitemaps contain the same URLs
        recipe_urls = list(set(recipe_urls))
        return recipe_urls

    def _extract_urls_from_sitemap(self, root: Element, namespace: dict) -> list[str]:
        """
        Extract recipe URLs from a sitemap XML element.

        Args:
            root: XML root element
            namespace: XML namespace dictionary

        Returns:
            List of recipe URLs
        """
        urls = []
        url_elements = root.findall('.//ns:url', namespace)

        for url_elem in url_elements:
            loc = url_elem.find('ns:loc', namespace)
            if loc is not None and loc.text:
                url = loc.text
                # Filter for recipe URLs (HelloFresh uses /recipes/ or /recipe/ in paths)
                if '/recipes/' in url or '/recipe/' in url:
                    urls.append(url)

        logger.debug(f"Extracted {len(urls)} recipe URLs from sitemap")
        return urls

    def _discover_from_paginated_categories(self, max_pages: Optional[int] = None) -> list[str]:
        """
        Discover recipe URLs by crawling paginated category pages.

        Fallback strategy when sitemap.xml is unavailable. Crawls the main
        recipes page and follows pagination links.

        Args:
            max_pages: Maximum number of pages to crawl (None = no limit)

        Returns:
            List of discovered recipe URLs

        Raises:
            Exception: If crawling fails
        """
        recipe_urls = []
        page_num = 1
        base_recipes_url = urljoin(self.base_url, "/recipes")

        logger.info(f"Starting paginated category crawl (max_pages={max_pages})")

        while True:
            # Stop if we've reached max_pages
            if max_pages is not None and page_num > max_pages:
                logger.info(f"Reached max_pages limit ({max_pages})")
                break

            # Construct pagination URL (adjust based on HelloFresh's actual pagination)
            if page_num == 1:
                page_url = base_recipes_url
            else:
                # HelloFresh may use ?page=N or /recipes/page/N - adjust as needed
                page_url = f"{base_recipes_url}?page={page_num}"

            # Check robots.txt
            if not self.robots_parser.can_fetch(page_url):
                logger.warning(f"robots.txt disallows {page_url}, stopping")
                break

            # Rate limit
            self.rate_limiter.wait_if_needed(self.domain)

            logger.info(f"Fetching page {page_num}: {page_url}")

            try:
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
            except (requests.exceptions.RequestException, ssl.SSLError, ssl.CertificateError, OSError, IOError) as e:
                # Catch specific network/I/O errors only - let programming bugs propagate
                logger.error(f"Failed to fetch page {page_num}: {e}")
                break

            # Parse HTML to find recipe URLs
            # This is a simplified approach - in production, use BeautifulSoup or similar
            html = response.text
            page_urls = self._extract_recipe_urls_from_html(html)

            if not page_urls:
                logger.info(f"No recipe URLs found on page {page_num}, stopping")
                break

            recipe_urls.extend(page_urls)
            logger.info(f"Found {len(page_urls)} URLs on page {page_num}")

            page_num += 1

        logger.info(f"Paginated crawl complete: {len(recipe_urls)} URLs from {page_num - 1} pages")
        return recipe_urls

    def _extract_recipe_urls_from_html(self, html: str) -> list[str]:
        """
        Extract recipe URLs from HTML content.

        Uses regex to find recipe links. In production, consider using
        BeautifulSoup for more robust HTML parsing.

        Args:
            html: HTML content to parse

        Returns:
            List of recipe URLs found in HTML
        """
        import re

        # Find all href links containing /recipes/
        pattern = r'href=["\']([^"\']*?/recipes?/[^"\']+?)["\']'
        matches = re.findall(pattern, html)

        # Normalize and deduplicate URLs
        urls = []
        seen = set()

        for match in matches:
            # Convert relative URLs to absolute
            if match.startswith('/'):
                url = urljoin(self.base_url, match)
            elif match.startswith('http'):
                url = match
            else:
                # Skip relative URLs without leading slash (e.g., "../page")
                continue

            # Normalize: remove query params and fragments for deduplication
            url = url.split('?')[0].split('#')[0]

            # Deduplicate URLs
            if url not in seen:
                seen.add(url)
                urls.append(url)

        return urls
