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
import recipe_scrapers
from recipe_scrapers._exceptions import WebsiteNotImplementedError

from src.schemas.scraper import ScrapedRecipeData
from src.db.models.recipe import SourceType


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
    try:
        parsed = urlparse(url)

        # Ensure scheme is http or https
        if parsed.scheme not in ('http', 'https'):
            raise ScraperError(f"Invalid URL scheme: {parsed.scheme}. Only http and https are allowed")

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

        # Block localhost variants by name
        if hostname in ('localhost', 'localhost.localdomain'):
            raise ScraperError("Access to localhost is not allowed")

        # Block common cloud metadata endpoints
        if hostname in ('169.254.169.254', 'metadata.google.internal', 'metadata.azure.com', 'metadata.aws.amazon.com'):
            raise ScraperError("Access to cloud metadata endpoints is not allowed")

        # Validate IP addresses using ipaddress module for comprehensive checking
        try:
            ip = ipaddress.ip_address(hostname)
            # Block private, loopback, link-local, multicast, and reserved IP addresses
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_multicast or ip.is_reserved or ip.is_unspecified):
                raise ScraperError("Access to private, loopback, link-local, or reserved IP addresses is not allowed")
        except ValueError:
            # hostname is not an IP address (it's a domain name), which is fine
            # Additional domain name validations could be added here if needed
            pass

    except ScraperError:
        raise  # Re-raise our validation errors
    except Exception as e:
        raise ScraperError(f"Invalid URL: {str(e)}")

    try:
        # Attempt to scrape the recipe
        scraper = recipe_scrapers.scrape_html(
            html=None,
            org_url=url,
            wild_mode=False  # Try site-specific scraper first
        )
    except WebsiteNotImplementedError:
        # Site not supported - try wild_mode (JSON-LD extraction)
        try:
            scraper = recipe_scrapers.scrape_html(
                html=None,
                org_url=url,
                wild_mode=True
            )
        except WebsiteNotImplementedError:
            raise UnsupportedSiteError(
                f"Site not supported by recipe-scrapers and wild_mode failed: {url}"
            )
        except Exception as e:
            raise ParseError(f"Failed to parse recipe in wild_mode: {str(e)}")
    except ConnectionError as e:
        raise NetworkError(f"Network request failed: {str(e)}")
    except TimeoutError as e:
        raise NetworkError(f"Request timed out: {str(e)}")
    except Exception as e:
        # Catch other exceptions from recipe-scrapers
        raise ScraperError(f"Failed to scrape recipe: {str(e)}")

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
        raise ParseError(f"Failed to extract recipe data: {str(e)}")
