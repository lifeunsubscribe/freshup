"""
Custom exception hierarchy for recipe URL crawlers.

Provides abstraction over HTTP library exceptions (requests.exceptions)
to prevent leaky abstractions where external library types propagate
to higher layers of the application.
"""


class CrawlerError(Exception):
    """
    Base exception for all crawler-related errors.

    Use this as the catch-all when handling crawler operations,
    or catch specific subclasses for finer-grained error handling.
    """
    pass


class CrawlerNetworkError(CrawlerError):
    """
    Raised when network requests fail during URL discovery.

    Wraps underlying HTTP library exceptions (requests.exceptions.RequestException)
    to prevent leaking implementation details to consumers. This includes:
    - Connection failures (DNS, TCP, SSL)
    - Timeouts (connect, read)
    - HTTP errors (4xx, 5xx)
    - Redirect limits exceeded
    """
    pass


class CrawlerParseError(CrawlerError):
    """
    Raised when parsing fails during URL discovery.

    This includes:
    - Malformed XML/HTML that cannot be parsed
    - Invalid sitemap structure
    - Missing required elements in expected format
    - Encoding issues
    """
    pass
