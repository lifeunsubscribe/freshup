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
            raise ScraperError("The provided URL is not accessible for recipe import")

        # Block common cloud metadata endpoints
        if hostname in ('169.254.169.254', 'metadata.google.internal', 'metadata.azure.com', 'metadata.aws.amazon.com'):
            logger.warning(f"SSRF protection: Blocked cloud metadata endpoint: {hostname}")
            raise ScraperError("The provided URL is not accessible for recipe import")

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
                raise ScraperError("The provided URL is not accessible for recipe import")
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
                            raise ScraperError("The provided URL is not accessible for recipe import.")
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
        else:
            # Fallback to original URL if no validated IP
            request_url = url
            headers = {'User-Agent': USER_AGENT}

        # Fetch the HTML content with timeout and disabled redirects
        # Redirects are disabled to prevent redirect-based SSRF bypasses
        response = requests.get(request_url, timeout=timeout, headers=headers, allow_redirects=False, verify=True)

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
            if yields_raw:
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
            tags=[],  # recipe-scrapers doesn't typically extract tags
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
