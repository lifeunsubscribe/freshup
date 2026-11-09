"""
Recipe scraping service for FreshUp.

Provides a thin wrapper around the recipe-scrapers library to extract
structured recipe data from external URLs. Supports 624+ recipe sites
through the recipe-scrapers library (MIT licensed).
"""

from typing import Optional
from urllib.parse import urlparse
import re
import ipaddress
import socket
import logging
import requests
import requests.certs
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError

from src.schemas.scraper import ScrapedRecipeData
from src.db.models.recipe import SourceType
from src.config import get_settings
from src.services.crawlers.base_crawler import USER_AGENT

logger = logging.getLogger(__name__)


# Custom exceptions for scraping errors
class ScraperError(Exception):
    """Base exception for recipe scraping errors."""
    pass


class NetworkError(ScraperError):
    """Raised when network request fails."""
    pass


class UnsupportedSiteError(ScraperError):
    """Raised when site is not supported even with wild_mode."""
    pass


class ParseError(ScraperError):
    """Raised when recipe data cannot be parsed."""
    pass


# Domain to source_type mapping
DOMAIN_TO_SOURCE_TYPE = {
    "hellofresh.com": SourceType.hellofresh_web.value,
    "www.hellofresh.com": SourceType.hellofresh_web.value,
    "kitchensanctuary.com": SourceType.kitchen_sanctuary.value,
    "www.kitchensanctuary.com": SourceType.kitchen_sanctuary.value,
}


class _PinnedHostnameAdapter(HTTPAdapter):
    """
    Lets a request connect to a pre-validated IP while TLS is done for the real hostname.

    scrape_recipe() resolves the hostname once, checks the address is public, and
    then connects to that exact address so a second DNS answer cannot redirect the
    request to an internal host (DNS rebinding). Requesting "https://<ip>/..." on
    its own breaks HTTPS, though: no SNI is sent and the certificate is checked
    against the IP, so every real site fails the handshake. This adapter sends the
    hostname as SNI and verifies the certificate against it instead.
    """

    def __init__(self, hostname: str, **kwargs):
        self._hostname = hostname
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        # A private SSL context: urllib3 switches off the context's own hostname
        # check when assert_hostname is set (it does the comparison itself), and
        # requests would otherwise hand it the context every session shares.
        context = create_urllib3_context()
        context.load_verify_locations(cafile=requests.certs.where())
        pool_kwargs["ssl_context"] = context
        pool_kwargs["server_hostname"] = self._hostname
        pool_kwargs["assert_hostname"] = self._hostname
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def _http_get(url: str, *, tls_hostname: Optional[str] = None, **kwargs) -> requests.Response:
    """
    GET a URL, optionally pinning TLS to a hostname that differs from the URL's host.

    Args:
        url: URL to request. May address the server by IP.
        tls_hostname: When the URL addresses the server by IP, the hostname to use
            for SNI and certificate verification. None means standard behaviour.
        **kwargs: Passed through to requests (timeout, headers, allow_redirects, verify).

    Returns:
        The response
    """
    with requests.Session() as session:
        if tls_hostname:
            session.mount("https://", _PinnedHostnameAdapter(tls_hostname))
        return session.get(url, **kwargs)


# Upper bound on tags taken from a page; some sites stuff dozens of SEO keywords in
MAX_SCRAPED_TAGS = 12


def _clean_title(title: Optional[str], scraper) -> Optional[str]:
    """
    Trim a tagline that the page's structured data has glued onto the recipe name.

    HelloFresh publishes "Peruvian-Style Lomo Saltado Enjoy a multi-dish culinary
    tour of a new destination!" as the name. The page's own <h1> holds just the
    name, so when the <h1> is how the scraped title begins, the <h1> wins.

    Args:
        title: Title as extracted by recipe-scrapers
        scraper: The recipe-scrapers object for the page

    Returns:
        The shorter heading when it is a leading part of the title, else the title unchanged
    """
    if not title:
        return title
    try:
        h1 = scraper.soup.find("h1")
        heading = h1.get_text(" ", strip=True) if h1 else ""
        if not isinstance(heading, str):
            return title
        heading = " ".join(heading.split())
    except Exception:
        return title

    if not heading or len(heading) >= len(title):
        return title
    # Must be a leading run of whole words, not a coincidental shared prefix
    if title.lower().startswith(heading.lower()) and title[len(heading)].isspace():
        return heading
    return title


