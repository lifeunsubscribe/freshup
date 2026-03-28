"""
Scraper API endpoints for FreshUp.

Provides endpoints for importing recipes from external URLs, discovering recipes
from supported sources (HelloFresh, Kitchen Sanctuary), and viewing import statistics.

Authorization:
- Single URL import: Any authenticated user
- Batch operations: Coordinator only
- Discovery operations: Coordinator only
- Status: Any authenticated user

Rate Limiting (API layer - abuse prevention):
- /import-url: 20 requests/minute per IP
- /import-batch: 5 requests/minute per IP
- /discover/{source}: 5 requests/minute per IP
- /discover-and-import/{source}: 3 requests/minute per IP
- /status: No rate limiting (read-only, cheap query)

Note: Service layer has separate polite delays (1 second between external requests)
for crawler etiquette, not abuse prevention.
"""

import logging
from typing import Literal
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.database import get_db
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.middleware.auth import get_current_user
from src.middleware.rate_limit import limiter
from src.services.import_service import import_recipe_from_url, import_batch
from src.services.crawlers.hellofresh_crawler import HelloFreshCrawler
from src.services.crawlers.kitchen_sanctuary_crawler import KitchenSanctuaryCrawler
from src.schemas.scraper import (
    ImportUrlRequest,
    ImportBatchRequest,
    DiscoverAndImportRequest,
    DiscoveryResponse,
    StatusResponse,
    SourceStats,
)
from src.schemas.import_service import ImportResult, BatchImportResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["scraper"])


