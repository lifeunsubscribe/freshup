"""
Kitchen Sanctuary URL discovery crawler.

Discovers recipe URLs from Kitchen Sanctuary via WordPress sitemap.xml.
Includes rate limiting and robots.txt compliance.
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

# Kitchen Sanctuary base URL
KITCHEN_SANCTUARY_BASE_URL = "https://www.kitchensanctuary.com"


class KitchenSanctuaryCrawler:
    """
    Crawler for discovering Kitchen Sanctuary recipe URLs.

    Uses WordPress sitemap.xml parsing to extract recipe URLs.
    WordPress typically provides sitemap index at /sitemap.xml or /wp-sitemap.xml,
    which links to post-specific sitemaps containing recipe URLs.

    Features:
    - Rate limiting (2s default, respects robots.txt Crawl-delay)
    - robots.txt compliance
    - HTTP retry logic with exponential backoff
    - Filters sitemap entries to recipe pages only (excludes category/tag/about pages)
    """

    def __init__(
        self,
        base_url: str = KITCHEN_SANCTUARY_BASE_URL,
        rate_limit_delay: float = 2.0,
    ):
        """
        Initialize Kitchen Sanctuary crawler.

        Args:
            base_url: Base URL for Kitchen Sanctuary (default: https://www.kitchensanctuary.com)
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

        # Initialize utilities from base_crawler
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
        Discover recipe URLs from Kitchen Sanctuary.

        Parses WordPress sitemap.xml to extract recipe URLs, filtering out
        non-recipe pages (category, tag, about, contact, etc.).

        Args:
            max_pages: Maximum number of sitemap pages to crawl. None means no limit.
                      Used primarily for testing.

        Returns:
            List of discovered recipe URLs

        Raises:
            CrawlerNetworkError: If network requests fail (connection, timeout, HTTP errors)
            CrawlerParseError: If parsing fails (malformed XML, invalid structure)
            CrawlerError: If unexpected errors occur

        Example:
            >>> crawler = KitchenSanctuaryCrawler()
            >>> urls = crawler.discover_recipe_urls(max_pages=5)
            >>> print(f"Discovered {len(urls)} recipe URLs")
        """
        logger.info("Starting Kitchen Sanctuary recipe URL discovery")

        try:
            urls = self._discover_from_sitemap(max_pages=max_pages)
            logger.info(f"Discovered {len(urls)} URLs from sitemap.xml")
            return urls
        except (CrawlerNetworkError, CrawlerParseError):
            # Re-raise crawler exceptions as-is (already wrapped)
            raise
        except requests.exceptions.RequestException as e:
            # Wrap actual network errors at the public API boundary
            # This catches all requests exceptions: ConnectionError, Timeout, HTTPError, etc.
            # These are genuine network/transport issues, not programming bugs
            logger.exception(f"Sitemap strategy failed with network error: {e}")
            raise CrawlerNetworkError(f"Network error during URL discovery: {e}") from e
        except (ssl.SSLError, ssl.CertificateError) as e:
            # Wrap SSL/TLS errors at the public API boundary
            logger.exception(f"Sitemap strategy failed with SSL error: {e}")
            raise CrawlerNetworkError(f"SSL error during URL discovery: {e}") from e
        except (ValueError, UnicodeDecodeError) as e:
            # Wrap parsing/encoding errors at the public API boundary
            logger.exception(f"Sitemap strategy failed with {type(e).__name__}: {e}")
            raise CrawlerParseError(f"Parse error during URL discovery: {e}") from e
        except (OSError, IOError) as e:
            # Catch I/O errors specifically - these are external errors, not programming bugs
            logger.exception(f"Sitemap strategy failed with I/O error: {e}")
            raise CrawlerError(f"I/O error during URL discovery: {e}") from e

    def _discover_from_sitemap(self, max_pages: Optional[int] = None) -> list[str]:
        """
        Discover recipe URLs from WordPress sitemap.xml.

        WordPress typically provides a sitemap index that links to separate
        sitemaps for posts, pages, categories, etc. This method fetches the
        sitemap index and extracts URLs from post sitemaps, filtering to
        recipe pages only.

        Args:
            max_pages: Maximum number of sitemap pages to crawl (None = no limit)

        Returns:
            List of recipe URLs found in sitemap

        Raises:
            Exception: If sitemap fetch or parsing fails
        """
        # Try common WordPress sitemap locations
        sitemap_urls = [
            urljoin(self.base_url, "/sitemap.xml"),
            urljoin(self.base_url, "/wp-sitemap.xml"),
        ]

        recipe_urls = []

        for sitemap_url in sitemap_urls:
            try:
                logger.info(f"Trying sitemap at {sitemap_url}")
                urls = self._fetch_and_parse_sitemap(sitemap_url, max_pages=max_pages)
                if urls:
                    recipe_urls.extend(urls)
                    break  # Successfully found sitemap, stop trying other locations
            except (requests.exceptions.RequestException, ssl.SSLError, ssl.CertificateError,
                    ValueError, UnicodeDecodeError, OSError, IOError) as e:
                # Try next sitemap location if this one fails with external errors
                # This is a fallback/retry pattern for robustness - external errors only
                # Programming errors (AttributeError, TypeError, KeyError) will propagate
                logger.warning(f"Failed to fetch sitemap from {sitemap_url}: {e}")
                continue

        if not recipe_urls:
            raise Exception("Failed to fetch sitemap from any known location")

        # Remove duplicates
        recipe_urls = list(set(recipe_urls))
        return recipe_urls

    def _fetch_and_parse_sitemap(
        self, sitemap_url: str, max_pages: Optional[int] = None
    ) -> list[str]:
        """
        Fetch and parse a sitemap XML file.

        Handles both sitemap indexes (that link to other sitemaps) and
        regular sitemaps (that contain URL entries).

        Args:
            sitemap_url: URL of the sitemap to fetch
            max_pages: Maximum number of sitemap pages to crawl

        Returns:
            List of recipe URLs extracted from sitemap

        Raises:
            Exception: If fetch or parsing fails
        """
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

        # Define sitemap XML namespace for parsing
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Check if this is a sitemap index (references other sitemaps)
        sitemap_elements = root.findall('.//ns:sitemap', namespace)

        recipe_urls = []

        if sitemap_elements:
            # This is a sitemap index, fetch post sitemaps
            # WordPress typically has sitemaps named like: wp-sitemap-posts-post-1.xml
            pages_fetched = 0

            for sitemap_elem in sitemap_elements:
                # Stop if we've reached max_pages limit
                if max_pages is not None and pages_fetched >= max_pages:
                    logger.info(f"Reached max_pages limit ({max_pages})")
                    break

                loc = sitemap_elem.find('ns:loc', namespace)
                if loc is not None and loc.text:
                    sub_sitemap_url = loc.text

                    # Only fetch post sitemaps (skip pages, categories, tags)
                    # WordPress post sitemaps typically contain 'post' in the filename
                    if 'post' in sub_sitemap_url.lower():
                        logger.info(f"Found post sitemap: {sub_sitemap_url}")

                        try:
                            # Recursively fetch and parse sub-sitemap
                            if self.robots_parser.can_fetch(sub_sitemap_url):
                                self.rate_limiter.wait_if_needed(self.domain)
                                sub_response = self.session.get(sub_sitemap_url, timeout=10)
                                sub_response.raise_for_status()

                                # Parse sub-sitemap
                                try:
                                    if not sub_response.content:
                                        raise ValueError(f"Sub-sitemap response is empty: {sub_sitemap_url}")
                                    sub_root = ET.fromstring(sub_response.content)
                                except ET.ParseError as e:
                                    raise ValueError(f"Failed to parse sub-sitemap XML from {sub_sitemap_url}: {e}")
                                except (UnicodeDecodeError, UnicodeError) as e:
                                    # Catch encoding errors specifically - these are external data issues
                                    raise ValueError(f"Encoding error processing sub-sitemap from {sub_sitemap_url}: {e}")

                                # Extract URLs from sub-sitemap
                                urls = self._extract_recipe_urls_from_sitemap(sub_root, namespace)
                                recipe_urls.extend(urls)
                                pages_fetched += 1
                            else:
                                logger.warning(f"robots.txt disallows {sub_sitemap_url}")
                        except (requests.exceptions.RequestException, ssl.SSLError, ssl.CertificateError,
                                ValueError, UnicodeDecodeError, OSError, IOError) as e:
                            # Continue processing other sub-sitemaps if one fails with external errors
                            # Robustness pattern for partial failures - external errors only
                            # Programming errors (AttributeError, TypeError, KeyError) will propagate
                            logger.warning(f"Failed to fetch sub-sitemap {sub_sitemap_url}: {e}")
                            continue
        else:
            # This is a regular sitemap, extract URLs directly
            recipe_urls = self._extract_recipe_urls_from_sitemap(root, namespace)

        return recipe_urls

    def _extract_recipe_urls_from_sitemap(self, root: Element, namespace: dict) -> list[str]:
        """
        Extract recipe URLs from a sitemap XML element.

        Filters URLs to include only recipe pages, excluding WordPress
        administrative/category/tag pages.

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

                # Filter to recipe pages only
                if self._is_recipe_url(url):
                    urls.append(url)

        logger.debug(f"Extracted {len(urls)} recipe URLs from sitemap")
        return urls

    def _is_recipe_url(self, url: str) -> bool:
        """
        Determine if a URL is a recipe page.

        Filters out WordPress administrative pages, category/tag pages,
        and non-recipe content pages.

        Args:
            url: URL to check

        Returns:
            True if URL is a recipe page, False otherwise
        """
        url_lower = url.lower()

        # Exclude common non-recipe WordPress pages
        exclude_patterns = [
            '/category/',
            '/tag/',
            '/page/',
            '/author/',
            '/about',
            '/contact',
            '/privacy',
            '/terms',
            '/disclaimer',
            '/sitemap',
            '/feed',
            '/wp-content/',
            '/wp-admin/',
            '/wp-includes/',
            '/wp-json/',
            '/xmlrpc.php',
            '/robots.txt',
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Ensure URL is from the correct domain
        if self.domain not in url_lower:
            return False

        # Accept URLs that look like recipe posts
        # WordPress recipe sites typically have recipes at root level or /recipes/ path
        # Recipe URLs typically have a path like /recipe-name/ or /recipes/recipe-name/
        parsed = urlparse(url)
        path = parsed.path

        # Exclude homepage and pagination pages
        if path == '/' or path == '' or '/page/' in path:
            return False

        # Accept anything else that looks like a content page
        # (WordPress recipe posts typically have meaningful slugs)
        return True
