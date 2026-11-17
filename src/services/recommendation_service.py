"""
Recommendation ranking service.

rank_candidates() returns a scored and ordered list of catalog cards and
imported recipes for a user. Cards come from every top-level catalog
collection (SourceCollection with parent_slug IS NULL), one entry per card.
Persisted recipes with no linked card are also candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.recipe import Recipe
from src.db.models.source_catalog import (
    SourceCollection,
    SourceCollectionCard,
    SourceRecipeCard,
)
from src.db.models.user_cook_event import UserCookEvent
from src.services.card_tags import overlap_tags
from src.services.taste_service import (
    card_keys,
    is_blocked,
    is_card_blocked,
    popularity,
    recipe_keys,
    user_affinities,
)

_COOKED_EXCLUSION_DAYS = 14


@dataclass
class RankedItem:
    """A single ranked recommendation candidate."""

    kind: Literal["card", "recipe"]
    card: Optional[SourceRecipeCard]
    recipe: Optional[Recipe]
    score: float
    reason: Literal["taste", "popular", "explore"]


@dataclass
class _Candidate:
    """Internal working representation before slot assignment."""

    kind: str
    card: Optional[SourceRecipeCard]
    recipe: Optional[Recipe]
    score: float
    base_reason: str  # "taste" or "popular"
    pop_score: float  # used to pick explore candidates
    keys: frozenset  # taste keys for explore eligibility check
    source: str  # source_type, used for diversity rule


def rank_candidates(
    user,
    db: Session,
    limit: int,
    exclude_card_ids: Iterable[UUID] = (),
    exclude_recipe_ids: Iterable[UUID] = (),
) -> list[RankedItem]:
    """
    Return up to `limit` ranked recommendation candidates for the user.

    Scoring: with affinities, `0.75 * (taste + 1) / 2 + 0.25 * popularity`
    (reason `taste`); with no affinities, `popularity` (reason `popular`).
    Imported recipes without a card use popularity 0.5.

    Explore slots (every 5th position) take the most popular unplaced
    candidate whose keys have no entry in affinities; skipped when none exists.

    Diversity: when the last 3 picks share a source, the next pick comes from
    a different source if any unplaced candidate has one. Applied in a single
    pass that builds the list slot by slot.
    """
    exclude_card_set = set(exclude_card_ids)
    exclude_recipe_set = set(exclude_recipe_ids)

    # Top-level collections only (parent_slug IS NULL)
    top_level = (
        db.query(SourceCollection)
        .filter(SourceCollection.parent_slug.is_(None))
        .all()
    )
    if not top_level:
        return []

    collection_ids = [c.id for c in top_level]

    # Cards in top-level collections with their collection slugs
    rows = (
        db.query(SourceRecipeCard, SourceCollection.slug)
        .join(SourceCollectionCard, SourceCollectionCard.card_id == SourceRecipeCard.id)
        .join(SourceCollection, SourceCollection.id == SourceCollectionCard.collection_id)
        .filter(SourceCollectionCard.collection_id.in_(collection_ids))
        .all()
    )

    # Deduplicate: one entry per card, accumulate collection slugs
    card_map: dict[UUID, tuple[SourceRecipeCard, set[str]]] = {}
    for card, slug in rows:
        if card.id not in card_map:
            card_map[card.id] = (card, set())
        card_map[card.id][1].add(slug)

    # Source prior: mean star rating across all candidate cards per source_type
    source_ratings: dict[str, list[float]] = {}
    for card, _ in card_map.values():
        if card.rating is not None:
            source_ratings.setdefault(card.source_type, []).append(card.rating)
    source_prior: dict[str, Optional[float]] = {
        st: sum(rs) / len(rs) for st, rs in source_ratings.items()
    }

    # Recipe IDs cooked in the last 14 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=_COOKED_EXCLUSION_DAYS)
    recent_events = (
        db.query(UserCookEvent)
        .filter(
            UserCookEvent.user_id == user.id,
            UserCookEvent.cooked_at >= cutoff,
        )
        .all()
    )
    recently_cooked: set[UUID] = {ev.recipe_id for ev in recent_events}

    affinities = user_affinities(user.id, db)
    has_affinities = bool(affinities)

    # Overlap keys for all candidate cards
    all_card_ids = list(card_map.keys())
    card_overlap = overlap_tags(db, all_card_ids)

    candidates: list[_Candidate] = []

    # --- Card candidates ---
    for card_id, (card, slugs) in card_map.items():
        if card_id in exclude_card_set:
            continue
        # A card is "cooked" through its linked recipe
        if card.recipe_id is not None and card.recipe_id in recently_cooked:
            continue
        c_keys = card_keys(card, card_overlap.get(card_id, set()))
        if is_card_blocked(card, c_keys, user):
            continue
        st_prior = source_prior.get(card.source_type)
        pop = popularity(card, st_prior, slugs)
        if has_affinities:
            matched = [affinities[k] for k in c_keys if k in affinities]
            taste = sum(matched) / len(matched) if matched else 0.0
            sc = 0.75 * (taste + 1) / 2 + 0.25 * pop
            reason = "taste"
        else:
            sc = pop
            reason = "popular"
        candidates.append(_Candidate(
            kind="card",
            card=card,
            recipe=None,
            score=sc,
            base_reason=reason,
            pop_score=pop,
            keys=frozenset(c_keys),
            source=card.source_type,
        ))

    # --- Recipe candidates: persisted, not linked to any card ---
    linked_recipe_ids: set[UUID] = {
        card.recipe_id
        for card, _ in card_map.values()
        if card.recipe_id is not None
    }
    recipe_query = db.query(Recipe).filter(Recipe.is_persisted.is_(True))
    if linked_recipe_ids:
        recipe_query = recipe_query.filter(Recipe.id.notin_(linked_recipe_ids))
    for recipe in recipe_query.all():
        if recipe.id in exclude_recipe_set:
            continue
        if recipe.id in recently_cooked:
            continue
        if is_blocked(recipe, user):
            continue
        # Imported recipes without a card use a fixed popularity of 0.5
        pop = 0.5
        r_keys = recipe_keys(recipe)
        if has_affinities:
            matched = [affinities[k] for k in r_keys if k in affinities]
            taste = sum(matched) / len(matched) if matched else 0.0
            sc = 0.75 * (taste + 1) / 2 + 0.25 * pop
            reason = "taste"
        else:
            sc = pop
            reason = "popular"
        candidates.append(_Candidate(
            kind="recipe",
            card=None,
            recipe=recipe,
            score=sc,
            base_reason=reason,
            pop_score=pop,
            keys=frozenset(r_keys),
            source=getattr(recipe, "source_type", "manual"),
        ))

    # Sort by score descending before slot building
    candidates.sort(key=lambda c: c.score, reverse=True)

    return _build_list(candidates, affinities, limit)


def _build_list(
    candidates: list[_Candidate],
    affinities: dict,
    limit: int,
) -> list[RankedItem]:
    """
    Single-pass slot builder applying explore-slot and source-diversity rules.

    Both rules are applied together in one forward pass so they cannot undo
    each other. The diversity constraint is local: it only blocks a source when
    the last three placed items all share it and at least one unplaced candidate
    from a different source still exists. It does not balance sources globally.
    """
    result: list[RankedItem] = []
    # Parallel list of source strings for placed items (keeps diversity logic simple)
    placed_sources: list[str] = []
    unplaced = list(candidates)  # already sorted by score desc

    for slot in range(1, limit + 1):
        if not unplaced:
            break

        # Diversity: if last 3 picks share a source, block that source next
        blocked_source: Optional[str] = None
        if len(placed_sources) >= 3 and len(set(placed_sources[-3:])) == 1:
            bs = placed_sources[-1]
            if any(c.source != bs for c in unplaced):
                blocked_source = bs

        # Explore slot every 5th: most popular candidate with no affinity keys
        if slot % 5 == 0:
            explore_pick: Optional[_Candidate] = None
            best_pop = -1.0
            for c in unplaced:
                if blocked_source is not None and c.source == blocked_source:
                    continue
                if not any(k in affinities for k in c.keys):
                    if c.pop_score > best_pop:
                        best_pop = c.pop_score
                        explore_pick = c
            if explore_pick is not None:
                result.append(RankedItem(
                    kind=explore_pick.kind,
                    card=explore_pick.card,
                    recipe=explore_pick.recipe,
                    score=explore_pick.score,
                    reason="explore",
                ))
                placed_sources.append(explore_pick.source)
                unplaced.remove(explore_pick)
                continue
            # No explore candidate found; fall through to regular pick

        # Regular pick: highest-scored unplaced candidate not from blocked_source
        for c in unplaced:
            if blocked_source is None or c.source != blocked_source:
                result.append(RankedItem(
                    kind=c.kind,
                    card=c.card,
                    recipe=c.recipe,
                    score=c.score,
                    reason=c.base_reason,
                ))
                placed_sources.append(c.source)
                unplaced.remove(c)
                break

    return result