def validate_domain(url: str, allowed_domains: list[str]) -> bool:
    """
    Validate that a URL's hostname is from an allowed domain.

    Uses proper domain suffix matching to prevent SSRF attacks via
    subdomain tricks like "evil.com/hellofresh.com" or "hellofresh.com.evil.com".

    Args:
        url: URL to validate
        allowed_domains: List of allowed domain suffixes (e.g., ["hellofresh.com"])

    Returns:
        True if the URL's hostname matches an allowed domain, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Validate URL scheme (only allow http and https)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False
        hostname_lower = hostname.lower()

        # Check if hostname exactly matches or is a subdomain of an allowed domain
        for domain in allowed_domains:
            domain_lower = domain.lower()
            if hostname_lower == domain_lower or hostname_lower.endswith(f".{domain_lower}"):
                return True
        return False
    except Exception:
        return False


def require_coordinator(user: User) -> None:
    """
    Verify that the user has coordinator role.

    Args:
        user: Authenticated user

    Raises:
        HTTPException(403): If user is not a coordinator
    """
    if user.role != UserRole.coordinator.value:
        logger.warning(f"Access denied: User {user.id} attempted coordinator-only operation")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Coordinator role required for this operation"
        )


@router.post("/import-url", response_model=ImportResult, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def import_single_url(
    payload: ImportUrlRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import a recipe from a single URL.

    Any authenticated user can import recipes. The recipe becomes globally
    readable (system-imported, created_by=None).

    Rate limited to 20 requests per minute per IP address to prevent abuse.

    Args:
        payload: Request body containing the URL to import
        request: FastAPI request object (required by slowapi for rate limiting)
        current_user: Authenticated user (injected by get_current_user)
        db: Database session

    Returns:
        ImportResult: Result of the import operation (success/duplicate/error)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If URL is invalid or import fails
        HTTPException(429): If rate limit is exceeded
    """
    logger.info(f"User {current_user.id} importing recipe from URL")

    # Validate URL is from a supported domain
    allowed_domains = ["hellofresh.com", "kitchensanctuary.com"]
    if not validate_domain(payload.url, allowed_domains):
        logger.warning(f"User {current_user.id} attempted to import from unsupported domain: {payload.url}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL must be from a supported domain: {', '.join(allowed_domains)}"
        )

    try:
        result = import_recipe_from_url(payload.url, db)
        return result
    except Exception as e:
        logger.error(f"Unexpected error during import for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/import-batch", response_model=BatchImportResult, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def import_batch_urls(
    payload: ImportBatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import recipes from multiple URLs (batch operation).

    Coordinator-only endpoint. Processes URLs sequentially with rate limiting
    (1 second delay between requests by default).

    Rate limited to 5 requests per minute per IP address to prevent abuse.

    Args:
        payload: Request body containing list of URLs to import
        request: FastAPI request object (required by slowapi for rate limiting)
        current_user: Authenticated user (must be coordinator)
        db: Database session

    Returns:
        BatchImportResult: Aggregate statistics and individual results

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If user is not a coordinator
        HTTPException(429): If rate limit is exceeded
    """
    require_coordinator(current_user)

    logger.info(f"Coordinator {current_user.id} importing batch of {len(payload.urls)} URLs")

    # Validate all URLs are from supported domains
    allowed_domains = ["hellofresh.com", "kitchensanctuary.com"]
    invalid_urls = [url for url in payload.urls if not validate_domain(url, allowed_domains)]
    if invalid_urls:
        logger.warning(f"Coordinator {current_user.id} attempted batch import with {len(invalid_urls)} invalid URLs")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All URLs must be from supported domains: {', '.join(allowed_domains)}. Found {len(invalid_urls)} invalid URL(s)."
        )

    try:
        result = import_batch(payload.urls, db, delay_seconds=1.0)
        logger.info(
            f"Batch import complete: {result.imported} imported, "
            f"{result.duplicates} duplicates, {result.errors} errors"
        )
        return result
    except Exception as e:
        logger.error(f"Unexpected error during batch import: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch import failed: {str(e)}"
        )


@router.post("/discover/{source}", response_model=DiscoveryResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def discover_urls(
    source: Literal["hellofresh", "kitchen_sanctuary"],
    request: Request,
    max_pages: int | None = Query(default=None, description="Maximum number of pages to crawl (for testing)", ge=1),
    current_user: User = Depends(get_current_user),
):
    """
    Discover recipe URLs from a supported source without importing.

    Coordinator-only endpoint. Uses crawlers to discover URLs from sitemap.xml
    or paginated category pages. URLs are returned but NOT imported.

    Rate limited to 5 requests per minute per IP address to prevent abuse.

    Args:
        source: Source to discover from (hellofresh or kitchen_sanctuary)
        request: FastAPI request object (required by slowapi for rate limiting)
        max_pages: Optional maximum number of pages to crawl (for testing/limiting scope)
        current_user: Authenticated user (must be coordinator)

    Returns:
        DiscoveryResponse: Source name, discovered URLs, and count

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If user is not a coordinator
        HTTPException(400): If discovery fails
        HTTPException(429): If rate limit is exceeded
    """
    require_coordinator(current_user)

    logger.info(f"Coordinator {current_user.id} discovering URLs from {source}")

    try:
        if source == "hellofresh":
            crawler = HelloFreshCrawler()
            urls = crawler.discover_recipe_urls(max_pages=max_pages)
        else:  # kitchen_sanctuary
            crawler = KitchenSanctuaryCrawler()
            urls = crawler.discover_recipe_urls(max_pages=max_pages)

        logger.info(f"Discovered {len(urls)} URLs from {source}")
        return DiscoveryResponse(source=source, urls=urls, count=len(urls))

    except Exception as e:
        logger.error(f"Discovery failed for {source}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL discovery failed: {str(e)}"
        )


@router.post("/discover-and-import/{source}", response_model=BatchImportResult, status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
def discover_and_import(
    source: Literal["hellofresh", "kitchen_sanctuary"],
    request: Request,
    payload: DiscoverAndImportRequest = DiscoverAndImportRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Discover recipe URLs from a source and import them (coordinator-only).

    Combines URL discovery with batch import. Limits both the discovery crawling
    (max_pages) and the number of imported recipes (max_recipes) to optimize
    performance and reduce load on target servers.

    Performance optimization:
    - Automatically limits sitemap crawling to only the pages needed
    - Heuristic: ~25 recipes per sitemap page (auto-calculated if max_pages not provided)
    - Significantly reduces unnecessary crawling (e.g., 500 URLs → 75 URLs for max_recipes=50)

    Rate limiting:
    - API layer: 3 requests per minute per IP address to prevent abuse
    - Service layer: 1 second delay between imports (polite crawling)

    Args:
        source: Source to discover from (hellofresh or kitchen_sanctuary)
        request: FastAPI request object (required by slowapi for rate limiting)
        payload: Request body with max_recipes (default: 50) and optional max_pages
        current_user: Authenticated user (must be coordinator)
        db: Database session

    Returns:
        BatchImportResult: Aggregate statistics and individual results

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If user is not a coordinator
        HTTPException(400): If discovery or import fails
        HTTPException(429): If rate limit is exceeded
    """
    require_coordinator(current_user)

    max_recipes = payload.max_recipes or 50

    # Calculate max_pages to limit discovery crawling (optimization)
    # Heuristic: ~25 recipes per sitemap page (conservative estimate to allow buffer for duplicates)
    # This significantly reduces crawling overhead by discovering only what we need
    if payload.max_pages is None:
        max_pages = (max_recipes // 25) + 1
        logger.info(f"Auto-calculated max_pages={max_pages} from max_recipes={max_recipes}")
    else:
        max_pages = payload.max_pages
        logger.info(f"Using explicit max_pages={max_pages}")

    logger.info(f"Coordinator {current_user.id} discovering and importing from {source} (max_recipes: {max_recipes}, max_pages: {max_pages})")

    try:
        # Discover URLs with page limit to reduce unnecessary crawling
        if source == "hellofresh":
            crawler = HelloFreshCrawler()
            urls = crawler.discover_recipe_urls(max_pages=max_pages)
        else:  # kitchen_sanctuary
            crawler = KitchenSanctuaryCrawler()
            urls = crawler.discover_recipe_urls(max_pages=max_pages)

        logger.info(f"Discovered {len(urls)} URLs from {source} (limited to {max_pages} pages)")

        # Limit to max_recipes (may be fewer URLs than max_recipes if discovery was limited)
        urls_to_import = urls[:max_recipes]
        logger.info(f"Importing {len(urls_to_import)} recipes")

        # Import batch
        result = import_batch(urls_to_import, db, delay_seconds=1.0)

        logger.info(
            f"Discover-and-import complete for {source}: {result.imported} imported, "
            f"{result.duplicates} duplicates, {result.errors} errors"
        )
        return result

    except Exception as e:
        logger.error(f"Discover-and-import failed for {source}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Discover-and-import failed: {str(e)}"
        )


@router.get("/status", response_model=StatusResponse, status_code=status.HTTP_200_OK)
def get_import_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get recipe import statistics by source type.

    Returns the count of recipes grouped by source_type (e.g., hellofresh_web,
    kitchen_sanctuary, url_import, manual).

    Any authenticated user can view statistics.

    Args:
        current_user: Authenticated user (injected by get_current_user)
        db: Database session

    Returns:
        StatusResponse: Recipe counts by source type

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
    """
    logger.debug(f"User {current_user.id} requesting import status")

    try:
        # Query recipe counts grouped by source_type
        stats_query = (
            db.query(
                Recipe.source_type,
                func.count(Recipe.id).label('count')
            )
            .group_by(Recipe.source_type)
            .all()
        )

        stats = [
            SourceStats(source_type=source_type, count=count)
            for source_type, count in stats_query
        ]

        return StatusResponse(stats=stats)

    except Exception as e:
        logger.error(f"Error retrieving import status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve import status"
        )
