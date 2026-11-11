"""
Catalog endpoints for browsing HelloFresh collections.

Provides member-accessible endpoints that list top-level collections and
return one collection's cards, fetching the collection page on demand when
it has never been read or is older than CATALOG_REFRESH_HOURS.

Authorization:
- Both endpoints: Any authenticated user (member or coordinator)

Rate Limiting:
- GET /catalog/{source}/collections: 5 requests/minute per IP
- GET /catalog/{source}/collections/{slug}: 10 requests/minute per IP
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.db.database import get_db
from src.db.models.user import User
from src.middleware.auth import get_current_user
from src.middleware.rate_limit import limiter
from src.schemas.catalog import CardResponse, CollectionDetail, CollectionSummary
from src.services import catalog_service
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError
from src.utils.sanitize import sanitize_exception_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

# Supported catalog sources — currently only HelloFresh.
_VALID_SOURCES = frozenset({"hellofresh_web"})


def _validate_source(source: str) -> None:
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown catalog source: {source!r}",
        )


@router.get(
    "/{source}/collections",
    response_model=list[CollectionSummary],
    status_code=status.HTTP_200_OK,
)
@limiter.limit("5/minute")
def list_collections(
    source: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CollectionSummary]:
    """
    List top-level collections for a source.

    On the first call for a source with no seeded rows, seeds from
    HelloFresh's collection sitemap (one network request).  Returns
    collections sorted by name.

    Args:
        source:       Catalog source identifier, e.g. "hellofresh_web".
        request:      FastAPI request (required by rate limiter).
        current_user: Authenticated user.
        db:           Database session.

    Returns:
        List of CollectionSummary objects sorted by name.

    Raises:
        HTTPException(404): When the source is unknown.
        HTTPException(400): When sitemap seeding fails.
        HTTPException(429): When the rate limit is exceeded.
    """
    _validate_source(source)
    logger.debug("User %s listing collections for source %r", current_user.id, source)

    # Seed on first call when no rows exist for this source.
    from sqlalchemy import func
    from src.db.models.source_catalog import SourceCollection, SourceCollectionCard

    row_count = (
        db.query(func.count(SourceCollection.id))
        .filter_by(source_type=source)
        .scalar()
    )
    if row_count == 0:
        try:
            catalog_service.seed_hellofresh_collections(db)
        except CrawlerNetworkError as exc:
            logger.warning("Sitemap seed failed for %r: %s", source, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to seed collections from the source. Please try again later.",
            )
        except CrawlerParseError as exc:
            logger.warning("Sitemap seed parse error for %r: %s", source, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to process collection data from the source. The source format may have changed.",
            )

    # Query top-level collections with their card counts.
    rows = (
        db.query(SourceCollection, func.count(SourceCollectionCard.card_id).label("card_count"))
        .outerjoin(SourceCollectionCard, SourceCollectionCard.collection_id == SourceCollection.id)
        .filter(SourceCollection.source_type == source, SourceCollection.parent_slug.is_(None))
        .group_by(SourceCollection.id)
        .order_by(SourceCollection.name)
        .all()
    )

    return [
        CollectionSummary(
            slug=coll.slug,
            name=coll.name,
            card_count=count,
            last_fetched_at=coll.last_fetched_at,
        )
        for coll, count in rows
    ]


@router.get(
    "/{source}/collections/{slug}",
    response_model=CollectionDetail,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
def get_collection(
    source: str,
    slug: str,
    request: Request,
    fresh: bool = Query(
        default=None,
        description="true = always fetch; false = return stored without fetching. Omit for default staleness logic.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionDetail:
    """
    Return a collection's detail: metadata, children and recipe cards.

    Fetches the collection page on demand when it has never been read or
    is older than CATALOG_REFRESH_HOURS (unless ``?fresh=false``).

    Args:
        source:       Catalog source identifier.
        slug:         Collection URL slug.
        request:      FastAPI request (required by rate limiter).
        fresh:        Override staleness logic: True = force fetch, False = skip fetch.
        current_user: Authenticated user.
        db:           Database session.

    Returns:
        CollectionDetail with children and cards in page order.
        When a fetch failed but stored cards exist, includes ``fetch_error``.

    Raises:
        HTTPException(404): When the source or slug is unknown.
        HTTPException(400): When the fetch fails and no stored cards exist.
        HTTPException(429): When the rate limit is exceeded.
    """
    _validate_source(source)
    logger.debug(
        "User %s requesting collection %r/%r (fresh=%r)", current_user.id, source, slug, fresh
    )

    # fresh query param overrides staleness logic.
    if fresh is True:
        refresh_if_stale, force_refresh = True, True
    elif fresh is False:
        refresh_if_stale, force_refresh = False, False
    else:
        refresh_if_stale, force_refresh = True, False

    try:
        result = catalog_service.get_collection(
            db,
            source,
            slug,
            refresh_if_stale=refresh_if_stale,
            force_refresh=force_refresh,
        )
    except CrawlerNetworkError as exc:
        logger.warning("Fetch failed for %r/%r (network): %s", source, slug, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to fetch collection from the source. Please try again later.",
        )
    except CrawlerParseError as exc:
        logger.warning("Fetch failed for %r/%r (parse): %s", source, slug, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to process collection data from the source. The source format may have changed.",
        )
    except SQLAlchemyError as exc:
        logger.error("Database error for %r/%r: %s", source, slug, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error retrieving collection",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    collection = result.collection

    # Build children summaries
    children = [
        CollectionSummary(
            slug=child.slug,
            name=child.name,
            card_count=result.children_card_counts.get(str(child.id), 0),
            last_fetched_at=child.last_fetched_at,
        )
        for child in result.children
    ]

    # Build card responses
    cards = [
        CardResponse(
            id=card.id,
            name=card.name,
            headline=card.headline,
            image_url=card.image_url,
            prep_time_minutes=card.prep_time_minutes,
            rating=card.rating,
            rating_count=card.rating_count,
            recipe_url=card.recipe_url,
            recipe_id=card.recipe_id,
            is_persisted=bool(card.recipe_rel and card.recipe_rel.is_persisted),
        )
        for card in result.cards
    ]

    return CollectionDetail(
        slug=collection.slug,
        name=collection.name,
        source_type=collection.source_type,
        last_fetched_at=collection.last_fetched_at,
        children=children,
        cards=cards,
        fetch_error=result.fetch_error,
    )
