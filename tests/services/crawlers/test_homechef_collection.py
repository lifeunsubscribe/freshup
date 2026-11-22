"""
Tests for Home Chef listing page parsing and HomeChefCrawler.fetch_collection.

Covers:
- parse_homechef_listing: category fixture (24 cards), menu fixture (88 cards)
- Name/headline split on ' with '
- CrawlerParseError when page has no meal links
- fetch_collection: robots.txt disallow, slug mismatch, pagination (up to 3 pages)
- Menu slug skips pagination
"""

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.services.crawlers.homechef_crawler import (
    HOMECHEF_BASE_URL,
    MENU_SLUG,
    HomeChefCrawler,
    parse_homechef_listing,
    _split_title,
)
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "../../fixtures")
CATEGORY_FIXTURE = os.path.join(FIXTURE_DIR, "homechef_category_customer_favorites.html")
MENU_FIXTURE = os.path.join(FIXTURE_DIR, "homechef_weekly_menu.html")


def _load(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _make_crawler_no_robots() -> HomeChefCrawler:
    with patch.object(HomeChefCrawler, "_configure_from_robots_txt"):
        return HomeChefCrawler()


# ---------------------------------------------------------------------------
# _split_title unit tests
# ---------------------------------------------------------------------------


class TestSplitTitle:
    def test_splits_on_first_with(self):
        name, headline = _split_title("Teriyaki Ginger-Glazed Salmon with stir-fried bok choy")
        assert name == "Teriyaki Ginger-Glazed Salmon"
        assert headline == "with stir-fried bok choy"

    def test_no_with_gives_none_headline(self):
        name, headline = _split_title("Turkey Breast Roast")
        assert name == "Turkey Breast Roast"
        assert headline is None

    def test_multiple_with_splits_on_first(self):
        name, headline = _split_title("Chicken with Lemon with Herbs")
        assert name == "Chicken"
        assert headline == "with Lemon with Herbs"

    def test_strips_whitespace(self):
        name, headline = _split_title("  Name with Sides  ")
        assert name == "Name"
        assert headline == "with Sides"


# ---------------------------------------------------------------------------
# parse_homechef_listing — fixture tests
# ---------------------------------------------------------------------------


class TestParseHomechefListingCategoryFixture:
    def test_returns_24_cards(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        assert len(page.cards) == 24

    def test_slug_derived_from_url(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        assert page.slug == "customer-favorites"

    def test_first_card_name_split(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        # First card: Teriyaki Ginger-Glazed Salmon with stir-fried bok choy and carrots
        first = page.cards[0]
        assert first.name == "Teriyaki Ginger-Glazed Salmon"
        assert first.headline == "with stir-fried bok choy and carrots"

    def test_card_external_id_is_last_path_segment(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        for card in page.cards:
            assert card.external_id == card.recipe_url.split("/")[-1]

    def test_card_recipe_url_is_absolute(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        for card in page.cards:
            assert card.recipe_url.startswith(HOMECHEF_BASE_URL)

    def test_every_card_carries_the_listings_photo(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        for card in page.cards:
            assert card.image_url is not None, card.name
            assert card.image_url.startswith("https://asset.homechef.com/")

    def test_photo_is_the_550_wide_one_with_its_commas_intact(self):
        """The image URLs contain commas, and the srcset lists 275w, 550w and 1100w."""
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        first = page.cards[0]
        assert first.image_url.startswith(
            "https://asset.homechef.com/cdn-cgi/image/w=550,f=auto,q=75/uploads/meal/plated/3429/"
        )
        assert first.image_url.endswith(".jpg")

    def test_rating_and_time_are_none(self):
        html = _load(CATEGORY_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")
        for card in page.cards:
            assert card.rating is None
            assert card.rating_count is None
            assert card.prep_time_minutes is None


class TestParseHomechefListingMenuFixture:
    def test_returns_88_cards(self):
        html = _load(MENU_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/menu")
        assert len(page.cards) == 88

    def test_slug_derived_from_url(self):
        html = _load(MENU_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/menu")
        # URL path is /menu so last segment is "menu"
        assert page.slug == "menu"

    def test_title_uses_amplitude_value(self):
        html = _load(MENU_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/menu")
        # First card is Turkey Breast Roast (no "with" → headline None)
        first = page.cards[0]
        assert first.name == "Turkey Breast Roast"
        assert first.headline is None

    def test_card_recipe_url_is_absolute(self):
        html = _load(MENU_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/menu")
        for card in page.cards:
            assert card.recipe_url.startswith(HOMECHEF_BASE_URL)

    def test_no_duplicate_external_ids(self):
        html = _load(MENU_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/menu")
        ids = [c.external_id for c in page.cards]
        assert len(ids) == len(set(ids))


class TestCardImage:
    def test_menu_cards_carry_a_photo_too(self):
        html = _load(MENU_FIXTURE)
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/menu")
        with_photo = [c for c in page.cards if c.image_url]
        assert len(with_photo) == len(page.cards)

    def test_a_card_without_a_photo_has_none(self):
        html = '<a href="/meals/plain-toast"><h2>Plain Toast</h2><p>with butter</p></a>'
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/breakfast")
        assert page.cards[0].image_url is None

    def test_falls_back_to_the_widest_when_none_is_wide_enough(self):
        html = (
            '<a href="/meals/small-photo">'
            '<img data-srcset="https://asset.homechef.com/a,b/small.jpg 100w, '
            'https://asset.homechef.com/a,b/medium.jpg 275w">'
            '<h2>Small Photo</h2></a>'
        )
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/breakfast")
        assert page.cards[0].image_url == "https://asset.homechef.com/a,b/medium.jpg"

    def test_ignores_a_srcset_that_is_not_a_web_address(self):
        html = (
            '<a href="/meals/odd"><img data-srcset="javascript:alert(1) 550w">'
            '<h2>Odd</h2></a>'
        )
        page = parse_homechef_listing(html, f"{HOMECHEF_BASE_URL}/recipes/breakfast")
        assert page.cards[0].image_url is None


class TestParseHomechefListingErrors:
    def test_raises_parse_error_when_no_meal_links(self):
        with pytest.raises(CrawlerParseError, match="No meal links"):
            parse_homechef_listing("<html><body>no meals here</body></html>", "https://example.com/recipes/chicken")


# ---------------------------------------------------------------------------
# HomeChefCrawler.fetch_collection — network mocked
# ---------------------------------------------------------------------------


class TestHomeChefCrawlerFetchCollection:
    def _make_response(self, html: str, status_code: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = html
        resp.raise_for_status = MagicMock()
        return resp

    def test_robots_disallow_raises_network_error(self):
        crawler = _make_crawler_no_robots()
        crawler.robots_parser = MagicMock()
        crawler.robots_parser.can_fetch.return_value = False
        with pytest.raises(CrawlerNetworkError, match="robots.txt disallows"):
            crawler.fetch_collection("customer-favorites", f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")

    def test_invalid_slug_raises_value_error(self):
        crawler = _make_crawler_no_robots()
        with pytest.raises(ValueError, match="Invalid collection slug"):
            crawler.fetch_collection("bad slug!", f"{HOMECHEF_BASE_URL}/recipes/bad-slug")

    def test_fetch_failure_raises_network_error(self):
        import requests.exceptions
        crawler = _make_crawler_no_robots()
        crawler.robots_parser = MagicMock()
        crawler.robots_parser.can_fetch.return_value = True
        crawler.rate_limiter = MagicMock()
        crawler.session = MagicMock()
        crawler.session.get.side_effect = requests.exceptions.ConnectionError("fail")
        with pytest.raises(CrawlerNetworkError, match="Failed to fetch"):
            crawler.fetch_collection("customer-favorites", f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")

    def test_slug_mismatch_raises_parse_error(self):
        # Serve a page whose URL path's last segment differs from requested slug.
        html = _load(CATEGORY_FIXTURE)
        # customer-favorites page served for "chicken" slug → mismatch
        crawler = _make_crawler_no_robots()
        crawler.robots_parser = MagicMock()
        crawler.robots_parser.can_fetch.return_value = True
        crawler.rate_limiter = MagicMock()
        crawler.session = MagicMock()
        crawler.session.get.return_value = self._make_response(html)
        with pytest.raises(CrawlerParseError, match="slug"):
            crawler.fetch_collection("chicken", f"{HOMECHEF_BASE_URL}/recipes/customer-favorites")

    def test_single_page_returns_cards(self):
        html = _load(CATEGORY_FIXTURE)
        crawler = _make_crawler_no_robots()
        crawler.robots_parser = MagicMock()
        crawler.robots_parser.can_fetch.return_value = True
        crawler.rate_limiter = MagicMock()
        crawler.session = MagicMock()
        crawler.session.get.return_value = self._make_response(html)
        # Patch _find_next_page to simulate no next page so only 1 HTTP call
        with patch.object(crawler, "_find_next_page", return_value=None):
            page = crawler.fetch_collection(
                "customer-favorites",
                f"{HOMECHEF_BASE_URL}/recipes/customer-favorites",
            )
        assert len(page.cards) == 24

    def test_pagination_stops_at_max_3_pages(self):
        html = _load(CATEGORY_FIXTURE)
        resp = self._make_response(html)
        crawler = _make_crawler_no_robots()
        crawler.robots_parser = MagicMock()
        crawler.robots_parser.can_fetch.return_value = True
        crawler.rate_limiter = MagicMock()
        crawler.session = MagicMock()
        crawler.session.get.return_value = resp
        # Always return a next-page URL so the crawler would loop forever without the cap.
        with patch.object(
            crawler, "_find_next_page",
            return_value=f"{HOMECHEF_BASE_URL}/recipes/customer-favorites?page=2",
        ):
            page = crawler.fetch_collection(
                "customer-favorites",
                f"{HOMECHEF_BASE_URL}/recipes/customer-favorites",
            )
        assert crawler.session.get.call_count == 3

    def test_menu_slug_fetches_single_page(self):
        html = _load(MENU_FIXTURE)
        resp = self._make_response(html)
        crawler = _make_crawler_no_robots()
        crawler.robots_parser = MagicMock()
        crawler.robots_parser.can_fetch.return_value = True
        crawler.rate_limiter = MagicMock()
        crawler.session = MagicMock()
        crawler.session.get.return_value = resp
        page = crawler.fetch_collection(MENU_SLUG, HOMECHEF_BASE_URL + "/menu")
        assert crawler.session.get.call_count == 1
        assert len(page.cards) == 88
