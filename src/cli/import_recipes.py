"""
Recipe import CLI for FreshUp.

Command-line tool for bulk recipe imports from external sources.
Supports both URL discovery (via crawlers) and single URL imports.

Usage:
    # Discover and import from HelloFresh (max 50 recipes)
    python -m src.cli.import_recipes --source hellofresh --max 50

    # Discover and import from Kitchen Sanctuary (max 50 recipes)
    python -m src.cli.import_recipes --source kitchen_sanctuary --max 50

    # Import a single URL
    python -m src.cli.import_recipes --url "https://www.hellofresh.com/recipes/..."
"""

import argparse
import sys
import logging
from typing import Optional

from src.db.database import init_engine, get_session_factory
from src.services.import_service import import_recipe_from_url, import_batch
from src.services.crawlers.hellofresh_crawler import HelloFreshCrawler
from src.services.crawlers.kitchen_sanctuary_crawler import KitchenSanctuaryCrawler
from src.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_from_source(source: str, max_recipes: int) -> None:
    """
    Discover and import recipes from a source.

    Args:
        source: Source name (hellofresh or kitchen_sanctuary)
        max_recipes: Maximum number of recipes to import
    """
    logger.info(f"Starting discovery and import from {source} (max: {max_recipes})")

    # Initialize database
    settings = get_settings()
    init_engine(settings.database_url)
    SessionFactory = get_session_factory()

    try:
        # Discover URLs using crawler
        if source == "hellofresh":
            crawler = HelloFreshCrawler()
            urls = crawler.discover_recipe_urls()
        elif source == "kitchen_sanctuary":
            crawler = KitchenSanctuaryCrawler()
            urls = crawler.discover_recipe_urls()
        else:
            logger.error(f"Invalid source: {source}")
            sys.exit(1)

        logger.info(f"Discovered {len(urls)} URLs from {source}")

        # Limit to max_recipes
        urls_to_import = urls[:max_recipes]
        logger.info(f"Importing {len(urls_to_import)} recipes (limited by max_recipes={max_recipes})")

        # Import recipes in batch
        with SessionFactory() as db:
            result = import_batch(urls_to_import, db, delay_seconds=1.0)

            logger.info("=" * 60)
            logger.info("IMPORT SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total URLs processed: {result.total}")
            logger.info(f"Successfully imported: {result.imported}")
            logger.info(f"Duplicates skipped: {result.duplicates}")
            logger.info(f"Errors: {result.errors}")
            logger.info("=" * 60)

            if result.errors > 0:
                logger.warning("Some imports failed. Review logs for details.")
                # Log first 5 errors for quick debugging
                error_results = [r for r in result.results if r.status == "error"][:5]
                for i, err_result in enumerate(error_results, 1):
                    logger.warning(f"Error {i}: {err_result.source_url} - {err_result.error_message}")

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)


def import_from_url(url: str) -> None:
    """
    Import a recipe from a single URL.

    Args:
        url: Recipe URL to import
    """
    logger.info(f"Importing recipe from URL: {url}")

    # Initialize database
    settings = get_settings()
    init_engine(settings.database_url)
    SessionFactory = get_session_factory()

    try:
        with SessionFactory() as db:
            result = import_recipe_from_url(url, db)

            logger.info("=" * 60)
            logger.info("IMPORT RESULT")
            logger.info("=" * 60)
            logger.info(f"Status: {result.status}")
            logger.info(f"URL: {result.source_url}")

            if result.status == "success":
                logger.info(f"Recipe ID: {result.recipe_id}")
                if result.warnings:
                    logger.warning("Warnings:")
                    for warning in result.warnings:
                        logger.warning(f"  - {warning}")
            elif result.status == "duplicate":
                logger.info(f"Recipe already exists (ID: {result.recipe_id})")
            elif result.status == "error":
                logger.error(f"Error: {result.error_message}")
                sys.exit(1)

            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import recipes from external sources into FreshUp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Bulk import from HelloFresh (max 50 recipes)
  python -m src.cli.import_recipes --source hellofresh --max 50

  # Bulk import from Kitchen Sanctuary (max 100 recipes)
  python -m src.cli.import_recipes --source kitchen_sanctuary --max 100

  # Import a single recipe URL
  python -m src.cli.import_recipes --url "https://www.hellofresh.com/recipes/chicken-tikka"
        """
    )

    # Mutually exclusive group: either --source or --url
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--source",
        type=str,
        choices=["hellofresh", "kitchen_sanctuary"],
        help="Source to import from (discovers URLs via crawler)"
    )
    group.add_argument(
        "--url",
        type=str,
        help="Single recipe URL to import"
    )

    # Optional arguments
    parser.add_argument(
        "--max",
        type=int,
        default=50,
        help="Maximum number of recipes to import from source (default: 50, only used with --source)"
    )

    args = parser.parse_args()

    # Execute appropriate import mode
    if args.source:
        import_from_source(args.source, args.max)
    elif args.url:
        if args.max != 50:
            logger.warning("--max argument is ignored when using --url (single import mode)")
        import_from_url(args.url)


if __name__ == "__main__":
    main()
