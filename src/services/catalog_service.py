"""
Catalog service for HelloFresh collection browsing.

Manages seeding top-level collections from the HelloFresh sitemap, checking
staleness, fetching on demand, and upserting cards and join rows.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
import requests.exceptions

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.config import get_settings
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.schemas.catalog import CollectionPage
from src.services.crawlers.base_crawler import create_http_session
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError
from src.services.crawlers.hellofresh_crawler import (
    HELLOFRESH_BASE_URL,
    HelloFreshCrawler,
    classify_hellofresh_url,
)
from src.utils.sanitize import sanitize_exception_message

logger = logging.getLogger(__name__)

HELLOFRESH_SOURCE = "hellofresh_web"
COLLECTIONS_SITEMAP_URL = f"{HELLOFRESH_BASE_URL}/sitemap_recipe_collections.xml"
_SITEMAP_NS = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Reuses the same slug validation as the crawler; ensures no path traversal.
_SLUG_RE = re.compile(r"^[a-zA-Z0-9][-a-zA-Z0-9_]*$")


def _slug_to_name(slug: str) -> str:
    """Derive a human-readable display name from a URL slug."""
    return slug.replace("-", " ").capitalize()


def _is_stale(last_fetched_at: Optional[datetime]) -> bool:
    """Return True when last_fetched_at is null or older than CATALOG_REFRESH_HOURS."""
    if last_fetched_at is None:
        return True
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.catalog_refresh_hours)
    # SQLite stores naive datetimes; treat them as UTC.
    dt = last_fetched_at if last_fetched_at.tzinfo else last_fetched_at.replace(tzinfo=timezone.utc)
    return dt < cutoff


@dataclass
class CollectionResult:
    """Internal return type from get_collection."""

    collection: SourceCollection
    cards: list[SourceRecipeCard] = field(default_factory=list)
    children: list[SourceCollection] = field(default_factory=list)
    children_card_counts: dict[str, int] = field(default_factory=dict)  # id → count
    fetch_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def seed_hellofresh_collections(db: Session) -> int:
    """
    Seed top-level HelloFresh collections from the collections sitemap.

    Fetches ``sitemap_recipe_collections.xml`` once and inserts any collection
    URL not already in the database with ``last_fetched_at = null``.  Existing
    rows are left unchanged so that already-fetched collections keep their data.

    Args:
        db: Database session.

    Returns:
        Number of new rows inserted.

    Raises:
        CrawlerNetworkError: When the sitemap cannot be fetched.
        CrawlerParseError: When the sitemap XML cannot be parsed.
    """
    session = create_http_session(retries=2, backoff_factor=0.5, timeout=30)

    try:
        response = session.get(COLLECTIONS_SITEMAP_URL, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise CrawlerNetworkError(
            f"Failed to fetch collections sitemap: {exc}"
        ) from exc

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:  # type: ignore[attr-defined]
        raise CrawlerParseError(f"Collections sitemap is not valid XML: {exc}") from exc

    existing_slugs: set[str] = {
        row[0]
        for row in db.query(SourceCollection.slug).filter_by(source_type=HELLOFRESH_SOURCE).all()
    }

    new_rows: list[SourceCollection] = []
    for url_elem in root.findall(".//ns:url/ns:loc", _SITEMAP_NS):
        url = (url_elem.text or "").strip()
        if classify_hellofresh_url(url) != "collection":
            continue
        path = urlparse(url).path.rstrip("/")
        slug = path.split("/")[-1]
        if not _SLUG_RE.fullmatch(slug) or slug in existing_slugs:
            continue
        existing_slugs.add(slug)
        new_rows.append(
            SourceCollection(
                source_type=HELLOFRESH_SOURCE,
                slug=slug,
                name=_slug_to_name(slug),
                url=url,
                last_fetched_at=None,
                parent_slug=None,
            )
        )

    if new_rows:
        db.add_all(new_rows)
        db.commit()
        logger.info("Seeded %d HelloFresh collections from sitemap", len(new_rows))

    return len(new_rows)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def upsert_collection_page(db: Session, page: CollectionPage, source_type: str = HELLOFRESH_SOURCE) -> None:
    """
    Persist a fetched CollectionPage: update the collection row, upsert cards,
    upsert children, and replace join rows with the page's ordering.

    Args:
        db:          Database session.
        page:        Parsed collection page from the crawler.
        source_type: Source type string (default: "hellofresh_web").
    """
    collection = db.query(SourceCollection).filter_by(
        source_type=source_type, slug=page.slug
    ).first()
    if collection is None:
        collection = SourceCollection(
            source_type=source_type,
            slug=page.slug,
            url=page.url,
        )
        db.add(collection)

    collection.name = page.name
    collection.url = page.url
    collection.last_fetched_at = datetime.now(timezone.utc)

    # Upsert cards by (source_type, recipe_url)
    upserted_cards: list[SourceRecipeCard] = []
    seen_urls: set[str] = set()
    for card_data in page.cards:
        if card_data.recipe_url in seen_urls:
            continue
        seen_urls.add(card_data.recipe_url)
        card = db.query(SourceRecipeCard).filter_by(
            source_type=source_type, recipe_url=card_data.recipe_url
        ).first()
        if card is None:
            card = SourceRecipeCard(source_type=source_type, recipe_url=card_data.recipe_url)
            db.add(card)
        card.external_id = card_data.external_id
        card.name = card_data.name
        card.headline = card_data.headline
        card.image_url = card_data.image_url
        card.prep_time_minutes = card_data.prep_time_minutes
        card.rating = card_data.rating
        card.rating_count = card_data.rating_count
        upserted_cards.append(card)

    # Upsert children as SourceCollection rows with parent_slug = slug
    for child in page.children:
        if not _SLUG_RE.fullmatch(child.slug):
            continue
        child_row = db.query(SourceCollection).filter_by(
            source_type=source_type, slug=child.slug
        ).first()
        if child_row is None:
            db.add(SourceCollection(
                source_type=source_type,
                slug=child.slug,
                name=child.name,
                url=f"{HELLOFRESH_BASE_URL}/recipes/{child.slug}",
                parent_slug=page.slug,
                last_fetched_at=None,
            ))
        else:
            if child_row.parent_slug is not None:
                child_row.parent_slug = page.slug
            child_row.name = child.name

    # Flush so card PKs are assigned before building join rows
    db.flush()

    # Replace join rows with the page's current ordering
    db.query(SourceCollectionCard).filter_by(collection_id=collection.id).delete()
    for position, card in enumerate(upserted_cards):
        db.add(SourceCollectionCard(
            collection_id=collection.id,
            card_id=card.id,
            position=position,
        ))

    db.commit()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_collection(
    db: Session,
    source: str,
    slug: str,
    *,
    refresh_if_stale: bool = True,
    force_refresh: bool = False,
) -> Optional[CollectionResult]:
    """
    Return a CollectionResult for the given source and slug, fetching
    when stale (or forced).

    Returns None when the slug is not in the database (router returns 404).

    When a fetch attempt fails but stored cards exist, the result carries
    ``fetch_error`` with a sanitized message and HTTP 200 is appropriate.
    When a fetch fails and there are no stored cards the exception propagates
    so the router can return HTTP 400.

    Args:
        db:               Database session.
        source:           Source type string, e.g. "hellofresh_web".
        slug:             Collection slug.
        refresh_if_stale: When True, fetch if last_fetched_at is null or old.
        force_refresh:    When True, fetch regardless of age.

    Raises:
        CrawlerNetworkError: Fetch failed and no cards are stored.
        CrawlerParseError:   Fetch failed and no cards are stored.
    """
    collection = db.query(SourceCollection).filter_by(
        source_type=source, slug=slug
    ).first()
    if collection is None:
        return None

    should_fetch = force_refresh or (refresh_if_stale and _is_stale(collection.last_fetched_at))
    fetch_error: Optional[str] = None

    if should_fetch:
        try:
            crawler = _make_crawler()
            page = crawler.fetch_collection(slug)
            upsert_collection_page(db, page, source_type=source)
            # Reload after upsert so the result reflects the fresh data
            db.refresh(collection)
        except (CrawlerNetworkError, CrawlerParseError) as exc:
            # Check whether we have stored cards to fall back to
            stored_count = db.query(func.count(SourceCollectionCard.card_id)).filter_by(
                collection_id=collection.id
            ).scalar()
            if stored_count:
                fetch_error = sanitize_exception_message(str(exc), max_length=250)
                logger.warning(
                    "Fetch failed for %s/%s, returning %d stored card(s): %s",
                    source, slug, stored_count, exc,
                )
            else:
                raise

    # Load cards ordered by position with recipe relationship eagerly loaded
    cards = (
        db.query(SourceRecipeCard)
        .join(SourceCollectionCard, SourceCollectionCard.card_id == SourceRecipeCard.id)
        .filter(SourceCollectionCard.collection_id == collection.id)
        .order_by(SourceCollectionCard.position)
        .options(joinedload(SourceRecipeCard.recipe_rel))
        .all()
    )

    # Load direct children and their card counts
    children = (
        db.query(SourceCollection)
        .filter_by(source_type=source, parent_slug=slug)
        .order_by(SourceCollection.name)
        .all()
    )

    child_ids = [c.id for c in children]
    if child_ids:
        counts = (
            db.query(SourceCollectionCard.collection_id, func.count(SourceCollectionCard.card_id))
            .filter(SourceCollectionCard.collection_id.in_(child_ids))
            .group_by(SourceCollectionCard.collection_id)
            .all()
        )
        counts_map: dict = {str(cid): cnt for cid, cnt in counts}
    else:
        counts_map = {}

    return CollectionResult(
        collection=collection,
        cards=cards,
        children=children,
        children_card_counts={str(c.id): counts_map.get(str(c.id), 0) for c in children},
        fetch_error=fetch_error,
    )


def _make_crawler() -> HelloFreshCrawler:
    """Return a HelloFreshCrawler; extracted so tests can patch it."""
    return HelloFreshCrawler()
