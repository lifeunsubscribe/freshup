"""
Recipe URL discovery crawlers for FreshUp.

Provides crawlers for discovering recipe URLs from external recipe sites
via sitemap.xml parsing and paginated category crawling, with support for
rate limiting and robots.txt compliance.
"""

from src.services.crawlers.hellofresh_crawler import HelloFreshCrawler

__all__ = ['HelloFreshCrawler']
