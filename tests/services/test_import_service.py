"""
Unit tests for recipe import service.

Tests cover:
- URL normalization for deduplication
- Single recipe import (success, duplicate, errors)
- Batch import with rate limiting
- Ingredient parsing and handling of unparseable ingredients
- Error handling (scraping errors, database errors)
- Transaction rollback on failure

Note: All external HTTP requests and database operations are mocked.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from uuid import uuid4

from src.services.import_service import (
    import_recipe_from_url,
    import_batch,
    _normalize_url,
)
from src.schemas.import_service import ImportResult, ImportStatus, BatchImportResult
from src.schemas.scraper import ScrapedRecipeData
from src.services.scraper_service import ScraperError, NetworkError
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient


class TestNormalizeUrl:
    """Tests for _normalize_url function."""

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is removed."""
        assert _normalize_url("  https://example.com/recipe  ") == "https://example.com/recipe"

    def test_lowercase_scheme_and_domain(self):
        """Test that scheme and domain are lowercased."""
        assert _normalize_url("HTTPS://EXAMPLE.COM/Recipe") == "https://example.com/Recipe"

    def test_removes_trailing_slash(self):
        """Test that trailing slash is removed from path."""
        assert _normalize_url("https://example.com/recipe/") == "https://example.com/recipe"
        assert _normalize_url("https://example.com/") == "https://example.com"

    def test_preserves_query_parameters(self):
        """Test that query parameters are preserved."""
        assert _normalize_url("https://example.com/recipe?id=123") == "https://example.com/recipe?id=123"

    def test_preserves_fragment(self):
        """Test that URL fragments are preserved."""
        assert _normalize_url("https://example.com/recipe#section") == "https://example.com/recipe#section"

    def test_complete_normalization(self):
        """Test complete normalization with all rules applied."""
        url = "  HTTPS://Example.COM/Recipe/?id=123#top  "
        expected = "https://example.com/Recipe?id=123#top"
        assert _normalize_url(url) == expected

    def test_handles_invalid_url_gracefully(self):
        """Test that invalid URLs are returned as-is (after strip)."""
        invalid_url = "not-a-url"
        # Should return stripped version without crashing
        result = _normalize_url(invalid_url)
        assert result == invalid_url