def _extract_tags(scraper) -> list[str]:
    """
    Build tags from the category, cuisine and keywords a page declares.

    Args:
        scraper: The recipe-scrapers object for the page

    Returns:
        Lowercased, de-duplicated tags in the order found (at most MAX_SCRAPED_TAGS)
    """
    tags: list[str] = []
    for field in ("category", "cuisine", "keywords"):
        try:
            value = getattr(scraper, field)()
        except Exception:
            continue  # Most pages declare only some of these

        if isinstance(value, str):
            parts = value.split(",")
        elif isinstance(value, (list, tuple)):
            parts = value
        else:
            continue

        for part in parts:
            if not isinstance(part, str):
                continue
            tag = " ".join(part.split()).lower()
            if tag and tag not in tags:
                tags.append(tag)

    return tags[:MAX_SCRAPED_TAGS]


def _reconcile_hellofresh_times(
    scraper, prep_time: Optional[int], cook_time: Optional[int]
) -> tuple[Optional[int], Optional[int]]:
    """
    Correct HelloFresh prep and cook times so they add up to the real total.

    HelloFresh's page data labels the total time "prepTime" and the hands-on time
    "totalTime". recipe-scrapers reports those as prep and cook, which sums to more
    than the meal takes (45 + 10 for a 45 minute recipe). The page's schema.org
    totalTime is the true total, so when "prep" equals it, the other number is the
    hands-on prep and the rest is cooking.

    Args:
        scraper: The recipe-scrapers object for the page
        prep_time: Prep minutes as extracted
        cook_time: Cook minutes as extracted

    Returns:
        (prep_minutes, cook_minutes), corrected when the pattern above is recognised
    """
    try:
        declared_total = scraper.schema.total_time()
    except Exception:
        return prep_time, cook_time

    if not all(isinstance(value, int) for value in (declared_total, prep_time, cook_time)):
        return prep_time, cook_time

    if prep_time == declared_total and 0 < cook_time < declared_total:
        return cook_time, declared_total - cook_time
    return prep_time, cook_time


