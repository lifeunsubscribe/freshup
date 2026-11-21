"""
Quality report service for FreshUp.

Provides two read-only report functions:

- extraction_report(db): per-source card extraction coverage stats and
  the top-20 ingredient words that have no vocabulary key.
- recommendation_report(user, db): top-20 recommendations with source
  shares, cuisine variety, and ingredient dominance metrics; also runs
  select_week for one full simulated week.

Both functions make no writes; callers may pass a read-only session.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from src.services.plan_week import week_start_of


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SourceExtractionStats:
    source_type: str
    card_count: int
    pct_image: float          # 0..100
    pct_prep_time: float
    pct_ingredient_keys: float
    pct_3plus_keys: float
    top_unmapped_words: list[tuple[str, int]]  # (word, count), descending
    warnings: list[str]


@dataclass
class ExtractionReport:
    sources: list[SourceExtractionStats]


@dataclass
class TopItem:
    name: str
    source_type: str
    reason: str
    cuisine_keys: list[str]
    main_ingredient_key: Optional[str]


@dataclass
class WeekDay:
    day_name: str
    name: str
    source_type: str
    cuisine_keys: list[str]


@dataclass
class UserRecommendationStats:
    label: str                          # user email or "synthetic"
    top20: list[TopItem]
    source_shares: dict[str, float]     # source_type -> share 0..1
    distinct_cuisines: int
    max_ingredient_share: float         # 0..1
    max_ingredient_key: Optional[str]
    week: list[WeekDay]
    warnings: list[str]


@dataclass
class RecommendationReport:
    users: list[UserRecommendationStats]


# ---------------------------------------------------------------------------
# Extraction report
# ---------------------------------------------------------------------------

# Words too short or too generic to be useful vocabulary signals.
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "in", "of", "with", "to", "from",
    "for", "some", "any", "all", "one", "two", "plus",
    "fresh", "frozen", "cooked", "dried", "raw", "ground", "sliced",
    "diced", "chopped", "minced", "whole", "half", "about",
    "large", "medium", "small", "extra",
    "cup", "cups", "tbsp", "tsp", "oz", "lb", "lbs", "g", "kg", "ml",
    "pkg", "package", "can", "jar", "bottle", "bag", "bags",
    "piece", "pieces", "clove", "cloves", "sprig", "sprigs",
    "slice", "slices", "head", "bunch", "pinch",
})


def extraction_report(db: Session) -> ExtractionReport:
    """
    Return per-source extraction coverage stats for all SourceRecipeCards.

    Unmapped words are computed from RecipeIngredient.ingredient_name: each
    name is tokenised into individual words; words whose standalone keys_for
    result is empty are "unmapped".  Stop words and words shorter than 4
    characters are excluded.
    """
    from src.db.models.source_catalog import SourceRecipeCard
    from src.db.models.recipe_ingredient import RecipeIngredient
    from src.services.ingredient_keys import keys_for

    # --- Gather cards grouped by source_type ---
    cards = db.query(SourceRecipeCard).all()

    source_buckets: dict[str, list] = {}
    for card in cards:
        source_buckets.setdefault(card.source_type, []).append(card)

    # --- Unmapped word counts across all ingredient names ---
    ingredient_names = [
        row.ingredient_name
        for row in db.query(RecipeIngredient).all()
    ]
    unmapped_counter: Counter = Counter()
    for name in ingredient_names:
        for word in re.split(r"[\s,/()&]+", name.lower()):
            word = word.strip("-")
            if len(word) < 4 or word in _STOP_WORDS:
                continue
            if not keys_for(word):
                unmapped_counter[word] += 1

    top_unmapped = unmapped_counter.most_common(20)

    # --- Per-source stats ---
    sources: list[SourceExtractionStats] = []
    coverage_threshold = 60.0

    for source_type, source_cards in sorted(source_buckets.items()):
        n = len(source_cards)
        n_image = sum(1 for c in source_cards if c.image_url)
        n_prep = sum(1 for c in source_cards if c.prep_time_minutes is not None)
        n_keys = sum(1 for c in source_cards if c.ingredient_keys is not None)
        n_3plus = sum(
            1 for c in source_cards
            if c.ingredient_keys is not None and len(c.ingredient_keys) >= 3
        )

        pct_image = 100.0 * n_image / n if n else 0.0
        pct_prep = 100.0 * n_prep / n if n else 0.0
        pct_keys = 100.0 * n_keys / n if n else 0.0
        pct_3plus = 100.0 * n_3plus / n if n else 0.0

        warnings: list[str] = []
        if pct_image < coverage_threshold:
            warnings.append(
                f"image_url coverage {pct_image:.0f}% < {coverage_threshold:.0f}%"
            )
        if pct_prep < coverage_threshold:
            warnings.append(
                f"prep_time_minutes coverage {pct_prep:.0f}% < {coverage_threshold:.0f}%"
            )
        if pct_keys < coverage_threshold:
            warnings.append(
                f"ingredient_keys coverage {pct_keys:.0f}% < {coverage_threshold:.0f}%"
            )

        sources.append(SourceExtractionStats(
            source_type=source_type,
            card_count=n,
            pct_image=pct_image,
            pct_prep_time=pct_prep,
            pct_ingredient_keys=pct_keys,
            pct_3plus_keys=pct_3plus,
            top_unmapped_words=top_unmapped,
            warnings=warnings,
        ))

    return ExtractionReport(sources=sources)


# ---------------------------------------------------------------------------
# Recommendation report
# ---------------------------------------------------------------------------

def _item_top_ingredient(keys: set[str]) -> Optional[str]:
    """Return the first ingredient: key found, or None."""
    for k in sorted(keys):
        if k.startswith("ingredient:"):
            return k[len("ingredient:"):]
    return None


def _next_week_start() -> date:
    """The first day of the plan week after the current one."""
    return week_start_of(date.today()) + timedelta(days=7)


def _build_user_stats(label: str, user, db: Session) -> UserRecommendationStats:
    from src.services.recommendation_service import rank_candidates
    from src.services.taste_service import card_keys, recipe_keys
    from src.services.card_tags import overlap_tags
    from src.services.meal_plan_service import select_week

    ranked = rank_candidates(user, db, limit=20)

    # Build overlap keys for card candidates
    card_ids = [r.card.id for r in ranked if r.kind == "card" and r.card is not None]
    card_overlap = overlap_tags(db, card_ids) if card_ids else {}

    # Collect per-item metadata
    top20: list[TopItem] = []
    source_counter: Counter = Counter()
    cuisine_set: set[str] = set()
    ingredient_counter: Counter = Counter()

    for item in ranked:
        if item.kind == "card" and item.card is not None:
            source = item.card.source_type
            keys = card_keys(item.card, card_overlap.get(item.card.id, set()))
            name = item.card.name
        else:
            source = getattr(item.recipe, "source_type", "manual") or "manual"
            keys = recipe_keys(item.recipe)
            name = item.recipe.name

        cuisines = [k[len("cuisine:"):] for k in keys if k.startswith("cuisine:")]
        main_ing = _item_top_ingredient(keys)

        top20.append(TopItem(
            name=name,
            source_type=source,
            reason=item.reason,
            cuisine_keys=cuisines,
            main_ingredient_key=main_ing,
        ))
        source_counter[source] += 1
        cuisine_set.update(cuisines)
        if main_ing:
            ingredient_counter[main_ing] += 1

    total = len(top20)
    source_shares = {s: c / total for s, c in source_counter.items()} if total else {}

    max_ingredient_share = 0.0
    max_ingredient_key: Optional[str] = None
    if total and ingredient_counter:
        top_ing, top_count = ingredient_counter.most_common(1)[0]
        max_ingredient_share = top_count / total
        max_ingredient_key = top_ing

    # --- Select week ---
    week_start = _next_week_start()
    week_choices = select_week(user, db, week_start)

    week: list[WeekDay] = []
    week_card_ids = [
        c.item.card.id
        for c in week_choices
        if c.item.kind == "card" and c.item.card is not None
    ]
    week_card_overlap = overlap_tags(db, week_card_ids) if week_card_ids else {}

    for choice in week_choices:
        item = choice.item
        if item.kind == "card" and item.card is not None:
            w_source = item.card.source_type
            w_keys = card_keys(item.card, week_card_overlap.get(item.card.id, set()))
            w_name = item.card.name
        else:
            w_source = getattr(item.recipe, "source_type", "manual") or "manual"
            w_keys = recipe_keys(item.recipe)
            w_name = item.recipe.name

        w_cuisines = [k[len("cuisine:"):] for k in w_keys if k.startswith("cuisine:")]
        week.append(WeekDay(
            day_name=choice.day.strftime("%A"),
            name=w_name,
            source_type=w_source,
            cuisine_keys=w_cuisines,
        ))

    # --- Warnings ---
    warnings: list[str] = []

    # Source skew: one source above 70% while another has 20+ candidates.
    # The ranker's diversity cap is 75%, so 80% is unreachable; use 70%.
    if total:
        all_sources_in_db = _all_source_candidate_counts(user, db)
        for src, share in source_shares.items():
            if share > 0.70:
                other_has_20plus = any(
                    count >= 20 for s, count in all_sources_in_db.items() if s != src
                )
                if other_has_20plus:
                    warnings.append(
                        f"source skew: {src} holds {share:.0%} of top 20 "
                        f"while another source has 20+ candidates"
                    )

    if len(cuisine_set) < 3:
        warnings.append(
            f"low cuisine variety: only {len(cuisine_set)} distinct cuisine(s) in top 20"
        )

    if max_ingredient_share > 0.40 and max_ingredient_key:
        warnings.append(
            f"ingredient dominance: '{max_ingredient_key}' appears in "
            f"{max_ingredient_share:.0%} of top 20"
        )

    return UserRecommendationStats(
        label=label,
        top20=top20,
        source_shares=source_shares,
        distinct_cuisines=len(cuisine_set),
        max_ingredient_share=max_ingredient_share,
        max_ingredient_key=max_ingredient_key,
        week=week,
        warnings=warnings,
    )


def _all_source_candidate_counts(user, db: Session) -> dict[str, int]:
    """Count all ranking candidates per source (for skew warning only)."""
    from src.db.models.source_catalog import (
        SourceCollection, SourceCollectionCard, SourceRecipeCard,
    )

    top_level = (
        db.query(SourceCollection)
        .filter(SourceCollection.parent_slug.is_(None))
        .all()
    )
    if not top_level:
        return {}

    collection_ids = [c.id for c in top_level]
    rows = (
        db.query(SourceRecipeCard, SourceCollection.slug)
        .join(SourceCollectionCard, SourceCollectionCard.card_id == SourceRecipeCard.id)
        .join(SourceCollection, SourceCollection.id == SourceCollectionCard.collection_id)
        .filter(SourceCollectionCard.collection_id.in_(collection_ids))
        .all()
    )
    seen: set = set()
    counts: Counter = Counter()
    for card, _ in rows:
        if card.id not in seen:
            seen.add(card.id)
            counts[card.source_type] += 1
    return dict(counts)


def recommendation_report(user, db: Session) -> RecommendationReport:
    """
    Return recommendation stats for the given user and a synthetic new user.

    The synthetic user has no history (empty affinities) and no allergies,
    representing a brand-new account with no personalisation signals.
    """
    from src.db.models.user import User as UserModel

    users_stats: list[UserRecommendationStats] = []

    # Real users from the database
    all_users = db.query(UserModel).all()
    for db_user in all_users:
        label = getattr(db_user, "email", str(db_user.id))
        stats = _build_user_stats(label, db_user, db)
        users_stats.append(stats)

    # Synthetic brand-new user: UUID does not exist in DB → user_affinities returns {}
    from types import SimpleNamespace
    synthetic = SimpleNamespace(
        id=uuid4(),
        taste_preferences={},
        allergies=[],
        email="synthetic",
    )
    users_stats.append(_build_user_stats("synthetic", synthetic, db))

    return RecommendationReport(users=users_stats)
