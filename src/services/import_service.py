"""
Recipe import orchestration service for FreshUp.

Coordinates scraping, parsing, deduplication, and database persistence for
recipe imports from external URLs. Supports both single URL and batch imports
with rate limiting.
"""

import logging
import time
from typing import Optional
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.services.scraper_service import scrape_recipe, ScraperError
from src.services.ingredient_parser import parse_ingredient
from src.schemas.import_service import ImportResult, ImportStatus, BatchImportResult
from src.db.models.recipe import Recipe
from src.db.models.recipe_ingredient import RecipeIngredient

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication comparisons.

    Normalization rules:
    - Strip whitespace
    - Convert scheme and domain to lowercase
    - Remove trailing slash from path
    - Preserve query parameters and fragments

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string

    Example:
        >>> _normalize_url("  HTTPS://Example.com/Recipe/  ")
        "https://example.com/recipe"
    """
    url = url.strip()
    try:
        parsed = urlparse(url)

        # If no scheme or netloc, the URL is invalid - return as-is
        if not parsed.scheme or not parsed.netloc:
            return url

        # Normalize scheme and netloc (domain) to lowercase
        normalized_scheme = parsed.scheme.lower()
        normalized_netloc = parsed.netloc.lower()
        # Remove trailing slash from path
        normalized_path = parsed.path.rstrip('/') if parsed.path else ''

        # Reconstruct URL
        normalized = f"{normalized_scheme}://{normalized_netloc}{normalized_path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        if parsed.fragment:
            normalized += f"#{parsed.fragment}"

        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL, using original: {e}")
        return url


def import_recipe_from_url(url: str, db: Session) -> ImportResult:
    """
    Import a recipe from a URL into the database.

    Pipeline:
    1. Normalize and deduplicate against existing recipes by source_url
    2. Scrape recipe data using scraper_service
    3. Parse ingredients using ingredient_parser
    4. Map to RecipeCreate and RecipeIngredientCreate schemas
    5. Save to database (Recipe + RecipeIngredient records)

    Scraped recipes are system-imported (created_by=None) and globally readable.

    Args:
        url: Recipe URL to import
        db: Database session

    Returns:
        ImportResult with status, recipe_id (on success), warnings, and errors

    Note:
        - Unparseable ingredients are imported with qty=0.001 (workaround for
          validation requiring qty > 0). A warning is added to ImportResult.
        - Duplicate detection is case-insensitive and URL-normalized.
        - All database operations are wrapped in a transaction.
    """
    normalized_url = _normalize_url(url)
    warnings = []

    # Step 1: Check for existing recipe with this source_url (deduplication)
    try:
        # Check both normalized URL and original URL to handle existing unnormalized data
        existing_recipe = db.query(Recipe).filter(
            (Recipe.source_url == normalized_url) | (Recipe.source_url == url.strip())
        ).first()

        if existing_recipe:
            logger.info(f"Recipe already exists for URL: {normalized_url}")
            return ImportResult(
                status=ImportStatus.duplicate,
                recipe_id=existing_recipe.id,
                warnings=[],
                error_message=None,
                source_url=url,
            )
    except SQLAlchemyError as e:
        logger.error(f"Database error during deduplication check: {e}", exc_info=True)
        return ImportResult(
            status=ImportStatus.error,
            recipe_id=None,
            warnings=[],
            error_message=f"Database error during deduplication: {str(e)}",
            source_url=url,
        )

    # Step 2: Scrape recipe data
    try:
        scraped_data = scrape_recipe(url)
    except ScraperError as e:
        logger.warning(f"Scraper error for URL {url}: {e}")
        return ImportResult(
            status=ImportStatus.error,
            recipe_id=None,
            warnings=[],
            error_message=f"Scraping failed: {str(e)}",
            source_url=url,
        )
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
        return ImportResult(
            status=ImportStatus.error,
            recipe_id=None,
            warnings=[],
            error_message=f"Unexpected scraping error: {str(e)}",
            source_url=url,
        )

    # Step 3: Parse ingredients
    parsed_ingredients = []
    for raw_ingredient in scraped_data.ingredients:
        parsed = parse_ingredient(raw_ingredient)

        # Handle unparseable ingredients (qty=0 from parser)
        # Use sentinel value 0.001 as workaround for validation requiring qty > 0
        quantity = parsed['quantity']
        if quantity == 0.0:
            quantity = 0.001
            warnings.append(f"Unparseable ingredient (using minimal qty): {raw_ingredient}")

        parsed_ingredients.append({
            'ingredient_name': parsed['ingredient_name'] or raw_ingredient,
            'quantity': quantity,
            'unit': parsed['unit'] or '',
            'is_optional': parsed['is_optional'],
        })

    # Step 4 & 5: Create Recipe and RecipeIngredient records in transaction
    try:
        # Create Recipe
        new_recipe = Recipe(
            name=scraped_data.title or "Untitled Recipe",
            source_type=scraped_data.source_type,
            source_url=normalized_url,
            source_image=scraped_data.image_url,
            prep_time_minutes=scraped_data.prep_time_minutes,
            cook_time_minutes=scraped_data.cook_time_minutes,
            base_servings=scraped_data.servings or 4,
            steps=scraped_data.instructions,
            tags=scraped_data.tags,
            nutritional_info=scraped_data.nutrients,
            created_by=None,  # System-imported recipe, no owner
        )

        db.add(new_recipe)
        db.flush()  # Get recipe.id for ingredients

        # Create RecipeIngredient records
        for parsed_ing in parsed_ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=new_recipe.id,
                ingredient_name=parsed_ing['ingredient_name'],
                quantity=parsed_ing['quantity'],
                unit=parsed_ing['unit'],
                is_optional=parsed_ing['is_optional'],
            )
            db.add(recipe_ingredient)

        # Commit transaction
        db.commit()
        db.refresh(new_recipe)

        logger.info(f"Successfully imported recipe {new_recipe.id} from {normalized_url}")
        return ImportResult(
            status=ImportStatus.success,
            recipe_id=new_recipe.id,
            warnings=warnings,
            error_message=None,
            source_url=url,
        )

    except IntegrityError as e:
        # Handle race condition: another process inserted same URL between check and commit
        db.rollback()
        logger.info(f"IntegrityError during import, checking for duplicate: {e}")

        try:
            # Query for the existing recipe that caused the integrity error
            # Check both normalized URL and original URL to handle existing unnormalized data
            existing_recipe = db.query(Recipe).filter(
                (Recipe.source_url == normalized_url) | (Recipe.source_url == url.strip())
            ).first()

            if existing_recipe:
                logger.info(f"Recipe already exists for URL (race condition): {normalized_url}")
                return ImportResult(
                    status=ImportStatus.duplicate,
                    recipe_id=existing_recipe.id,
                    warnings=[],
                    error_message=None,
                    source_url=url,
                )
        except SQLAlchemyError as query_error:
            logger.error(f"Error querying for duplicate after IntegrityError: {query_error}")

        # If we can't find the duplicate or there's another integrity issue, return error
        return ImportResult(
            status=ImportStatus.error,
            recipe_id=None,
            warnings=warnings,
            error_message=f"Database integrity error: {str(e)}",
            source_url=url,
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during recipe import: {e}", exc_info=True)
        return ImportResult(
            status=ImportStatus.error,
            recipe_id=None,
            warnings=warnings,
            error_message=f"Database error: {str(e)}",
            source_url=url,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during recipe import: {e}", exc_info=True)
        return ImportResult(
            status=ImportStatus.error,
            recipe_id=None,
            warnings=warnings,
            error_message=f"Unexpected error: {str(e)}",
            source_url=url,
        )


def import_batch(
    urls: list[str],
    db: Session,
    delay_seconds: float = 1.0,
) -> BatchImportResult:
    """
    Import multiple recipes from a list of URLs.

    Processes URLs sequentially with rate limiting between requests to avoid
    overwhelming source websites. Each import is independent - failures do not
    stop processing of remaining URLs.

    Args:
        urls: List of recipe URLs to import
        db: Database session
        delay_seconds: Delay between imports in seconds (default: 1.0)

    Returns:
        BatchImportResult with aggregate statistics and individual results

    Note:
        - Rate limiting applies between ALL imports, not just successful ones
        - Database session is reused across all imports (ensure proper error handling)
        - No delay is applied after the final import
        - Invalid URLs (empty, whitespace-only, or malformed) are skipped with error status
    """
    results = []
    imported_count = 0
    duplicate_count = 0
    error_count = 0

    for i, url in enumerate(urls):
        # Validate URL input
        if not url or not url.strip():
            logger.warning(f"Skipping empty URL at index {i}")
            results.append(ImportResult(
                status=ImportStatus.error,
                recipe_id=None,
                warnings=[],
                error_message="Invalid URL: empty or whitespace-only",
                source_url=url or "",
            ))
            error_count += 1
            continue

        # Basic URL format validation
        url_stripped = url.strip()
        try:
            parsed = urlparse(url_stripped)
            if not parsed.scheme or not parsed.netloc:
                logger.warning(f"Skipping malformed URL at index {i}: {url_stripped}")
                results.append(ImportResult(
                    status=ImportStatus.error,
                    recipe_id=None,
                    warnings=[],
                    error_message="Invalid URL: missing scheme or domain",
                    source_url=url,
                ))
                error_count += 1
                continue
        except Exception as e:
            logger.warning(f"Skipping invalid URL at index {i}: {e}")
            results.append(ImportResult(
                status=ImportStatus.error,
                recipe_id=None,
                warnings=[],
                error_message=f"Invalid URL format: {str(e)}",
                source_url=url,
            ))
            error_count += 1
            continue
        # Import recipe
        result = import_recipe_from_url(url, db)
        results.append(result)

        # Update counters
        if result.status == ImportStatus.success:
            imported_count += 1
        elif result.status == ImportStatus.duplicate:
            duplicate_count += 1
        elif result.status == ImportStatus.error:
            error_count += 1

        # Rate limiting: sleep between requests (but not after the last one)
        if i < len(urls) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

    return BatchImportResult(
        total=len(urls),
        imported=imported_count,
        duplicates=duplicate_count,
        errors=error_count,
        results=results,
    )
