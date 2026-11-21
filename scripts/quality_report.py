"""
Quality report CLI for FreshUp.

Prints extraction coverage and recommendation balance stats to stdout.

Usage:
    DATABASE_URL=sqlite:////path/to/freshup.db .venv/bin/python scripts/quality_report.py
    DATABASE_URL=sqlite:////path/to/freshup.db .venv/bin/python scripts/quality_report.py --user sarah@freshup.dev
"""

from __future__ import annotations

import argparse
import os
import sys

# Put the repo root on sys.path so src.* imports resolve when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.database import init_engine, get_session_factory
from src.services.quality_report import extraction_report, recommendation_report


def _print_extraction(report) -> None:
    print("=" * 60)
    print("EXTRACTION REPORT")
    print("=" * 60)
    for s in report.sources:
        print(f"\nSource: {s.source_type}  ({s.card_count} cards)")
        print(f"  image_url       {s.pct_image:5.1f}%")
        print(f"  prep_time       {s.pct_prep_time:5.1f}%")
        print(f"  ingredient_keys {s.pct_ingredient_keys:5.1f}%")
        print(f"  3+ keys         {s.pct_3plus_keys:5.1f}%")
        if s.top_unmapped_words:
            print("  Top unmapped words (across all sources):")
            for word, count in s.top_unmapped_words[:10]:
                print(f"    {word:<20} {count}")
        for w in s.warnings:
            print(f"  WARNING: {w}")
    print()


def _print_recommendations(report, filter_user: str | None) -> None:
    print("=" * 60)
    print("RECOMMENDATION REPORT")
    print("=" * 60)
    for stats in report.users:
        if filter_user and stats.label not in (filter_user, "synthetic"):
            continue
        print(f"\nUser: {stats.label}")
        print(f"  Distinct cuisines in top 20: {stats.distinct_cuisines}")
        if stats.max_ingredient_key:
            print(
                f"  Dominant ingredient: {stats.max_ingredient_key} "
                f"({stats.max_ingredient_share:.0%} of top 20)"
            )
        print("  Source shares:")
        for src, share in sorted(stats.source_shares.items(), key=lambda x: -x[1]):
            print(f"    {src:<25} {share:.0%}")
        print(f"  Top 20 recommendations:")
        for i, item in enumerate(stats.top20, 1):
            cuisines = ", ".join(item.cuisine_keys) or "—"
            print(f"    {i:2}. [{item.reason:<7}] {item.name[:45]:<45}  {item.source_type}")
            print(f"        cuisines: {cuisines}")
        print(f"  Week ({len(stats.week)} days):")
        for day in stats.week:
            cuisines = ", ".join(day.cuisine_keys) or "—"
            print(f"    {day.day_name:<10}  {day.name[:45]:<45}  {day.source_type}  [{cuisines}]")
        for w in stats.warnings:
            print(f"  WARNING: {w}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="FreshUp quality report")
    parser.add_argument("--user", help="Show recommendations for this user email only")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required.", file=sys.stderr)
        sys.exit(1)

    init_engine(database_url)
    factory = get_session_factory()
    db = factory()
    try:
        ext_report = extraction_report(db)
        _print_extraction(ext_report)

        # recommendation_report needs a user argument; pass the first real user
        # or a synthetic one when no --user flag is given.
        from src.db.models.user import User as UserModel
        if args.user:
            user = db.query(UserModel).filter(UserModel.email == args.user).first()
            if not user:
                print(f"ERROR: user '{args.user}' not found.", file=sys.stderr)
                sys.exit(1)
        else:
            user = db.query(UserModel).first()

        rec_report = recommendation_report(user, db)
        _print_recommendations(rec_report, filter_user=args.user)
    finally:
        db.close()


if __name__ == "__main__":
    main()
