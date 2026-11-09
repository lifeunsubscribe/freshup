"""
HelloFresh URL discovery crawler.

Discovers recipe URLs from HelloFresh via sitemap.xml with paginated
category crawl fallback. Includes rate limiting and robots.txt compliance.
"""

import logging
import re
import ssl
import requests.exceptions
import defusedxml.ElementTree as ET  # Use defusedxml for defense-in-depth XXE protection
from typing import Literal, Optional
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

# Seconds to wait for a sitemap. The recipe sitemap is far larger than a normal page.
SITEMAP_TIMEOUT = 30

# Where to look for a sitemap when robots.txt does not declare one
FALLBACK_SITEMAP_PATHS = ("/sitemap_index.xml", "/sitemap.xml")

# A recipe page is /recipes/<slug>-<id>, where <id> is a 24-character hex id.
# Everything else under /recipes/ is a listing: a cuisine, an ingredient, a collection.
_RECIPE_PATH = re.compile(r"^/recipes/[^/]+-[0-9a-f]{24}/?$")

UrlKind = Literal["recipe", "collection", "other"]


def classify_hellofresh_url(url: str) -> UrlKind:
    """
    Say what kind of HelloFresh page a URL points at.

    Args:
        url: Absolute HelloFresh URL

    Returns:
        "recipe" for a single recipe page (the only kind that can be imported),
        "collection" for a listing of recipes (cuisine, ingredient, hall of fame),
        "other" for anything outside /recipes.

    Example:
        >>> classify_hellofresh_url("https://www.hellofresh.com/recipes/lomo-saltado-67fccc45e22258bf0284050d")
        'recipe'
        >>> classify_hellofresh_url("https://www.hellofresh.com/recipes/pasta-recipes")
        'collection'
    """
    path = urlparse(url).path
    if _RECIPE_PATH.match(path):
        return "recipe"
    if path.rstrip("/") == "/recipes" or path.startswith("/recipes/"):
        return "collection"
    return "other"


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

    def _build_error_message_with_context(
        self,
        error_type: str,
        current_error: Exception,
        sitemap_exception: Optional[Exception]
    ) -> str:
        """
        Build error message with optional sitemap failure context.

        Args:
            error_type: Type of error (e.g., "Invalid URL", "Network error")
            current_error: The current exception being handled
            sitemap_exception: Optional exception from sitemap strategy failure

        Returns:
            Formatted error message with optional sitemap context
        """
        base_msg = f"{error_type} during URL discovery: {current_error}"
        if sitemap_exception:
            return f"{base_msg}. Sitemap strategy also failed: {sitemap_exception}"
        return base_msg

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
            logger.warning(f"Sitemap strategy failed with invalid URL: {e}, trying fallback strategy")
            # Don't raise yet - try fallback first, but preserve exception for chaining
            sitemap_exception = e
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
            error_msg = self._build_error_message_with_context("Invalid URL", e, sitemap_exception)
            raise CrawlerNetworkError(error_msg) from e
        except requests.exceptions.RequestException as e:
            # Wrap actual network errors at the public API boundary
            # This catches all requests exceptions: ConnectionError, Timeout, HTTPError, etc.
            # These are genuine network/transport issues, not programming bugs
            logger.exception(f"Paginated category strategy failed with network error: {e}")
            error_msg = self._build_error_message_with_context("Network error", e, sitemap_exception)
            raise CrawlerNetworkError(error_msg) from e
        except (ssl.SSLError, ssl.CertificateError) as e:
            # Wrap SSL/TLS errors at the public API boundary
            logger.exception(f"Paginated category strategy failed with SSL error: {e}")
            error_msg = self._build_error_message_with_context("SSL error", e, sitemap_exception)
            raise CrawlerNetworkError(error_msg) from e
        except (ValueError, UnicodeDecodeError) as e:
            # Wrap parsing/encoding errors at the public API boundary
            logger.exception(f"Paginated category strategy failed with {type(e).__name__}: {e}")
            error_msg = self._build_error_message_with_context("Parse error", e, sitemap_exception)
            raise CrawlerParseError(error_msg) from e
        except (OSError, IOError) as e:
            # Catch I/O errors specifically (network operations, file access)
            # These are external errors, not programming bugs
            logger.exception(f"Paginated category strategy failed with I/O error: {e}")
            error_msg = self._build_error_message_with_context("I/O error", e, sitemap_exception)
            raise CrawlerError(error_msg) from e

    def _discover_from_sitemap(self) -> list[str]:
        """
        Discover recipe URLs from HelloFresh's sitemaps.

        Starts from the sitemaps the site declares in robots.txt, and only guesses
        at conventional locations if it declares none. Returns recipe pages only;
        collection pages listed alongside them are dropped.

        Returns:
            Sorted list of recipe URLs found

        Raises:
            requests.exceptions.RequestException: If no sitemap could be fetched
            ValueError: If no sitemap could be parsed
        """
        declared = [
            u for u in self.robots_parser.get_sitemaps(self.base_url)
            if urlparse(u).netloc == self.domain
        ]
        if declared:
            # Go straight to the recipe sitemaps when the site names them
            entry_points = [u for u in declared if 'recipe' in u.lower()] or declared
        else:
            entry_points = [urljoin(self.base_url, path) for path in FALLBACK_SITEMAP_PATHS]

        recipe_urls: set[str] = set()
        fetched: set[str] = set()
        succeeded = False
        last_error: Optional[Exception] = None

        for sitemap_url in entry_points:
            try:
                recipe_urls.update(self._collect_from_sitemap(sitemap_url, fetched))
                succeeded = True
            except (requests.exceptions.RequestException, ValueError) as e:
                logger.warning(f"Could not read sitemap {sitemap_url}: {e}")
                last_error = e
                continue

            # Guessed locations are alternatives to each other: stop at the first that works
            if not declared:
                break

        if not succeeded and last_error is not None:
            raise last_error

        return sorted(recipe_urls)

    def _collect_from_sitemap(self, sitemap_url: str, fetched: set[str]) -> list[str]:
        """
        Fetch one sitemap and return the recipe URLs in it.

        Follows a sitemap index into the sitemaps it lists whose name mentions
        recipes. `fetched` records what has already been read, because a site can
        list the same sitemap both in robots.txt and in its index.

        Args:
            sitemap_url: Sitemap or sitemap index to fetch
            fetched: Sitemap URLs already read during this discovery (updated in place)

        Returns:
            Recipe URLs found

        Raises:
            requests.exceptions.RequestException: If the fetch fails
            ValueError: If the response is empty or is not valid XML
        """
        if sitemap_url in fetched:
            return []
        fetched.add(sitemap_url)

        if not self.robots_parser.can_fetch(sitemap_url):
            logger.warning(f"robots.txt disallows {sitemap_url}")
            return []

        self.rate_limiter.wait_if_needed(self.domain)

        logger.info(f"Fetching sitemap from {sitemap_url}")
        response = self.session.get(sitemap_url, timeout=SITEMAP_TIMEOUT)
        response.raise_for_status()

        try:
            if not response.content:
                raise ValueError(f"Sitemap response is empty: {sitemap_url}")
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse sitemap XML from {sitemap_url}: {e}")
        except (UnicodeDecodeError, UnicodeError) as e:
            # Catch encoding errors specifically - these are external data issues
            raise ValueError(f"Encoding error processing sitemap from {sitemap_url}: {e}")

        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # A sitemap index lists other sitemaps rather than pages
        sitemap_elements = root.findall('.//ns:sitemap', namespace)
        if not sitemap_elements:
            return self._extract_urls_from_sitemap(root, namespace)

        recipe_urls: list[str] = []
        for sitemap_elem in sitemap_elements:
            loc = sitemap_elem.find('ns:loc', namespace)
            if loc is not None and loc.text and 'recipe' in loc.text.lower():
                logger.info(f"Found recipe sitemap: {loc.text}")
                recipe_urls.extend(self._collect_from_sitemap(loc.text, fetched))
        return recipe_urls

    def _extract_urls_from_sitemap(self, root: Element, namespace: dict) -> list[str]:
        """
        Extract recipe URLs from a sitemap XML element.

        Args:
            root: XML root element
            namespace: XML namespace dictionary

        Returns:
            List of recipe URLs (collection and non-recipe pages are dropped)
        """
        urls = []
        url_elements = root.findall('.//ns:url', namespace)

        for url_elem in url_elements:
            loc = url_elem.find('ns:loc', namespace)
            if loc is not None and loc.text:
                url = loc.text
                if classify_hellofresh_url(url) == "recipe":
                    urls.append(url)

        logger.debug(f"Extracted {len(urls)} recipe URLs from {len(url_elements)} sitemap entries")
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

        Uses regex to find links under /recipes/, then keeps only those that
        point at a single recipe (see classify_hellofresh_url).

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

            # A listing page links to other listings as well as to recipes
            if classify_hellofresh_url(url) != "recipe":
                continue

            # Deduplicate URLs
            if url not in seen:
                seen.add(url)
                urls.append(url)

        return urls