def _detect_source_type(url: str) -> str:
    """
    Auto-detect source_type from URL domain.

    Args:
        url: Recipe URL

    Returns:
        Source type string (hellofresh_web, kitchen_sanctuary, or url_import)
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check for exact domain match
        if domain in DOMAIN_TO_SOURCE_TYPE:
            return DOMAIN_TO_SOURCE_TYPE[domain]

        # Default to url_import for unknown sites
        return SourceType.url_import.value
    except Exception:
        # If URL parsing fails, default to url_import
        return SourceType.url_import.value


def scrape_recipe(url: str) -> ScrapedRecipeData:
    """
    Scrape recipe data from a URL.

    Uses the recipe-scrapers library to extract structured recipe data.
    Automatically detects source_type from the URL domain. Falls back to
    wild_mode for unsupported sites (attempts JSON-LD extraction).

    Args:
        url: Recipe URL to scrape

    Returns:
        ScrapedRecipeData with normalized recipe information

    Raises:
        NetworkError: If HTTP request fails
        UnsupportedSiteError: If site is not supported and wild_mode fails
        ParseError: If recipe data cannot be parsed
        ScraperError: For other scraping errors

    Example:
        >>> data = scrape_recipe("https://www.hellofresh.com/recipes/...")
        >>> print(data.title)
        >>> print(data.source_type)  # "hellofresh_web"
    """
    if not url or not url.strip():
        raise ScraperError("URL cannot be empty")

    url = url.strip()

    # Validate URL to prevent SSRF attacks
    # Store the validated IP to use for the request to prevent DNS rebinding TOCTOU
    validated_ip = None
    original_hostname = None

    try:
        parsed = urlparse(url)

        # Ensure scheme is http or https
        if parsed.scheme not in ('http', 'https'):
            logger.warning(f"Invalid URL scheme rejected: {parsed.scheme}")
            raise ScraperError("The provided URL is not accessible for recipe import. Only HTTP and HTTPS URLs are supported.")

        # Ensure hostname is present
        if not parsed.netloc:
            raise ScraperError("Invalid URL: missing hostname")

        # Block private/internal IP addresses and localhost
        hostname = parsed.netloc.lower()

        # Handle IPv6 addresses with brackets (e.g., [::1]:8080 or [::1])
        if '[' in hostname:
            # Extract IPv6 address from brackets
            start = hostname.index('[')
            end = hostname.index(']')
            hostname = hostname[start+1:end]
        else:
            # For IPv4 or domain names, remove port if present
            hostname = hostname.split(':')[0]

        # Store original hostname for Host header
        original_hostname = hostname

        # Block localhost variants by name
        if hostname in ('localhost', 'localhost.localdomain'):
            logger.warning(f"SSRF protection: Blocked localhost hostname: {hostname}")
            raise ScraperError("The provided URL is not allowed. Please use a publicly accessible recipe website URL.")

        # Block common cloud metadata endpoints
        if hostname in ('169.254.169.254', 'metadata.google.internal', 'metadata.azure.com', 'metadata.aws.amazon.com'):
            logger.warning(f"SSRF protection: Blocked cloud metadata endpoint: {hostname}")
            raise ScraperError("The provided URL is not allowed. Please use a publicly accessible recipe website URL.")

        # Function to check if an IP address is safe
        def _is_safe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
            """Check if an IP address is safe (not private, loopback, link-local, etc.)."""
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or
                       ip.is_multicast or ip.is_reserved or ip.is_unspecified)

        # Validate IP addresses using ipaddress module for comprehensive checking
        try:
            ip = ipaddress.ip_address(hostname)
            # Block private, loopback, link-local, multicast, and reserved IP addresses
            if not _is_safe_ip(ip):
                logger.warning(f"SSRF protection: Blocked unsafe IP address: {ip}")
                raise ScraperError("The provided URL is not allowed. Please use a publicly accessible recipe website URL.")
            # Store the validated IP for use in the request
            validated_ip = hostname
        except ValueError:
            # hostname is a domain name, not an IP address
            # Resolve DNS to prevent DNS rebinding attacks
            try:
                # Get all IP addresses the hostname resolves to
                addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)

                # Check each resolved IP address and store the first safe one
                for info in addr_info:
                    resolved_ip_str = info[4][0]
                    # Remove IPv6 scope ID if present (e.g., "fe80::1%eth0" -> "fe80::1")
                    if '%' in resolved_ip_str:
                        resolved_ip_str = resolved_ip_str.split('%')[0]

                    try:
                        resolved_ip = ipaddress.ip_address(resolved_ip_str)
                        if not _is_safe_ip(resolved_ip):
                            # Log full technical details for debugging (includes IP address)
                            logger.warning(f"SSRF protection: Domain {hostname} resolves to blocked IP: {resolved_ip_str}")
                            # Raise sanitized user-facing message (no IP disclosure)
                            raise ScraperError("The provided URL is not allowed. Please use a publicly accessible recipe website URL.")
                        # Store the first validated IP for use in the request
                        if validated_ip is None:
                            validated_ip = resolved_ip_str
                    except ValueError:
                        # Should not happen with valid getaddrinfo results, but be defensive
                        # Log full technical details for debugging (includes IP address)
                        logger.error(f"Invalid IP address from DNS for {hostname}: {resolved_ip_str}")
                        # Raise sanitized user-facing message (no DNS internals)
                        raise ScraperError("The provided URL could not be resolved. Please verify the URL and try again.")

            except socket.gaierror as e:
                # DNS resolution failed - this is acceptable for valid public domains that don't exist
                # or in test environments. The actual scraper will fail later if the domain is invalid.
                # We only care about blocking domains that DO resolve to private IPs.
                pass
            except socket.timeout:
                # DNS timeout - allow to proceed, scraper will handle timeout errors
                pass

    except ScraperError:
        raise  # Re-raise our validation errors (already sanitized above)
    except Exception as e:
        # Log full technical details for debugging
        logger.error(f"Unexpected error during URL validation: {type(e).__name__}: {str(e)}")
        # Raise sanitized user-facing message (no exception details)
        raise ScraperError("The provided URL is invalid. Please verify the URL format and try again.")

    # Fetch HTML with timeout configuration to prevent indefinite hangs
    # The recipe_scrapers library doesn't handle HTTP timeouts directly, so we
    # fetch the HTML ourselves using requests with a configurable timeout
    settings = get_settings()
    timeout = settings.scraper_request_timeout

    try:
        # Use the validated IP address if we have one to prevent DNS rebinding TOCTOU
        # If we don't have a validated IP (e.g., DNS lookup failed), use the original URL
        if validated_ip and original_hostname:
            # Build URL with validated IP address
            parsed = urlparse(url)
            # Handle IPv6 addresses with brackets
            if ':' in validated_ip and not validated_ip.startswith('['):
                ip_with_brackets = f'[{validated_ip}]'
            else:
                ip_with_brackets = validated_ip

            # Reconstruct URL with validated IP, preserving port if present
            if parsed.port:
                request_url = f"{parsed.scheme}://{ip_with_brackets}:{parsed.port}{parsed.path}"
                if parsed.query:
                    request_url += f"?{parsed.query}"
            else:
                request_url = f"{parsed.scheme}://{ip_with_brackets}{parsed.path}"
                if parsed.query:
                    request_url += f"?{parsed.query}"

            # Set Host header to preserve virtual hosting and User-Agent for reliability
            headers = {'Host': original_hostname, 'User-Agent': USER_AGENT}
            # We connect to the IP, but TLS must still be negotiated for the name:
            # only pin when the URL actually named a host (not a literal IP).
            tls_hostname = original_hostname if validated_ip != original_hostname else None
        else:
            # Fallback to original URL if no validated IP
            request_url = url
            headers = {'User-Agent': USER_AGENT}
            tls_hostname = None

        # Fetch the HTML content with timeout and disabled redirects
        # Redirects are disabled to prevent redirect-based SSRF bypasses
        response = _http_get(
            request_url,
            tls_hostname=tls_hostname,
            timeout=timeout,
            headers=headers,
            allow_redirects=False,
            verify=True,
        )

        # Check for redirect responses (3xx status codes)
        # Since allow_redirects=False, we need to explicitly handle these
        if 300 <= response.status_code < 400:
            raise NetworkError(
                f"URL returned a redirect (HTTP {response.status_code}). "
                f"Redirects are not followed for security reasons. "
                f"Please use the final destination URL directly."
            )

        response.raise_for_status()  # Raise exception for 4xx/5xx status codes
        html_content = response.content
    except requests.exceptions.Timeout as e:
        # Log full technical details for debugging
        logger.warning(f"Request timeout for URL (timeout={timeout}s): {str(e)}")
        # Raise sanitized user-facing message (no timeout value, no internal details)
        raise NetworkError("Unable to connect to the recipe source. The request timed out. Please try again later.")
    except requests.exceptions.ConnectionError as e:
        # Log full technical details for debugging (may include IP, port, DNS info)
        logger.warning(f"Connection error for URL: {str(e)}")
        # Raise sanitized user-facing message (no network topology info)
        raise NetworkError("Unable to connect to the recipe source. Please verify the URL and try again.")
    except requests.exceptions.RequestException as e:
        # Catch other requests-related errors (like HTTPError from raise_for_status)
        # Log full technical details for debugging (may include server versions, status codes)
        logger.warning(f"HTTP request error for URL: {str(e)}")
        # Raise sanitized user-facing message (no HTTP details, no server info)
        raise NetworkError("Unable to retrieve the recipe page. Please verify the URL is accessible and try again.")

    try:
        # Attempt to scrape the recipe
        scraper = recipe_scrapers.scrape_html(
            html=html_content,
            org_url=url,
            wild_mode=False  # Try site-specific scraper first
        )
    except WebsiteNotImplementedError:
        # Site not supported - try wild_mode (JSON-LD extraction)
        try:
            scraper = recipe_scrapers.scrape_html(
                html=html_content,
                org_url=url,
                wild_mode=True
            )
        except WebsiteNotImplementedError:
            raise UnsupportedSiteError(
                f"Site not supported by recipe-scrapers and wild_mode failed: {url}"
            )
        except Exception as e:
            # Log full technical details for debugging (may include parser internals)
            logger.warning(f"Failed to parse recipe in wild_mode: {type(e).__name__}: {str(e)}")
            # Raise sanitized user-facing message (no parser internals)
            raise ParseError("Unable to extract recipe information from this page. The page format may not be supported.")
    except Exception as e:
        # Catch other exceptions from recipe-scrapers
        # Log full technical details for debugging (may include library internals)
        logger.error(f"Unexpected scraper error: {type(e).__name__}: {str(e)}")
        # Raise sanitized user-facing message (no library internals)
        raise ScraperError("Unable to process the recipe page. Please try a different URL.")

    # Extract data from scraper with safe fallbacks
    try:
        # Auto-detect source type from URL
        source_type = _detect_source_type(url)

        # Extract ingredients (list of raw strings)
        ingredients = []
        try:
            ingredients = scraper.ingredients() or []
        except Exception:
            pass  # Some sites may not have ingredients

        # Extract instructions (list of strings)
        instructions = []
        try:
            instructions_raw = scraper.instructions()
            if instructions_raw:
                # Some scrapers return a single string with newlines
                if isinstance(instructions_raw, str):
                    instructions = [s.strip() for s in instructions_raw.split('\n') if s.strip()]
                else:
                    instructions = [str(s).strip() for s in instructions_raw if s]
        except Exception:
            pass

        # Extract time values (in minutes)
        prep_time = None
        cook_time = None
        total_time = None
        try:
            prep_time = scraper.prep_time()
        except Exception:
            pass
        try:
            cook_time = scraper.cook_time()
        except Exception:
            pass
        try:
            total_time = scraper.total_time()
        except Exception:
            pass

        # Extract servings/yields
        servings = None
        try:
            yields_raw = scraper.yields()
            # yields() can return strings like "4 servings" or numbers
            if yields_raw is not None:
                if isinstance(yields_raw, (int, float)):
                    servings = int(yields_raw)
                elif isinstance(yields_raw, str):
                    # Try to extract number from string like "4 servings"
                    match = re.search(r'\d+', yields_raw)
                    if match:
                        servings = int(match.group())
        except Exception:
            pass

        # Extract nutrients (dictionary)
        nutrients = None
        try:
            nutrients_raw = scraper.nutrients()
            if nutrients_raw:
                nutrients = nutrients_raw
        except Exception:
            pass

        # Extract title
        title = None
        try:
            title = scraper.title()
        except Exception:
            pass
        title = _clean_title(title, scraper)

        if source_type == SourceType.hellofresh_web.value:
            prep_time, cook_time = _reconcile_hellofresh_times(scraper, prep_time, cook_time)
            if prep_time is not None and cook_time is not None:
                total_time = prep_time + cook_time

        # Extract image URL
        image_url = None
        try:
            image_url = scraper.image()
        except Exception:
            pass

        # Extract author
        author = None
        try:
            author = scraper.author()
        except Exception:
            pass

        # Extract site name
        site_name = None
        try:
            site_name = scraper.site_name()
        except Exception:
            pass

        # Build and return the normalized data model
        return ScrapedRecipeData(
            source_url=url,
            source_type=source_type,
            title=title,
            image_url=image_url,
            prep_time_minutes=prep_time,
            cook_time_minutes=cook_time,
            total_time_minutes=total_time,
            servings=servings,
            ingredients=ingredients,
            instructions=instructions,
            tags=_extract_tags(scraper),
            nutrients=nutrients,
            author=author,
            site_name=site_name,
        )

    except Exception as e:
        # If data extraction fails, raise ParseError
        # Log full technical details for debugging (may include extraction logic)
        logger.error(f"Failed to extract recipe data: {type(e).__name__}: {str(e)}")
        # Raise sanitized user-facing message (no extraction details)
        raise ParseError("Unable to extract complete recipe information from this page. Some data may be missing or in an unexpected format.")
