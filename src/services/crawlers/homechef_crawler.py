"""
Home Chef catalog crawler.

Discovers recipe cards from Home Chef category pages (/recipes/<slug>) and
the weekly menu (/menu). Pages carry meal links in two HTML structures:

  Category pages: <article class="card"><a href="/meals/<slug>">
                  <h2>Name</h2><p>with sides</p></a></article>

  Menu page:      <a data-amplitude-name="meal_title"
                     data-amplitude-value="Full Title"
                     href="/meals/<slug>">

Both structures are handled by parse_homechef_listing.
"""

import logging
import re
from html import unescape as _unescape_html
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests.exceptions

from src.schemas.catalog import CollectionCard, CollectionPage
from src.services.crawlers.base_crawler import (
    RateLimiter,
    RobotsTxtParser,
    create_http_session,
)
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError

logger = logging.getLogger(__name__)

HOMECHEF_BASE_URL = "https://www.homechef.com"
HOMECHEF_MENU_URL = f"{HOMECHEF_BASE_URL}/menu"

# Slug for the weekly menu collection.
MENU_SLUG = "this-week"

# Maximum pages to follow for category collections (not the menu).
MAX_CATEGORY_PAGES = 3

# Matches <a ...href="/meals/SLUG"...> blocks (categories and menu).
# Group 1: attrs before href | Group 2: full /meals/PATH | Group 3: slug
# Group 4: attrs after href | Group 5: inner content up to </a>
_MEAL_BLOCK_RE = re.compile(
    r'<a\b([^>]*)href="(/meals/([^"?#]+))"([^>]*)>(.*?)</a>',
    re.DOTALL,
)

# Extracts data-amplitude-value from a tag's attribute string.
_AMP_VALUE_RE = re.compile(r'data-amplitude-value="([^"]+)"')

# Extracts text from first <h2> inside a card body.
_H2_RE = re.compile(r'<h2[^>]*>([^<]+)</h2>')

# Extracts text from first <p> inside a card body.
_P_RE = re.compile(r'<p>([^<]+)</p>')

# Extracts href from a ?page=N pagination link.
_PAGINATION_NEXT_RE = re.compile(
    r'href="(/recipes/[^"]+\?page=(\d+))"'
)

# Valid slug: alphanumeric, hyphens, no path traversal.
_SLUG_RE = re.compile(r'^[a-zA-Z0-9][-a-zA-Z0-9_]*$')


def _split_title(full_title: str) -> tuple[str, Optional[str]]:
    """Split 'Name with sides' into (name, 'with sides') on the first ' with '."""
    name, sep, rest = full_title.partition(" with ")
    if sep:
        return name.strip(), ("with " + rest.strip())
    return full_title.strip(), None



def parse_homechef_listing(html: str, url: str) -> CollectionPage:
    """
    Parse a Home Chef listing page into a CollectionPage.

    Handles both category pages (/recipes/<slug>) and the weekly menu (/menu).
    Meal cards are identified by anchor tags with /meals/ hrefs.

    Args:
        html: Full HTML of the listing page.
        url:  Absolute URL the page was fetched from.

    Returns:
        CollectionPage with one CollectionCard per meal link found.

    Raises:
        CrawlerParseError: When the page contains no meal links.
    """
    cards: list[CollectionCard] = []
    seen_ids: set[str] = set()

    for m in _MEAL_BLOCK_RE.finditer(html):
        attrs_before = m.group(1)
        meal_path = m.group(2)
        attrs_after = m.group(4)
        inner = m.group(5)

        external_id = meal_path.split("/")[-1]
        if not external_id or external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        # Determine the full title from the opening tag or inner content.
        full_attrs = attrs_before + attrs_after
        amp_match = None
        if 'data-amplitude-name="meal_title"' in full_attrs:
            amp_match = _AMP_VALUE_RE.search(full_attrs)

        if amp_match:
            full_title = _unescape_html(amp_match.group(1))
            name, headline = _split_title(full_title)
        else:
            # Category page: name in h2, headline in p (already split by the site)
            h2 = _H2_RE.search(inner)
            p = _P_RE.search(inner)
            if not h2:
                logger.debug("Skipping card %r: no h2 found", external_id)
                continue
            name = _unescape_html(h2.group(1).strip())
            headline_text = p.group(1).strip() if p else None
            # The <p> already has "with ..." form; use as-is.
            headline = headline_text if headline_text else None

        if not name:
            logger.debug("Skipping card %r: empty name", external_id)
            continue

        recipe_url = f"{HOMECHEF_BASE_URL}{meal_path}"
        cards.append(
            CollectionCard(
                external_id=external_id,
                name=name,
                headline=headline,
                image_url=None,
                prep_time_minutes=None,
                rating=None,
                rating_count=None,
                recipe_url=recipe_url,
            )
        )

    if not cards:
        raise CrawlerParseError(f"No meal links found on {url}")

    # Derive slug from the page URL for the CollectionPage.
    parsed = urlparse(url)
    path_slug = parsed.path.rstrip("/").split("/")[-1] or MENU_SLUG

    return CollectionPage(
        name="",  # caller sets the display name from the seed list
        slug=path_slug,
        url=url,
        cards=cards,
        children=[],
    )


