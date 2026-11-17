"""
Catalog service for HelloFresh collection browsing.

Manages seeding top-level collections from the HelloFresh sitemap, checking
staleness, fetching on demand, upserting cards and join rows, and background
enrichment of card ingredient data.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional
from urllib.parse import urlparse
from uuid import UUID

import defusedxml.ElementTree as ET
import requests.exceptions

from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from src.db.database import get_session_factory

from src.config import get_settings
from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.schemas.catalog import CollectionPage
from src.schemas.import_service import ImportStatus
from src.services.crawlers.base_crawler import RateLimiter, RobotsTxtParser, create_http_session
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError
from src.services.crawlers.hellofresh_crawler import (
    HELLOFRESH_BASE_URL,
    HelloFreshCrawler,
    classify_hellofresh_url,
)
from src.services.crawlers.homechef_crawler import (
    HOMECHEF_BASE_URL,
    HOMECHEF_MENU_URL,
    MENU_SLUG,
    HomeChefCrawler,
)
from src.services.import_service import import_recipe_from_url, _safe_image_url
from src.services.ingredient_keys import keys_for, keys_for_recipe
from src.services.scraper_service import scrape_recipe
from src.utils.sanitize import sanitize_exception_message

logger = logging.getLogger(__name__)

HELLOFRESH_SOURCE = "hellofresh_web"
HOMECHEF_SOURCE = "homechef_web"
COLLECTIONS_SITEMAP_URL = f"{HELLOFRESH_BASE_URL}/sitemap_recipe_collections.xml"

# Fixed list of Home Chef category slugs (derived from the category nav on homechef.com/recipes/*).
# Seeding is static — no network request needed.
_HOMECHEF_CATEGORY_SLUGS: list[tuple[str, str]] = [
    ("breakfast", "Breakfast"),
    ("beef", "Beef"),
    ("calorie-conscious", "Calorie-Conscious"),
    ("carb-conscious", "Carb-Conscious"),
    ("chicken", "Chicken"),
    ("cod", "Cod"),
    ("customer-favorites", "Customer Favorites"),
    ("dessert", "Dessert"),
    ("fish", "Fish"),
    ("lamb", "Lamb"),
    ("pasta", "Pasta"),
    ("pork", "Pork"),
    ("poultry", "Poultry"),
    ("premium", "Premium"),
    ("salad", "Salad"),
    ("salmon", "Salmon"),
    ("seafood", "Seafood"),
    ("shrimp", "Shrimp"),
    ("smoothie", "Smoothie"),
    ("staff-picks", "Staff Picks"),
    ("steak", "Steak"),
    ("vegetarian", "Vegetarian"),
    ("without-milk", "Without Milk"),
    ("without-nuts", "Without Nuts"),
    ("without-soy", "Without Soy"),
    ("without-wheat", "Without Wheat"),
]


@dataclass
class CatalogSource:
    """Per-source configuration: display label, crawler factory, and seed function."""

    label: str
    # Callables are looked up at call time (not captured at import) so tests can
    # patch catalog_service._make_crawler and catalog_service.seed_hellofresh_collections.
    crawler_factory: Callable[[], Any]
    seed_fn: Callable[..., int]
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


def _parent_slug_from_url(url: str) -> Optional[str]:
    """
    Read a collection's parent from its URL.

    HelloFresh encodes the hierarchy in the path: ``/recipes/<slug>`` is a
    top-level category and ``/recipes/<parent>/<slug>`` is a sub-collection
    (usually an ingredient, e.g. ``/recipes/grain-recipes/arborio-rice``).
    """
    segments = urlparse(url).path.strip("/").split("/")
    return segments[-2] if len(segments) >= 3 else None


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
                parent_slug=_parent_slug_from_url(url),
            )
        )

    if new_rows:
        db.add_all(new_rows)
        db.commit()
        logger.info("Seeded %d HelloFresh collections from sitemap", len(new_rows))

    return len(new_rows)


def seed_homechef_collections(db: Session) -> int:
    """
    Seed Home Chef collections from the fixed category slug list.

    Inserts a row for each category slug not already in the database, plus
    the weekly menu collection ("this-week").  No network request is made.

    Args:
        db: Database session.

    Returns:
        Number of new rows inserted.
    """
    existing_slugs: set[str] = {
        row[0]
        for row in db.query(SourceCollection.slug).filter_by(source_type=HOMECHEF_SOURCE).all()
    }

    new_rows: list[SourceCollection] = []
    for slug, name in _HOMECHEF_CATEGORY_SLUGS:
        if slug in existing_slugs:
            continue
        existing_slugs.add(slug)
        new_rows.append(
            SourceCollection(
                source_type=HOMECHEF_SOURCE,
                slug=slug,
                name=name,
                url=f"{HOMECHEF_BASE_URL}/recipes/{slug}",
                last_fetched_at=None,
                parent_slug=None,
            )
        )

    # Weekly menu entry.
    if MENU_SLUG not in existing_slugs:
        new_rows.append(
            SourceCollection(
                source_type=HOMECHEF_SOURCE,
                slug=MENU_SLUG,
                name="This week at Home Chef",
                url=HOMECHEF_MENU_URL,
                last_fetched_at=None,
                parent_slug=None,
            )
        )

    if new_rows:
        db.add_all(new_rows)
        db.commit()
        logger.info("Seeded %d Home Chef collections", len(new_rows))

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
                # Sub-collections live under their parent's path; /recipes/<child>
                # alone serves the /recipes hub instead.
                url=f"{collection.url.rstrip('/')}/{child.slug}",
                parent_slug=page.slug,
                last_fetched_at=None,
            ))
        else:
            # The sitemap seed knows nothing about hierarchy, so a seeded row has
            # parent_slug None. A page listing this slug as a child is the first
            # thing that does know; take it.
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
            crawler = CATALOG_SOURCES[source].crawler_factory()
            page = crawler.fetch_collection(slug, collection.url)
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


def _make_homechef_crawler() -> HomeChefCrawler:
    """Return a HomeChefCrawler; extracted so tests can patch it."""
    return HomeChefCrawler()


# Registry of supported catalog sources.  Each entry's callables delegate to
# module-level functions so tests can patch crawlers or seed functions via
# monkeypatch/patch without breaking the registry.
CATALOG_SOURCES: dict[str, CatalogSource] = {
    HELLOFRESH_SOURCE: CatalogSource(
        label="HelloFresh",
        crawler_factory=lambda: _make_crawler(),
        seed_fn=lambda db: seed_hellofresh_collections(db),
    ),
    HOMECHEF_SOURCE: CatalogSource(
        label="Home Chef",
        crawler_factory=lambda: _make_homechef_crawler(),
        seed_fn=lambda db: seed_homechef_collections(db),
    ),
}


# ---------------------------------------------------------------------------
# Open (import on demand)
# ---------------------------------------------------------------------------


@dataclass
class OpenCardResult:
    """Return type from open_card."""

    recipe: Recipe
    # True when import_recipe_from_url was called on this request (new import or duplicate link).
    # False when the card was already linked and the recipe was returned from cache.
    imported: bool


def open_card(db: Session, card_id: UUID) -> Optional[OpenCardResult]:
    """
    Return the Recipe for a catalog card, importing it on demand if needed.

    - If the card's recipe_id is already set and the recipe exists, return it
      without fetching (imported=False).
    - Otherwise call import_recipe_from_url with the card's URL. On success or
      duplicate, link the card to the recipe and return it (imported=True).
    - On import error, raise ValueError with a sanitized message; the card is
      left unlinked so the next open retries.

    Args:
        db:      Database session.
        card_id: Primary key of the SourceRecipeCard to open.

    Returns:
        OpenCardResult, or None if the card does not exist.

    Raises:
        ValueError: When import_recipe_from_url returns status=error.
    """
    card = db.query(SourceRecipeCard).filter_by(id=card_id).first()
    if card is None:
        return None

    # Fast path: card is already linked to a recipe that still exists.
    if card.recipe_id is not None:
        recipe = (
            db.query(Recipe)
            .options(joinedload(Recipe.ingredients))
            .filter_by(id=card.recipe_id)
            .first()
        )
        if recipe is not None:
            if card.ingredient_keys is None:
                # Backfill ingredient keys for cards imported before this column existed.
                card.ingredient_keys = sorted(keys_for_recipe(recipe))
                try:
                    db.commit()
                except SQLAlchemyError:
                    db.rollback()
            return OpenCardResult(recipe=recipe, imported=False)
        # Recipe was pruned (ON DELETE SET NULL fired); fall through to re-import.

    result = import_recipe_from_url(card.recipe_url, db)

    if result.status in (ImportStatus.success, ImportStatus.duplicate):
        recipe = (
            db.query(Recipe)
            .options(joinedload(Recipe.ingredients))
            .filter_by(id=result.recipe_id)
            .first()
        )
        if recipe is not None:
            card.recipe_id = recipe.id
            card.ingredient_keys = sorted(keys_for_recipe(recipe))
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                card.recipe_id = None
                card.ingredient_keys = None
                raise ValueError("Failed to link card to recipe; please retry")
            return OpenCardResult(recipe=recipe, imported=True)

    # Import failed or recipe lookup returned None after a successful import (unexpected).
    raw_msg = result.error_message or "Import failed"
    raise ValueError(sanitize_exception_message(raw_msg, max_length=250))


# ---------------------------------------------------------------------------
# Background enrichment
# ---------------------------------------------------------------------------


def enrich_next_cards(db: Session, limit: int = 5) -> int:
    """
    Fill ingredient_keys, image_url, and prep_time_minutes for un-enriched catalog cards.

    Picks up to ``limit`` cards where ``ingredient_keys IS NULL`` or
    ``image_url IS NULL``, ordering cards missing an image first (so listing
    sources that omit photos, e.g. Home Chef, are filled quickly), then by
    collection-membership count descending.  For each card: checks robots.txt,
    waits on the rate limiter, scrapes the recipe page, and fills:

    - ``ingredient_keys``: set to ``sorted(keys_for(ing) for all ingredients)``
    - ``image_url``: set via ``_safe_image_url`` when the card has no image; falls
      back to ``""`` (sentinel) when no image URL is obtainable, so the card exits
      the ``image_url IS NULL`` selection filter and is not re-queued indefinitely
    - ``prep_time_minutes``: set from ``total_time_minutes`` when the card has no time

    Existing non-null values are never overwritten.  Does not create a Recipe row.

    A ``CrawlerNetworkError`` raised by the robots.txt check stops the batch
    immediately; remaining cards are left as-is.  Any other fetch or parse
    failure is logged; ``ingredient_keys`` is stored as ``[]`` (when it was NULL)
    and ``image_url`` as ``""`` (when it was NULL) so the card is not retried
    forever.  Commits after each card.

    Args:
        db:    Database session.
        limit: Maximum number of cards to process (default: 5).

    Returns:
        Number of cards updated.

    Raises:
        CrawlerNetworkError: When robots.txt disallows a card URL.
    """
    subq = (
        db.query(
            SourceCollectionCard.card_id,
            func.count(SourceCollectionCard.card_id).label("coll_count"),
        )
        .group_by(SourceCollectionCard.card_id)
        .subquery()
    )
    cards = (
        db.query(SourceRecipeCard)
        .outerjoin(subq, SourceRecipeCard.id == subq.c.card_id)
        .filter(
            or_(
                SourceRecipeCard.ingredient_keys.is_(None),
                SourceRecipeCard.image_url.is_(None),
            )
        )
        # Cards missing an image come before cards that only lack ingredient keys.
        .order_by(
            SourceRecipeCard.image_url.is_(None).desc(),
            func.coalesce(subq.c.coll_count, 0).desc(),
        )
        .limit(limit)
        .all()
    )

    if not cards:
        return 0

    rate_limiter = RateLimiter()
    robots_parser = RobotsTxtParser()
    updated = 0

    for card in cards:
        domain = urlparse(card.recipe_url).netloc

        # Robots check: a disallow stops the entire batch per the crawl policy.
        if not robots_parser.can_fetch(card.recipe_url):
            raise CrawlerNetworkError(f"robots.txt disallows {card.recipe_url}")

        rate_limiter.wait_if_needed(domain)

        any_field_assigned = False
        try:
            scraped = scrape_recipe(card.recipe_url)
            if card.ingredient_keys is None:
                ingredient_keys: set[str] = set()
                for ing in scraped.ingredients or []:
                    ingredient_keys |= keys_for(ing)
                card.ingredient_keys = sorted(ingredient_keys)
                any_field_assigned = True
            if card.image_url is None:
                # "" sentinel when scraper finds no image — exits IS NULL filter
                # to prevent this card from occupying the queue head indefinitely.
                card.image_url = _safe_image_url(scraped.image_url) or ""
                any_field_assigned = True
            if card.prep_time_minutes is None and scraped.total_time_minutes is not None:
                card.prep_time_minutes = scraped.total_time_minutes
                any_field_assigned = True
        except Exception as exc:
            logger.warning("enrich_next_cards: failed to fetch/parse %s: %s", card.recipe_url, exc)
            if card.ingredient_keys is None:
                card.ingredient_keys = []
                any_field_assigned = True
            if card.image_url is None:
                card.image_url = ""  # sentinel: exits IS NULL filter after failed scrape
                any_field_assigned = True

        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.error("enrich_next_cards: DB commit failed for card %s", card.id)
            continue

        if any_field_assigned:
            updated += 1

    return updated


async def card_enrichment_worker() -> None:
    """
    Background worker that periodically enriches un-enriched catalog cards.

    Runs until cancelled (application shutdown).  Opens a fresh session each
    pass, calls ``enrich_next_cards`` with the configured batch size, and logs
    the result.  All exceptions are caught so the worker never exits on its own.
    """
    settings = get_settings()
    logger.info(
        "Card enrichment worker started (interval: %ds, batch: %d)",
        settings.catalog_enrich_interval_seconds,
        settings.catalog_enrich_batch_size,
    )
    try:
        while True:
            try:
                batch_size = settings.catalog_enrich_batch_size

                def _run_pass():
                    factory = get_session_factory()
                    with factory() as db:
                        return enrich_next_cards(db, batch_size)

                loop = asyncio.get_running_loop()
                count = await loop.run_in_executor(None, _run_pass)
                logger.info("enriched %d card(s)", count)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Card enrichment worker error: %s", exc, exc_info=True)

            await asyncio.sleep(settings.catalog_enrich_interval_seconds)

    except asyncio.CancelledError:
        logger.info("Card enrichment worker shutting down gracefully")
        raise