class TestImportRecipeFromUrl:
    """Tests for import_recipe_from_url function."""

    @patch('src.services.import_service.scrape_recipe')
    @patch('src.services.import_service.parse_ingredient')
    def test_successful_import(self, mock_parse_ingredient, mock_scrape_recipe):
        """Test successful recipe import with all data."""
        # Mock database session
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No duplicate

        # Mock scraper response
        mock_scrape_recipe.return_value = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            title="Test Recipe",
            image_url="https://example.com/image.jpg",
            prep_time_minutes=10,
            cook_time_minutes=20,
            total_time_minutes=30,
            servings=4,
            ingredients=["1 cup flour", "2 eggs"],
            instructions=["Mix ingredients", "Bake at 350F"],
            tags=["dessert"],
            nutrients={"calories": "200"},
        )

        # Mock ingredient parser
        mock_parse_ingredient.side_effect = [
            {
                'quantity': 1.0,
                'unit': 'cup',
                'ingredient_name': 'flour',
                'preparation': '',
                'is_optional': False,
                'raw_text': '1 cup flour',
            },
            {
                'quantity': 2.0,
                'unit': '',
                'ingredient_name': 'eggs',
                'preparation': '',
                'is_optional': False,
                'raw_text': '2 eggs',
            },
        ]

        # Mock recipe creation
        mock_recipe = Mock()
        mock_recipe.id = uuid4()
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Capture the recipe object that gets created
        created_recipe = None
        def capture_recipe(obj):
            nonlocal created_recipe
            if isinstance(obj, Recipe):
                created_recipe = obj
                created_recipe.id = mock_recipe.id

        mock_db.add.side_effect = capture_recipe

        # Execute import
        result = import_recipe_from_url("https://example.com/recipe", mock_db)

        # Assertions
        assert result.status == ImportStatus.success
        assert result.recipe_id == mock_recipe.id
        assert result.error_message is None
        assert len(result.warnings) == 0

        # Verify database operations
        mock_db.add.call_count >= 1  # Recipe + ingredients
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @patch('src.services.import_service.scrape_recipe')
    def test_duplicate_recipe_skipped(self, mock_scrape_recipe):
        """Test that duplicate recipes are detected and skipped."""
        # Mock database session with existing recipe
        existing_recipe_id = uuid4()
        mock_existing = Mock()
        mock_existing.id = existing_recipe_id

        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        # Execute import
        result = import_recipe_from_url("https://example.com/recipe", mock_db)

        # Assertions
        assert result.status == ImportStatus.duplicate
        assert result.recipe_id == existing_recipe_id
        assert result.error_message is None

        # Verify scraper was NOT called
        mock_scrape_recipe.assert_not_called()

    @patch('src.services.import_service.scrape_recipe')
    def test_scraper_error_returns_error_status(self, mock_scrape_recipe):
        """Test that scraper errors are caught and returned as error status."""
        # Mock database session (no duplicate)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock scraper to raise error
        mock_scrape_recipe.side_effect = NetworkError("Connection timeout")

        # Execute import
        result = import_recipe_from_url("https://example.com/recipe", mock_db)

        # Assertions
        assert result.status == ImportStatus.error
        assert result.recipe_id is None
        assert "Connection timeout" in result.error_message

    @patch('src.services.import_service.scrape_recipe')
    @patch('src.services.import_service.parse_ingredient')
    def test_unparseable_ingredient_handled_gracefully(self, mock_parse_ingredient, mock_scrape_recipe):
        """Test that unparseable ingredients are imported with warning."""
        # Mock database session
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock scraper response
        mock_scrape_recipe.return_value = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            title="Test Recipe",
            servings=4,
            ingredients=["Salt to taste"],  # Unparseable (no quantity)
            instructions=["Cook it"],
        )

        # Mock ingredient parser returning qty=0 (unparseable)
        mock_parse_ingredient.return_value = {
            'quantity': 0.0,  # Parser returns 0 for unparseable
            'unit': '',
            'ingredient_name': 'Salt to taste',
            'preparation': '',
            'is_optional': True,
            'raw_text': 'Salt to taste',
        }

        # Mock recipe creation
        mock_recipe = Mock()
        mock_recipe.id = uuid4()
        created_objects = []

        def capture_objects(obj):
            created_objects.append(obj)
            if isinstance(obj, Recipe):
                obj.id = mock_recipe.id

        mock_db.add.side_effect = capture_objects
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Execute import
        result = import_recipe_from_url("https://example.com/recipe", mock_db)

        # Assertions
        assert result.status == ImportStatus.success
        assert len(result.warnings) == 1
        assert "Unparseable ingredient" in result.warnings[0]
        assert "Salt to taste" in result.warnings[0]

        # Verify ingredient was created with sentinel value 0.001
        ingredients = [obj for obj in created_objects if isinstance(obj, RecipeIngredient)]
        assert len(ingredients) == 1
        assert ingredients[0].quantity == 0.001

    @patch('src.services.import_service.scrape_recipe')
    @patch('src.services.import_service.parse_ingredient')
    def test_database_error_triggers_rollback(self, mock_parse_ingredient, mock_scrape_recipe):
        """Test that database errors trigger rollback and return error status."""
        # Mock database session
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock scraper response
        mock_scrape_recipe.return_value = ScrapedRecipeData(
            source_url="https://example.com/recipe",
            source_type="url_import",
            title="Test Recipe",
            servings=4,
            ingredients=["1 cup flour"],
            instructions=["Mix it"],
        )

        # Mock ingredient parser
        mock_parse_ingredient.return_value = {
            'quantity': 1.0,
            'unit': 'cup',
            'ingredient_name': 'flour',
            'preparation': '',
            'is_optional': False,
            'raw_text': '1 cup flour',
        }

        # Mock database to raise error on commit
        from sqlalchemy.exc import SQLAlchemyError
        mock_db.commit.side_effect = SQLAlchemyError("Database constraint violation")
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.rollback = Mock()

        # Execute import
        result = import_recipe_from_url("https://example.com/recipe", mock_db)

        # Assertions
        assert result.status == ImportStatus.error
        assert result.recipe_id is None
        assert "Database error" in result.error_message

        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    @patch('src.services.import_service.scrape_recipe')
    @patch('src.services.import_service.parse_ingredient')
    def test_recipe_created_with_system_import_fields(self, mock_parse_ingredient, mock_scrape_recipe):
        """Test that imported recipes have correct source_type and created_by=None."""
        # Mock database session
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock scraper response
        mock_scrape_recipe.return_value = ScrapedRecipeData(
            source_url="https://www.hellofresh.com/recipe",
            source_type="hellofresh_web",
            title="Test Recipe",
            servings=4,
            ingredients=["1 cup flour"],
            instructions=["Mix it"],
        )

        # Mock ingredient parser
        mock_parse_ingredient.return_value = {
            'quantity': 1.0,
            'unit': 'cup',
            'ingredient_name': 'flour',
            'preparation': '',
            'is_optional': False,
            'raw_text': '1 cup flour',
        }

        # Mock recipe creation
        created_recipe = None
        def capture_recipe(obj):
            nonlocal created_recipe
            if isinstance(obj, Recipe):
                created_recipe = obj
                created_recipe.id = uuid4()

        mock_db.add.side_effect = capture_recipe
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Execute import
        result = import_recipe_from_url("https://www.hellofresh.com/recipe", mock_db)

        # Assertions
        assert result.status == ImportStatus.success
        assert created_recipe is not None
        assert created_recipe.source_type == "hellofresh_web"
        assert created_recipe.created_by is None  # System-imported


