"""
Unit tests for HelloFresh collection page parsing.

Covers parse_collection_page (pure function) and HelloFreshCrawler.fetch_collection
(network method exercised via mocks).
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from src.services.crawlers.hellofresh_crawler import (
    HelloFreshCrawler,
    HF_IMAGE_PREFIX,
    parse_collection_page,
    _parse_prep_time,
    _strip_locale,
)
from src.services.crawlers.exceptions import CrawlerNetworkError, CrawlerParseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../fixtures/hellofresh_collection_vegetarian.html",
)


def _load_fixture() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return fh.read()


def _make_crawler_no_robots() -> HelloFreshCrawler:
    """Return a crawler with robots.txt fetch suppressed."""
    with patch.object(HelloFreshCrawler, "_configure_from_robots_txt"):
        return HelloFreshCrawler()


# ---------------------------------------------------------------------------
# Private-helper unit tests
# ---------------------------------------------------------------------------


class TestStripLocale:
    def test_strips_en_us(self):
        assert _strip_locale("5a1b2c3d4e5f6a7b8c9d0e1f-en-US") == "5a1b2c3d4e5f6a7b8c9d0e1f"

    def test_strips_de_de(self):
        assert _strip_locale("abc123def456abc123def456-de-DE") == "abc123def456abc123def456"

    def test_no_suffix_unchanged(self):
        assert _strip_locale("6b2c3d4e5f6a7b8c9d0e1f2a") == "6b2c3d4e5f6a7b8c9d0e1f2a"


class TestParsePrepTime:
    def test_minutes_only(self):
        assert _parse_prep_time("PT25M") == 25

    def test_hours_and_minutes(self):
        assert _parse_prep_time("PT1H5M") == 65

    def test_hours_only(self):
        assert _parse_prep_time("PT2H") == 120

    def test_none_input(self):
        assert _parse_prep_time(None) is None

    def test_empty_string(self):
        assert _parse_prep_time("") is None

    def test_unparseable(self):
        assert _parse_prep_time("30 minutes") is None


# ---------------------------------------------------------------------------
# parse_collection_page — fixture-based tests
# ---------------------------------------------------------------------------


class TestParseCollectionPageFixture:
    def test_returns_three_cards(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert len(page.cards) == 3

    def test_returns_two_children(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert len(page.children) == 2

    def test_collection_metadata(self):
        url = "https://www.hellofresh.com/recipes/vegetarian-recipes"
        page = parse_collection_page(_load_fixture(), url)
        assert page.name == "Vegetarian Recipes"
        assert page.slug == "vegetarian-recipes"
        assert page.url == url

    def test_first_card_locale_suffix_stripped(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        # Card 1 id in fixture is "5a1b2c3d4e5f6a7b8c9d0e1f-en-US"
        assert page.cards[0].external_id == "5a1b2c3d4e5f6a7b8c9d0e1f"

    def test_first_card_image_url_absolute(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[0].image_url.startswith(HF_IMAGE_PREFIX)
        assert page.cards[0].image_url == HF_IMAGE_PREFIX + "/image/zucchini-and-tomato-flatbreads-cf443dcd.jpg"

    def test_first_card_prep_time_minutes(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[0].prep_time_minutes == 25

    def test_second_card_prep_time_hours_and_minutes(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        # PT1H5M → 65 minutes
        assert page.cards[1].prep_time_minutes == 65

    def test_third_card_null_prep_time(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[2].prep_time_minutes is None

    def test_third_card_null_rating(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[2].rating is None
        assert page.cards[2].rating_count is None

    def test_third_card_null_headline(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[2].headline is None

    def test_first_card_rating(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[0].rating == 4.5
        assert page.cards[0].rating_count == 1823

    def test_children_names_and_slugs(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        slugs = {c.slug for c in page.children}
        names = {c.name for c in page.children}
        assert slugs == {"vegan-recipes", "quick-vegetarian"}
        assert names == {"Vegan Recipes", "Quick Vegetarian"}

    def test_recipe_url_preserved(self):
        page = parse_collection_page(_load_fixture(), "https://www.hellofresh.com/recipes/vegetarian-recipes")
        assert page.cards[0].recipe_url == (
            "https://www.hellofresh.com/recipes/zucchini-and-tomato-flatbreads-5a1b2c3d4e5f6a7b8c9d0e1f"
        )


# ---------------------------------------------------------------------------
# parse_collection_page — error / edge-case tests
# ---------------------------------------------------------------------------


class TestParseCollectionPageErrors:
    def test_missing_next_data_raises_parse_error(self):
        html = "<html><head></head><body><p>No data here.</p></body></html>"
        with pytest.raises(CrawlerParseError, match="__NEXT_DATA__"):
            parse_collection_page(html, "https://www.hellofresh.com/recipes/test")

    def test_invalid_json_raises_parse_error(self):
        html = '<html><body><script id="__NEXT_DATA__" type="application/json">{bad json}</script></body></html>'
        with pytest.raises(CrawlerParseError, match="not valid JSON"):
            parse_collection_page(html, "https://www.hellofresh.com/recipes/test")

    def test_missing_collection_key_raises_parse_error(self):
        html = '<html><body><script id="__NEXT_DATA__" type="application/json">{"props": {}}</script></body></html>'
        with pytest.raises(CrawlerParseError, match="ssrPayload.collection"):
            parse_collection_page(html, "https://www.hellofresh.com/recipes/test")

    def test_collection_url_card_is_skipped(self):
        """A card whose websiteUrl is a collection page is silently skipped."""
        import json as _json

        data = {
            "props": {
                "pageProps": {
                    "ssrPayload": {
                        "collection": {
                            "name": "Test",
                            "slug": "test",
                            "recipes": [
                                {
                                    "id": "aabbccddeeff001122334455",
                                    "name": "Real Recipe",
                                    "headline": None,
                                    "imagePath": "/image/real.jpg",
                                    "prepTime": "PT20M",
                                    "aggregateRating": 4.0,
                                    "aggregateRatingsCount": 100,
                                    "websiteUrl": "https://www.hellofresh.com/recipes/real-recipe-aabbccddeeff001122334455",
                                },
                                {
                                    "id": "bbccddeeff0011223344556",
                                    "name": "Oops Collection",
                                    "headline": None,
                                    "imagePath": "/image/oops.jpg",
                                    "prepTime": None,
                                    "aggregateRating": None,
                                    "aggregateRatingsCount": None,
                                    # This URL is a collection, not a recipe
                                    "websiteUrl": "https://www.hellofresh.com/recipes/vegetarian-recipes",
                                },
                            ],
                            "children": {"docs": []},
                        }
                    }
                }
            }
        }
        html = (
            '<html><body><script id="__NEXT_DATA__" type="application/json">'
            + _json.dumps(data)
            + '</script></body></html>'
        )
        page = parse_collection_page(html, "https://www.hellofresh.com/recipes/test")
        assert len(page.cards) == 1
        assert page.cards[0].name == "Real Recipe"


# ---------------------------------------------------------------------------
# fetch_collection — mock-based tests
# ---------------------------------------------------------------------------


class TestFetchCollection:
    def test_calls_robots_then_rate_limiter_then_session(self):
        """robots_parser.can_fetch and rate_limiter.wait_if_needed are called before session.get."""
        crawler = _make_crawler_no_robots()

        call_order = []

        crawler.robots_parser.can_fetch = MagicMock(
            side_effect=lambda url: call_order.append("robots") or True
        )
        crawler.rate_limiter.wait_if_needed = MagicMock(
            side_effect=lambda domain: call_order.append("rate_limiter")
        )

        mock_response = MagicMock()
        mock_response.text = _load_fixture()
        mock_response.raise_for_status = MagicMock()

        with patch.object(crawler.session, "get", return_value=mock_response) as mock_get:
            mock_get.side_effect = lambda url, **kw: (
                call_order.append("session_get") or mock_response
            )
            crawler.fetch_collection("vegetarian-recipes")

        assert call_order == ["robots", "rate_limiter", "session_get"]

    def test_robots_disallow_raises_network_error(self):
        crawler = _make_crawler_no_robots()
        crawler.robots_parser.can_fetch = MagicMock(return_value=False)

        with pytest.raises(CrawlerNetworkError, match="robots.txt disallows"):
            crawler.fetch_collection("vegetarian-recipes")

    def test_http_error_raises_network_error(self):
        import requests

        crawler = _make_crawler_no_robots()
        crawler.robots_parser.can_fetch = MagicMock(return_value=True)
        crawler.rate_limiter.wait_if_needed = MagicMock()

        with patch.object(
            crawler.session,
            "get",
            side_effect=requests.exceptions.ConnectionError("connection refused"),
        ):
            with pytest.raises(CrawlerNetworkError, match="connection refused"):
                crawler.fetch_collection("vegetarian-recipes")

    def test_returns_collection_page(self):
        crawler = _make_crawler_no_robots()
        crawler.robots_parser.can_fetch = MagicMock(return_value=True)
        crawler.rate_limiter.wait_if_needed = MagicMock()

        mock_response = MagicMock()
        mock_response.text = _load_fixture()
        mock_response.raise_for_status = MagicMock()

        with patch.object(crawler.session, "get", return_value=mock_response):
            page = crawler.fetch_collection("vegetarian-recipes")

        assert page.name == "Vegetarian Recipes"
        assert len(page.cards) == 3
        assert len(page.children) == 2

    def test_builds_correct_url(self):
        crawler = _make_crawler_no_robots()
        crawler.robots_parser.can_fetch = MagicMock(return_value=True)
        crawler.rate_limiter.wait_if_needed = MagicMock()

        mock_response = MagicMock()
        mock_response.text = _load_fixture()
        mock_response.raise_for_status = MagicMock()

        with patch.object(crawler.session, "get", return_value=mock_response) as mock_get:
            crawler.fetch_collection("vegetarian-recipes")

        called_url = mock_get.call_args[0][0]
        assert called_url == "https://www.hellofresh.com/recipes/vegetarian-recipes"
