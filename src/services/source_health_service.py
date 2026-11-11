"""
Daily source health check service.

Checks once per SOURCE_HEALTH_INTERVAL_HOURS that each recipe source still
imports the way it used to, records the result, and exposes the latest
status so the frontend can show per-source rows and a calm import-screen alert.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models.source_health import SourceHealthCheck
from src.schemas.source_health import SourceStatusResponse
from src.services.crawlers.base_crawler import USER_AGENT

logger = logging.getLogger(__name__)

# Sources covered by this service (order determines response order)
MONITORED_SOURCES = ["hellofresh_web", "kitchen_sanctuary"]

KITCHEN_SANCTUARY_FEED_URL = "https://www.kitchensanctuary.com/feed/"


def _check_hellofresh(settings) -> tuple[str, Optional[str], str]:
    """
    Scrape the HelloFresh canary URL and return (status, detail, import_mode).

    Healthy when scrape_recipe returns a title, >= 5 ingredients and >= 3 instructions.
    """
    from src.services.scraper_service import scrape_recipe, ScraperError

    canary_url = settings.source_health_canary_hellofresh
    try:
        data = scrape_recipe(canary_url)
    except ScraperError as e:
        return "failing", f"Scraper error: {str(e)[:200]}", "link"
    except Exception as e:
        return "failing", f"Unexpected error during import check: {type(e).__name__}", "link"

    missing = []
    if not data.title:
        missing.append("title")
    if len(data.ingredients) < 5:
        missing.append(f"ingredients (got {len(data.ingredients)}, need 5)")
    if len(data.instructions) < 3:
        missing.append(f"instructions (got {len(data.instructions)}, need 3)")

    if missing:
        return "failing", f"Recipe incomplete: missing {', '.join(missing)}.", "link"

    return "healthy", None, "link"


def _check_kitchen_sanctuary(settings) -> tuple[str, Optional[str], str]:
    """
    Fetch the Kitchen Sanctuary RSS feed and return (status, detail, import_mode).

    Healthy when the feed returns HTTP 200 and contains at least one <item>.
    Reports import_mode='saved_page' because direct scraping is blocked.
    """
    timeout = settings.scraper_request_timeout
    try:
        resp = requests.get(
            KITCHEN_SANCTUARY_FEED_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return "failing", "Feed request timed out.", "saved_page"
    except requests.exceptions.RequestException as e:
        return "failing", f"Feed request failed: {type(e).__name__}.", "saved_page"

    if resp.status_code != 200:
        return "failing", f"Feed returned HTTP {resp.status_code}.", "saved_page"

    if "<item>" not in resp.text:
        return "failing", "Feed returned no items.", "saved_page"

    return "healthy", None, "saved_page"


def check_source(source_type: str) -> SourceHealthCheck:
    """
    Run one health check for the given source and return an unsaved row.

    Args:
        source_type: 'hellofresh_web' or 'kitchen_sanctuary'

    Returns:
        SourceHealthCheck instance (not yet added to any session)
    """
    settings = get_settings()
    t0 = time.monotonic()

    if source_type == "hellofresh_web":
        status, detail, import_mode = _check_hellofresh(settings)
    elif source_type == "kitchen_sanctuary":
        status, detail, import_mode = _check_kitchen_sanctuary(settings)
    else:
        raise ValueError(f"Unknown source_type for health check: {source_type!r}")

    duration_ms = int((time.monotonic() - t0) * 1000)

    return SourceHealthCheck(
        source_type=source_type,
        checked_at=datetime.now(timezone.utc),
        status=status,
        detail=detail,
        import_mode=import_mode,
        duration_ms=duration_ms,
    )


def run_due_checks(db: Session) -> None:
    """
    For each monitored source, run a check if the latest row is older than
    SOURCE_HEALTH_INTERVAL_HOURS or absent.

    Failures are caught and logged so the caller (the worker loop) always
    continues to the next source.

    Args:
        db: SQLAlchemy session
    """
    settings = get_settings()
    interval = timedelta(hours=settings.source_health_interval_hours)
    now = datetime.now(timezone.utc)

    for source_type in MONITORED_SOURCES:
        try:
            stmt = (
                select(SourceHealthCheck)
                .where(SourceHealthCheck.source_type == source_type)
                .order_by(SourceHealthCheck.checked_at.desc())
                .limit(1)
            )
            latest = db.execute(stmt).scalar_one_or_none()

            if latest is not None:
                # Normalise to UTC if naive (SQLite stores naive datetimes)
                latest_at = latest.checked_at
                if latest_at.tzinfo is None:
                    latest_at = latest_at.replace(tzinfo=timezone.utc)
                if now - latest_at < interval:
                    logger.debug(
                        "Source health check skipped (not due yet)",
                        extra={"source_type": source_type, "last_checked": latest_at.isoformat()},
                    )
                    continue

            logger.info("Running source health check", extra={"source_type": source_type})
            row = check_source(source_type)
            db.add(row)
            db.commit()
            logger.info(
                "Source health check recorded",
                extra={
                    "source_type": source_type,
                    "status": row.status,
                    "duration_ms": row.duration_ms,
                },
            )

        except Exception as e:
            logger.error(
                f"Source health check failed for {source_type}: {e}",
                extra={"source_type": source_type},
                exc_info=True,
            )
            # Roll back any partial work so the session stays usable
            try:
                db.rollback()
            except Exception:
                pass


def _failing_since(rows: list[SourceHealthCheck]) -> Optional[datetime]:
    """
    Given rows ordered newest-first, return the checked_at of the first row
    in the current consecutive failing streak, or None if the latest is healthy.
    """
    if not rows or rows[0].status != "failing":
        return None

    # Walk backwards (oldest-first) through the failing streak from the most recent end
    failing_start = rows[0].checked_at
    for row in rows:
        if row.status != "failing":
            break
        failing_start = row.checked_at
    return failing_start


def latest_status(db: Session) -> list[SourceStatusResponse]:
    """
    Return the latest health status for each monitored source.

    Sources with no rows report status='never_checked'.

    Args:
        db: SQLAlchemy session

    Returns:
        List of SourceStatusResponse, one per monitored source, in MONITORED_SOURCES order.
    """
    result = []
    for source_type in MONITORED_SOURCES:
        stmt = (
            select(SourceHealthCheck)
            .where(SourceHealthCheck.source_type == source_type)
            .order_by(SourceHealthCheck.checked_at.desc())
        )
        rows = list(db.execute(stmt).scalars().all())

        if not rows:
            result.append(SourceStatusResponse(
                source_type=source_type,
                status="never_checked",
            ))
            continue

        latest = rows[0]
        result.append(SourceStatusResponse(
            source_type=source_type,
            status=latest.status,
            checked_at=latest.checked_at,
            failing_since=_failing_since(rows),
            detail=latest.detail,
            import_mode=latest.import_mode,
        ))

    return result
