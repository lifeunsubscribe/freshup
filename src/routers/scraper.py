"""
Scraper API endpoints for FreshUp.

Provides endpoints for importing recipes from external URLs, discovering recipes
from supported sources (HelloFresh, Kitchen Sanctuary), and viewing import statistics.

Authorization:
- Single URL import: Any authenticated user
- Batch operations: Coordinator only
- Discovery operations: Coordinator only
- Status: Any authenticated user
"""

import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.database import get_db
from src.db.models.user import User, UserRole
from src.db.models.recipe import Recipe
from src.middleware.auth import get_current_user
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
def import_single_url(
    request: ImportUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import a recipe from a single URL.

    Any authenticated user can import recipes. The recipe becomes globally
    readable (system-imported, created_by=None).

    Args:
        request: Request containing the URL to import
        current_user: Authenticated user (injected by get_current_user)
        db: Database session

    Returns:
        ImportResult: Result of the import operation (success/duplicate/error)

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(400): If URL is invalid or import fails
    """
    logger.info(f"User {current_user.id} importing recipe from URL")

    try:
        result = import_recipe_from_url(request.url, db)
        return result
    except Exception as e:
        logger.error(f"Unexpected error during import for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/import-batch", response_model=BatchImportResult, status_code=status.HTTP_200_OK)
def import_batch_urls(
    request: ImportBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import recipes from multiple URLs (batch operation).

    Coordinator-only endpoint. Processes URLs sequentially with rate limiting
    (1 second delay between requests by default).

    Args:
        request: Request containing list of URLs to import
        current_user: Authenticated user (must be coordinator)
        db: Database session

    Returns:
        BatchImportResult: Aggregate statistics and individual results

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If user is not a coordinator
    """
    require_coordinator(current_user)

    logger.info(f"Coordinator {current_user.id} importing batch of {len(request.urls)} URLs")

    try:
        result = import_batch(request.urls, db, delay_seconds=1.0)
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
def discover_urls(
    source: Literal["hellofresh", "kitchen_sanctuary"],
    max_pages: int | None = Query(default=None, description="Maximum number of pages to crawl (for testing)", ge=1),
    current_user: User = Depends(get_current_user),
):
    """
    Discover recipe URLs from a supported source without importing.

    Coordinator-only endpoint. Uses crawlers to discover URLs from sitemap.xml
    or paginated category pages. URLs are returned but NOT imported.

    Args:
        source: Source to discover from (hellofresh or kitchen_sanctuary)
        max_pages: Optional maximum number of pages to crawl (for testing/limiting scope)
        current_user: Authenticated user (must be coordinator)

    Returns:
        DiscoveryResponse: Source name, discovered URLs, and count

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If user is not a coordinator
        HTTPException(400): If discovery fails
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
def discover_and_import(
    source: Literal["hellofresh", "kitchen_sanctuary"],
    request: DiscoverAndImportRequest = DiscoverAndImportRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Discover recipe URLs from a source and import them (coordinator-only).

    Combines URL discovery with batch import. Limits the number of imported
    recipes using the max_recipes parameter (default: 50).

    Rate limiting: 1 second delay between imports.

    Args:
        source: Source to discover from (hellofresh or kitchen_sanctuary)
        request: Request with max_recipes parameter (default: 50)
        current_user: Authenticated user (must be coordinator)
        db: Database session

    Returns:
        BatchImportResult: Aggregate statistics and individual results

    Raises:
        HTTPException(401): If Authorization header is missing or token is invalid
        HTTPException(403): If user is not a coordinator
        HTTPException(400): If discovery or import fails
    """
    require_coordinator(current_user)

    max_recipes = request.max_recipes or 50
    logger.info(f"Coordinator {current_user.id} discovering and importing from {source} (max: {max_recipes})")

    try:
        # Discover URLs
        if source == "hellofresh":
            crawler = HelloFreshCrawler()
            urls = crawler.discover_recipe_urls()
        else:  # kitchen_sanctuary
            crawler = KitchenSanctuaryCrawler()
            urls = crawler.discover_recipe_urls()

        logger.info(f"Discovered {len(urls)} URLs from {source}")

        # Limit to max_recipes
        urls_to_import = urls[:max_recipes]
        logger.info(f"Importing {len(urls_to_import)} recipes (limited by max_recipes={max_recipes})")

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
