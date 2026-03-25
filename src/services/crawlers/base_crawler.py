"""
Base crawler utilities for recipe URL discovery.

Provides shared utilities for crawling recipe websites with rate limiting,
robots.txt compliance, and HTTP retry logic. Designed to be reusable across
multiple recipe site crawlers (HelloFresh, Kitchen Sanctuary, etc.).
"""

import time
import logging
from typing import Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logger = logging.getLogger(__name__)

# Polite User-Agent header for crawler identification
USER_AGENT = "FreshUp-Crawler/1.0 (+https://github.com/freshup/freshup)"


class RateLimiter:
    """
    Per-domain rate limiter to prevent overwhelming target servers.

    Enforces a minimum delay between requests to the same domain,
    with configurable delay per domain. Default is 2 seconds.
    """

    def __init__(self, default_delay: float = 2.0):
        """
        Initialize rate limiter.

        Args:
            default_delay: Default delay in seconds between requests (default: 2.0)
        """
        self.default_delay = default_delay
        self._last_request_time: dict[str, float] = {}
        self._domain_delays: dict[str, float] = {}

    def wait_if_needed(self, domain: str) -> None:
        """
        Wait if necessary to respect rate limiting for the given domain.

        Args:
            domain: Domain name to rate limit (e.g., "hellofresh.com")
        """
        now = time.time()
        last_request = self._last_request_time.get(domain)

        if last_request is not None:
            # Get domain-specific delay (from robots.txt) or use default
            delay = self._domain_delays.get(domain, self.default_delay)
            elapsed = now - last_request

            # Sleep if not enough time has passed since last request
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)

        # Update last request time for this domain
        self._last_request_time[domain] = time.time()

    def set_domain_delay(self, domain: str, delay: float) -> None:
        """
        Set a custom delay for a specific domain.

        Useful for respecting Crawl-delay directives from robots.txt.

        Args:
            domain: Domain name
            delay: Delay in seconds between requests
        """
        self._domain_delays[domain] = delay
        logger.info(f"Set rate limit for {domain}: {delay}s between requests")


class RobotsTxtParser:
    """
    Parser and cache for robots.txt files.

    Fetches and parses robots.txt for domains, caching results to avoid
    repeated requests. Respects Crawl-delay directives and Disallow rules.
    """

    def __init__(self, user_agent: str = USER_AGENT):
        """
        Initialize robots.txt parser.

        Args:
            user_agent: User agent string to use when checking robots.txt rules
        """
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def can_fetch(self, url: str) -> bool:
        """
        Check if the given URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if URL can be fetched, False if disallowed
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        # Get or create parser for this domain
        if domain not in self._parsers:
            self._fetch_robots_txt(domain, parsed.scheme)

        parser = self._parsers[domain]
        can_fetch = parser.can_fetch(self.user_agent, url)

        if not can_fetch:
            logger.warning(f"robots.txt disallows fetching: {url}")

        return can_fetch

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """
        Get the Crawl-delay directive from robots.txt for the given URL's domain.

        Args:
            url: URL to get crawl delay for

        Returns:
            Crawl delay in seconds, or None if not specified
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        if domain not in self._parsers:
            self._fetch_robots_txt(domain, parsed.scheme)

        parser = self._parsers[domain]
        crawl_delay = parser.crawl_delay(self.user_agent)

        if crawl_delay:
            logger.info(f"robots.txt Crawl-delay for {domain}: {crawl_delay}s")

        return crawl_delay

    def _fetch_robots_txt(self, domain: str, scheme: str = "https") -> None:
        """
        Fetch and parse robots.txt for the given domain.

        Args:
            domain: Domain name to fetch robots.txt for
            scheme: URL scheme (http or https)
        """
        robots_url = f"{scheme}://{domain}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            parser.read()
            logger.info(f"Successfully fetched robots.txt from {robots_url}")
        except Exception as e:
            # If robots.txt fetch fails, assume crawling is allowed
            logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}")
            logger.info(f"Assuming crawling is allowed for {domain}")

        self._parsers[domain] = parser


def create_http_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    timeout: int = 10
) -> requests.Session:
    """
    Create an HTTP session with retry logic.

    Configures exponential backoff for failed requests, retrying on:
    - Connection errors
    - Timeout errors
    - HTTP 500, 502, 503, 504 errors (server errors)

    Args:
        retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Backoff factor for exponential delay (default: 0.5)
                       Delay = {backoff_factor} * (2 ** (retry_number - 1))
        timeout: Default timeout in seconds (default: 10). Note: This parameter
                is for reference only. Timeout must be passed explicitly in each
                request call (e.g., session.get(url, timeout=timeout)).

    Returns:
        Configured requests.Session object

    Example:
        >>> session = create_http_session(retries=3, backoff_factor=0.5, timeout=10)
        >>> response = session.get("https://example.com", timeout=10)
    """
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],  # Only retry safe methods
    )

    # Mount adapter with retry strategy
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Set polite User-Agent
    session.headers.update({"User-Agent": USER_AGENT})

    logger.debug(f"Created HTTP session: retries={retries}, backoff={backoff_factor}, timeout={timeout}s")

    return session
