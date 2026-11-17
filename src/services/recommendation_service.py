"""
Recommendation ranking service.

rank_candidates returns a scored, ordered list of catalog cards and unlinked
recipes for a user, applying taste blending, recency exclusion, blocking, an
exploration slot every five items, and source diversity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Collection, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.db.models.recipe import Recipe
from src.db.models.source_catalog import SourceCollection, SourceCollectionCard, SourceRecipeCard
from src.db.models.user_cook_event import UserCookEvent
from src.services.card_tags import overlap_tags, tags_from_text
from src.services.taste_service import (
    card_keys,
    is_blocked,
    is_card_blocked,
    popularity,
    recipe_keys,
    user_affinities,
)

_COOKED_WITHIN_DAYS = 14


@dataclass
class RankedItem:
    kind: str  # "card" | "recipe"
    card: Optional[SourceRecipeCard]
    recipe: Optional[Recipe]
    score: float
    reason: str  # "taste" | "popular" | "explore"
    # Internal fields used during ranking; not part of the public contract.
    _source_type: str = ""
    _pop_score: float = 0.0
    _keys: frozenset = frozenset()


def _candidate_id(item: RankedItem) -> tuple:
    return (item.kind, item.card.id if item.card else item.recipe.id)  # type: ignore[union-attr]


def _apply_source_diversity(items: list[RankedItem]) -> list[RankedItem]:
    """
    Reorder items so no source appears more than 3 times consecutively while
    another source still has candidates.
    """
    result: list[RankedItem] = []
    remaining = list(items)
    while remaining:
        if len(result) >= 3:
            last_src = result[-1]._source_type
            if result[-2]._source_type == last_src and result[-3]._source_type == last_src:
                other_idx = next(
                    (i for i, c in enumerate(remaining) if c._source_type != last_src),
                    None,
                )
                if other_idx is not None:
                    result.append(remaining.pop(other_idx))
                    continue
        result.append(remaining.pop(0))
    return result


def rank_candidates(
    user,
    db: Session,
    limit: int,
    exclude_card_ids: Collection[UUID] = (),
    exclude_recipe_ids: Collection[UUID] = (),
) -> list[RankedItem]:
    """
    Return up to *limit* recommended items for *user*, ranked by taste-blended
    popularity.

    Candidates: catalog cards in any top-level collection (parent_slug IS NULL)
    plus recipes that no card links to.  Blocked items and anything cooked
    within the last 14 days are excluded.

    Scoring:
    - With affinities:  0.75 * (taste + 1) / 2 + 0.25 * popularity, reason "taste"
    - Without:          popularity, reason "popular"
    - Unlinked recipes always use popularity = 0.5

    Every fifth slot (indices 4, 9, 14 …) is taken from the explore pool — the
    most popular candidate whose keys have no overlap with the user's affinity
    dict — reason "explore".  The slot is skipped when the pool is exhausted.

    Source diversity: no more than 3 consecutive items from the same source
    while another source still has candidates.
    """
    # --- Affinities -------------------------------------------------------
    affinities = user_affinities(user.id, db)
    has_affinities = bool(affinities)
    affinity_keys = set(affinities.keys())

    # --- Recently cooked IDs (last 14 days) --------------------------------
    cutoff = datetime.now(timezone.utc) - timedelta(days=_COOKED_WITHIN_DAYS)
    recently_cooked_ids: set[UUID] = {
        row[0]
        for row in db.query(UserCookEvent.recipe_id)
        .filter(UserCookEvent.user_id == user.id, UserCookEvent.cooked_at >= cutoff)
        .all()
    }

    # --- Top-level collection cards ----------------------------------------
    top_cards: list[SourceRecipeCard] = (
        db.query(SourceRecipeCard)
        .join(SourceCollectionCard, SourceCollectionCard.card_id == SourceRecipeCard.id)
        .join(SourceCollection, SourceCollection.id == SourceCollectionCard.collection_id)
        .filter(SourceCollection.parent_slug.is_(None))
        .options(joinedload(SourceRecipeCard.recipe_rel))
        .distinct()
        .all()
    )

    exclude_card_set = set(exclude_card_ids)
    exclude_recipe_set = set(exclude_recipe_ids)

    # --- Source priors for popularity -------------------------------------
    source_priors: dict[str, float] = {
        st: avg
        for st, avg in db.query(SourceRecipeCard.source_type, func.avg(SourceRecipeCard.rating))
        .filter(SourceRecipeCard.rating.isnot(None))
        .group_by(SourceRecipeCard.source_type)
        .all()
    }

    # --- Collection slugs per card (for featured-collection detection) ----
    card_ids = [c.id for c in top_cards]
    card_slugs: dict[UUID, set[str]] = {}
    if card_ids:
        for cid, slug in (
            db.query(SourceCollectionCard.card_id, SourceCollection.slug)
            .join(SourceCollection, SourceCollection.id == SourceCollectionCard.collection_id)
            .filter(SourceCollectionCard.card_id.in_(card_ids))
            .all()
        ):
            card_slugs.setdefault(cid, set()).add(slug)

    # --- Overlap keys for card taste scoring ------------------------------
    overlap = overlap_tags(db, card_ids)

    # --- Build candidates from catalog cards ------------------------------
    candidates: list[RankedItem] = []

    for card in top_cards:
        if card.id in exclude_card_set:
            continue
        if card.recipe_id in recently_cooked_ids:
            continue
        keys = card_keys(card, overlap.get(card.id, set()))
        if is_card_blocked(card, keys, user):
            continue

        pop = popularity(card, source_priors.get(card.source_type), card_slugs.get(card.id, set()))
        frozen_keys = frozenset(keys)

        if has_affinities:
            matched = [affinities[k] for k in keys if k in affinities]
            taste_score = sum(matched) / len(matched) if matched else 0.0
            combined = 0.75 * (taste_score + 1) / 2 + 0.25 * pop
            reason = "taste"
        else:
            combined = pop
            reason = "popular"

        item = RankedItem(
            kind="card", card=card, recipe=None,
            score=combined, reason=reason,
        )
        item._source_type = card.source_type
        item._pop_score = pop
        item._keys = frozen_keys
        candidates.append(item)

    # --- Build candidates from unlinked recipes ---------------------------
    linked_ids: set[UUID] = {
        row[0]
        for row in db.query(SourceRecipeCard.recipe_id)
        .filter(SourceRecipeCard.recipe_id.isnot(None))
        .all()
    }

    unlinked_query = db.query(Recipe)
    if linked_ids:
        unlinked_query = unlinked_query.filter(~Recipe.id.in_(linked_ids))
    unlinked_recipes: list[Recipe] = unlinked_query.all()

    for recipe in unlinked_recipes:
        if recipe.id in exclude_recipe_set:
            continue
        if recipe.id in recently_cooked_ids:
            continue
        keys = recipe_keys(recipe)
        if is_blocked(recipe, user):
            continue

        # Imported recipes without a card always use popularity 0.5
        pop = 0.5
        frozen_keys = frozenset(keys)

        if has_affinities:
            matched = [affinities[k] for k in keys if k in affinities]
            taste_score = sum(matched) / len(matched) if matched else 0.0
            combined = 0.75 * (taste_score + 1) / 2 + 0.25 * pop
            reason = "taste"
        else:
            combined = pop
            reason = "popular"

        item = RankedItem(
            kind="recipe", card=None, recipe=recipe,
            score=combined, reason=reason,
        )
        item._source_type = getattr(recipe, "source_type", "manual")
        item._pop_score = pop
        item._keys = frozen_keys
        candidates.append(item)

    # --- Sort by score descending -----------------------------------------
    candidates.sort(key=lambda c: c.score, reverse=True)

    # --- Explore pool: no affinity overlap, sorted by popularity ----------
    explore_pool = sorted(
        [c for c in candidates if not (c._keys & affinity_keys)],
        key=lambda c: c._pop_score,
        reverse=True,
    )

    # --- Build final list with explore insertion --------------------------
    placed: set[tuple] = set()
    result: list[RankedItem] = []
    main_idx = 0
    exp_idx = 0
    slot = 0

    while len(result) < limit:
        if slot % 5 == 4:
            # Advance to the next unplaced explore candidate
            while exp_idx < len(explore_pool) and _candidate_id(explore_pool[exp_idx]) in placed:
                exp_idx += 1
            if exp_idx < len(explore_pool):
                c = explore_pool[exp_idx]
                exp_idx += 1
                cid = _candidate_id(c)
                placed.add(cid)
                explore_item = RankedItem(
                    kind=c.kind, card=c.card, recipe=c.recipe,
                    score=c.score, reason="explore",
                )
                explore_item._source_type = c._source_type
                explore_item._pop_score = c._pop_score
                explore_item._keys = c._keys
                result.append(explore_item)
                slot += 1
                continue
            # Explore pool exhausted: fall through to main pool

        # Advance to the next unplaced main candidate
        while main_idx < len(candidates) and _candidate_id(candidates[main_idx]) in placed:
            main_idx += 1
        if main_idx >= len(candidates):
            break
        c = candidates[main_idx]
        main_idx += 1
        placed.add(_candidate_id(c))
        result.append(c)
        slot += 1

    # --- Source diversity post-pass ----------------------------------------
    return _apply_source_diversity(result)