class TestImportBatch:
    """Tests for import_batch function."""

    @patch('src.services.import_service.import_recipe_from_url')
    @patch('src.services.import_service.time.sleep')
    def test_batch_import_all_success(self, mock_sleep, mock_import):
        """Test batch import with all successful imports."""
        # Mock individual imports
        recipe_id_1 = uuid4()
        recipe_id_2 = uuid4()
        recipe_id_3 = uuid4()

        mock_import.side_effect = [
            ImportResult(status=ImportStatus.success, recipe_id=recipe_id_1, source_url="https://example.com/1"),
            ImportResult(status=ImportStatus.success, recipe_id=recipe_id_2, source_url="https://example.com/2"),
            ImportResult(status=ImportStatus.success, recipe_id=recipe_id_3, source_url="https://example.com/3"),
        ]

        # Mock database session
        mock_db = Mock()

        # Execute batch import
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]
        result = import_batch(urls, mock_db, delay_seconds=0.5)

        # Assertions
        assert result.total == 3
        assert result.imported == 3
        assert result.duplicates == 0
        assert result.errors == 0
        assert len(result.results) == 3

        # Verify rate limiting (sleep called 2 times, not after last import)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.5)

    @patch('src.services.import_service.import_recipe_from_url')
    @patch('src.services.import_service.time.sleep')
    def test_batch_import_mixed_results(self, mock_sleep, mock_import):
        """Test batch import with mixed success, duplicate, and error results."""
        # Mock individual imports
        recipe_id = uuid4()
        mock_import.side_effect = [
            ImportResult(status=ImportStatus.success, recipe_id=recipe_id, source_url="https://example.com/1"),
            ImportResult(status=ImportStatus.duplicate, recipe_id=recipe_id, source_url="https://example.com/2"),
            ImportResult(status=ImportStatus.error, error_message="Scraping failed", source_url="https://example.com/3"),
            ImportResult(status=ImportStatus.success, recipe_id=uuid4(), source_url="https://example.com/4"),
        ]

        # Mock database session
        mock_db = Mock()

        # Execute batch import
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
            "https://example.com/4",
        ]
        result = import_batch(urls, mock_db, delay_seconds=0.1)

        # Assertions
        assert result.total == 4
        assert result.imported == 2
        assert result.duplicates == 1
        assert result.errors == 1
        assert len(result.results) == 4

        # Verify rate limiting
        assert mock_sleep.call_count == 3

    @patch('src.services.import_service.import_recipe_from_url')
    @patch('src.services.import_service.time.sleep')
    def test_batch_import_no_delay(self, mock_sleep, mock_import):
        """Test batch import with no rate limiting (delay_seconds=0)."""
        # Mock individual imports
        mock_import.side_effect = [
            ImportResult(status=ImportStatus.success, recipe_id=uuid4(), source_url="https://example.com/1"),
            ImportResult(status=ImportStatus.success, recipe_id=uuid4(), source_url="https://example.com/2"),
        ]

        # Mock database session
        mock_db = Mock()

        # Execute batch import with no delay
        urls = ["https://example.com/1", "https://example.com/2"]
        result = import_batch(urls, mock_db, delay_seconds=0)

        # Assertions
        assert result.total == 2
        assert result.imported == 2

        # Verify no sleep was called
        mock_sleep.assert_not_called()

    @patch('src.services.import_service.import_recipe_from_url')
    @patch('src.services.import_service.time.sleep')
    def test_batch_import_single_url_no_sleep(self, mock_sleep, mock_import):
        """Test that single URL batch import does not sleep."""
        # Mock individual import
        mock_import.return_value = ImportResult(
            status=ImportStatus.success,
            recipe_id=uuid4(),
            source_url="https://example.com/1"
        )

        # Mock database session
        mock_db = Mock()

        # Execute batch import with single URL
        urls = ["https://example.com/1"]
        result = import_batch(urls, mock_db, delay_seconds=1.0)

        # Assertions
        assert result.total == 1
        assert result.imported == 1

        # Verify no sleep (only 1 URL, no delay needed)
        mock_sleep.assert_not_called()

    @patch('src.services.import_service.import_recipe_from_url')
    def test_batch_import_empty_list(self, mock_import):
        """Test batch import with empty URL list."""
        # Mock database session
        mock_db = Mock()

        # Execute batch import with empty list
        result = import_batch([], mock_db)

        # Assertions
        assert result.total == 0
        assert result.imported == 0
        assert result.duplicates == 0
        assert result.errors == 0
        assert len(result.results) == 0

        # Verify no imports were attempted
        mock_import.assert_not_called()