class HomeChefCrawler:
    """
    Crawler for Home Chef category and menu listing pages.

    Fetches meal cards from /recipes/<slug> (category, up to 3 pages) or
    /menu (this week's menu, single page). Checks robots.txt and applies
    rate limiting.
    """

    def __init__(
        self,
        base_url: str = HOMECHEF_BASE_URL,
        rate_limit_delay: float = 2.0,
    ):
        if not base_url or not isinstance(base_url, str):
            raise ValueError("base_url must be a non-empty string")
        parsed = urlparse(base_url)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            raise ValueError(f"base_url must have http or https scheme, got: {base_url}")
        if not parsed.netloc:
            raise ValueError(f"base_url must include a valid domain, got: {base_url}")

        self.base_url = base_url.rstrip("/")
        self.domain = parsed.netloc

        self.session = create_http_session(retries=3, backoff_factor=0.5, timeout=10)
        self.rate_limiter = RateLimiter(default_delay=rate_limit_delay)
        self.robots_parser = RobotsTxtParser()
        self._configure_from_robots_txt()

    def _configure_from_robots_txt(self) -> None:
        crawl_delay = self.robots_parser.get_crawl_delay(self.base_url)
        if crawl_delay:
            self.rate_limiter.set_domain_delay(self.domain, crawl_delay)
            logger.info("Using Crawl-delay from robots.txt: %ss", crawl_delay)

    def fetch_collection(self, slug: str, url: str) -> CollectionPage:
        """
        Fetch a Home Chef collection page.

        For category slugs, follows ?page=N pagination up to MAX_CATEGORY_PAGES.
        For the menu slug ("this-week"), fetches a single page.
        Cards from all pages are merged into one CollectionPage.

        Args:
            slug: Collection slug, e.g. "customer-favorites" or "this-week".
            url:  Full URL for the first page.

        Returns:
            CollectionPage with all cards from all fetched pages.

        Raises:
            ValueError: If slug is malformed.
            CrawlerNetworkError: If robots.txt disallows the URL or the
                HTTP request fails.
            CrawlerParseError: If the first page contains no meal links, or
                the parsed slug does not match the requested slug.
        """
        if not _SLUG_RE.fullmatch(slug):
            raise ValueError(f"Invalid collection slug: {slug!r}")

        is_menu = (slug == MENU_SLUG)
        all_cards: list[CollectionCard] = []
        seen_ids: set[str] = set()
        fetch_url = url

        for page_num in range(1, MAX_CATEGORY_PAGES + 1):
            if not self.robots_parser.can_fetch(fetch_url):
                raise CrawlerNetworkError(f"robots.txt disallows fetching {fetch_url}")

            self.rate_limiter.wait_if_needed(self.domain)

            try:
                response = self.session.get(fetch_url, timeout=30)
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                raise CrawlerNetworkError(
                    f"Failed to fetch {fetch_url}: {exc}"
                ) from exc

            page = parse_homechef_listing(response.text, fetch_url)

            # On page 1, verify the slug for category pages.
            # The menu URL (/menu) does not embed "this-week" in its path, so skip that check.
            if page_num == 1 and not is_menu:
                if page.slug != slug:
                    raise CrawlerParseError(
                        f"Requested slug {slug!r} but page at {url} has slug {page.slug!r}"
                    )

            # Merge cards, deduplicating by external_id.
            for card in page.cards:
                if card.external_id not in seen_ids:
                    seen_ids.add(card.external_id)
                    all_cards.append(card)

            # Menu pages do not paginate.
            if is_menu:
                break

            # Find next page link in the HTML.
            next_url = self._find_next_page(response.text, slug, page_num)
            if not next_url or page_num >= MAX_CATEGORY_PAGES:
                break
            fetch_url = next_url

        return CollectionPage(
            name="",
            slug=slug,
            url=url,
            cards=all_cards,
            children=[],
        )

    def _find_next_page(self, html: str, slug: str, current_page: int) -> Optional[str]:
        """Return the absolute URL of the next page, or None if there is none."""
        expected_path = f"/recipes/{slug}?page={current_page + 1}"
        for m in _PAGINATION_NEXT_RE.finditer(html):
            path = m.group(1)
            if path == expected_path:
                return urljoin(self.base_url, path)
        return None
