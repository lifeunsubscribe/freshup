"""
Transcript recipe extraction service for FreshUp (Phase 2D).

Sends transcript chunks one at a time to the local LLM to extract ingredients
and cooking actions. Amount verification ensures the model cannot invent
quantities that were never spoken. A final merge call assembles the notes
into a ScrapedRecipeData that the existing URL-import path can consume.
"""

import re
from typing import Optional

from src.db.models.recipe import SourceType
from src.schemas.scraper import ScrapedRecipeData
from src.schemas.transcript import ChunkNotes, IngredientMention, NotesResult, RecipeDraft
from src.services.ingredient_keys import keys_for
from src.services.llm.client import LLMClient
from src.services.llm.exceptions import LLMResponseError, LLMUnavailableError
from src.services.llm.prompts.transcript import (
    CHUNK_SYSTEM_PROMPT,
    MERGE_SYSTEM_PROMPT,
    create_chunk_prompt,
    create_merge_prompt,
)
from src.services.recipe_themes import TAG_INDEX, VALUE_LABELS, normalize_tag
from src.services.scraper_service import MAX_SCRAPED_TAGS
from src.services.transcript_filter import MEASURE_WORDS, Chunk, CondensedTranscript, condense_transcript

# Maps spoken number words to their digit equivalents.
# Multi-word phrases must come before single-word entries so the substitution
# loop replaces them in one pass (longest-match ordering).
NUMBER_WORDS: list[tuple[str, str]] = [
    # fractions and mixed numbers
    ("one and a half", "1 1/2"),
    ("two and a half", "2 1/2"),
    ("three and a half", "3 1/2"),
    ("four and a half", "4 1/2"),
    ("half an", "1/2"),
    ("half a", "1/2"),
    # teens
    ("nineteen", "19"),
    ("eighteen", "18"),
    ("seventeen", "17"),
    ("sixteen", "16"),
    ("fifteen", "15"),
    ("fourteen", "14"),
    ("thirteen", "13"),
    ("twelve", "12"),
    ("eleven", "11"),
    # tens
    ("sixty", "60"),
    ("fifty", "50"),
    ("forty", "40"),
    ("thirty", "30"),
    ("twenty", "20"),
    ("ten", "10"),
    # single digits
    ("nine", "9"),
    ("eight", "8"),
    ("seven", "7"),
    ("six", "6"),
    ("five", "5"),
    ("four", "4"),
    ("three", "3"),
    ("two", "2"),
    ("one", "1"),
]

# Matches a leading "a" or "an" only when the next word is a measure word.
# Used in normalise_amount to convert "a tablespoon" → "1 tablespoon".
_A_MEASURE_RE = re.compile(
    r'^an?\s+(' + '|'.join(re.escape(w) for w in MEASURE_WORDS) + r')\b',
    re.IGNORECASE,
)

# Matches any sequence of digits (and slashes/spaces for fractions) in a string.
_DIGIT_RE = re.compile(r'\d')


def normalise_amount(amount: str) -> str:
    """
    Rewrite spoken number words as digits so the ingredient parser can read them.

    Examples:
        "two tablespoons"      → "2 tablespoons"
        "one and a half pounds" → "1 1/2 pounds"
        "half a cup"           → "1/2 cup"
        "a tablespoon"         → "1 tablespoon"
        "a pinch"              → "1 pinch"
        "two big handfuls"     → "2 big handfuls"
    """
    result = amount.strip()

    # "a/an + measure word" → "1 <measure word>"
    m = _A_MEASURE_RE.match(result)
    if m:
        result = "1 " + result[m.start(1):]

    # Replace multi-word and single-word number phrases (longest first).
    for word, digit in NUMBER_WORDS:
        result = re.sub(rf'\b{re.escape(word)}\b', digit, result, flags=re.IGNORECASE)

    return result


def spoken_amount(amount: Optional[str], chunk_text: str) -> Optional[str]:
    """
    Return *amount* normalised if the chunk actually contains it; otherwise None.

    Comparison rules:
    - If amount contains a digit, normalise both sides and compare the numeric
      tokens.  "2 tablespoons" matches a chunk that says "two tablespoons".
    - If amount has no digit at all, it must appear word-for-word in the chunk.
    - A kept amount is returned normalised.

    Args:
        amount: The amount string the LLM returned (may be None).
        chunk_text: The raw transcript chunk text.

    Returns:
        The normalised amount if confirmed spoken, or None.
    """
    if amount is None:
        return None

    normalised = normalise_amount(amount)
    normalised_chunk = normalise_amount(chunk_text)

    if _DIGIT_RE.search(normalised):
        # Extract every numeric token from the normalised amount.
        # A numeric token is a digit string or a simple fraction (d/d).
        numeric_tokens = re.findall(r'\d+/\d+|\d+', normalised)
        if not numeric_tokens:
            return None
        # All numeric tokens must appear in the normalised chunk.
        for token in numeric_tokens:
            # Match as a whole token (not a substring of a larger number).
            if not re.search(r'\b' + re.escape(token) + r'\b', normalised_chunk):
                return None
        return normalised
    else:
        # No digits — the phrase must appear literally in the chunk (case-insensitive).
        if re.search(re.escape(amount.strip()), chunk_text, re.IGNORECASE):
            return normalised
        return None


async def extract_chunk_notes(chunk: Chunk, client: LLMClient) -> ChunkNotes:
    """
    Ask the LLM for ingredients and actions in a single transcript chunk.

    Each ingredient's amount is verified against the chunk text before returning.
    Ingredients with an empty name and empty actions are dropped.

    Args:
        chunk: A single Chunk from transcript_filter.
        client: LLMClient instance (must not be None).

    Returns:
        ChunkNotes with verified ingredients and actions.

    Raises:
        LLMUnavailableError: Propagated from client if the model is unreachable.
        LLMResponseError: Propagated from client if the model's reply is invalid.
    """
    prompt = create_chunk_prompt(chunk.text)
    result: ChunkNotes = await client.complete(
        prompt=prompt,
        system_prompt=CHUNK_SYSTEM_PROMPT,
        response_schema=ChunkNotes,
    )

    verified_ingredients: list[IngredientMention] = []
    for ingredient in result.ingredients:
        if not ingredient.name.strip():
            continue
        verified_amount = spoken_amount(ingredient.amount, chunk.text)
        verified_ingredients.append(
            IngredientMention(name=ingredient.name, amount=verified_amount)
        )

    cleaned_actions = [a for a in result.actions if a.strip()]

    return ChunkNotes(ingredients=verified_ingredients, actions=cleaned_actions)


async def extract_all_notes(
    chunks: list[Chunk],
    client: LLMClient,
) -> NotesResult:
    """
    Extract cooking notes from every chunk, one at a time (sequential).

    The local model is a single CPU worker; concurrent calls would queue anyway.

    Error handling:
    - LLMResponseError for a chunk: skip it, increment failed_chunks, continue.
    - LLMUnavailableError: propagate immediately; no further chunks are sent so
      the caller can retry the whole job once the model is back.

    Args:
        chunks: Ordered list of Chunk objects from transcript_filter.
        client: LLMClient instance.

    Returns:
        NotesResult with one ChunkNotes per successful chunk (in order) and a
        count of skipped chunks.

    Raises:
        LLMUnavailableError: If the model is unreachable at any point.
    """
    notes: list[ChunkNotes] = []
    failed = 0

    for chunk in chunks:
        try:
            chunk_notes = await extract_chunk_notes(chunk, client)
            notes.append(chunk_notes)
        except LLMResponseError:
            failed += 1
        # LLMUnavailableError intentionally propagates unchanged.

    return NotesResult(notes=notes, failed_chunks=failed)


# Maximum characters in the merge prompt. Exceeding this raises TranscriptTooLongError
# rather than truncating — the sanitiser would silently cut the last steps off at 16,000.
MERGE_INPUT_BUDGET = 12000

# Tag labels from the cuisine/dish/diet/meal_type themes, built once at import time.
_MERGE_ALLOWED_TAGS: list[str] = [
    label
    for theme in ("cuisine", "dish", "diet", "meal_type")
    for label in VALUE_LABELS[theme].values()
]

# Canonical keys in the ingredient theme — used to auto-add ingredient tags.
_INGREDIENT_THEME_KEYS: frozenset[str] = frozenset(VALUE_LABELS["ingredient"].keys())


class NoRecipeFoundError(Exception):
    """Raised when the notes contain no ingredients and no actions."""


class TranscriptTooLongError(Exception):
    """Raised when the merge prompt exceeds MERGE_INPUT_BUDGET characters."""


def merge_ingredients(notes: list[ChunkNotes]) -> list[IngredientMention]:
    """
    Combine per-chunk ingredient mentions into one list.

    Two mentions are the same ingredient when keys_for(name) returns the same
    non-empty set, or when their lowercased names are identical. The first
    non-None amount wins; order follows first mention.
    """
    # identity -> (insertion_order, canonical_name, amount)
    seen: dict[tuple, tuple[int, str, Optional[str]]] = {}

    for chunk_notes in notes:
        for ing in chunk_notes.ingredients:
            name = ing.name.strip()
            if not name:
                continue
            ingredient_keys = keys_for(name)
            if ingredient_keys:
                identity: tuple = ("keys", frozenset(ingredient_keys))
            else:
                identity = ("name", name.lower())

            if identity in seen:
                order, existing_name, existing_amount = seen[identity]
                if existing_amount is None and ing.amount is not None:
                    seen[identity] = (order, existing_name, ing.amount)
            else:
                seen[identity] = (len(seen), name, ing.amount)

    ordered = sorted(seen.values(), key=lambda t: t[0])
    return [IngredientMention(name=name, amount=amount) for _, name, amount in ordered]


def _build_tags(
    draft_tags: list[str],
    merged: list[IngredientMention],
) -> list[str]:
    """
    Build the final tag list from model reply tags and ingredient keys.

    Model tags are kept only when normalize_tag(tag) is in TAG_INDEX.
    Ingredient keys from VALUE_LABELS["ingredient"] are added for each merged
    ingredient. Deduplicated by canonical value, model tags first.
    """
    seen_values: set[str] = set()
    tags: list[str] = []

    for tag in draft_tags:
        entry = TAG_INDEX.get(normalize_tag(tag))
        if entry is not None and entry[1] not in seen_values:
            seen_values.add(entry[1])
            tags.append(tag)

    for mention in merged:
        for key in keys_for(mention.name):
            if key in _INGREDIENT_THEME_KEYS and key not in seen_values:
                seen_values.add(key)
                tags.append(key)

    return tags[:MAX_SCRAPED_TAGS]


async def notes_to_recipe(
    notes: list[ChunkNotes],
    client: LLMClient,
    *,
    source_url: str,
    title_hint: Optional[str] = None,
    author: Optional[str] = None,
) -> ScrapedRecipeData:
    """
    Merge per-chunk notes into a single ScrapedRecipeData via one LLM merge call.

    Args:
        notes: Ordered list of ChunkNotes from extract_all_notes.
        client: LLMClient instance.
        source_url: URL to record as the recipe's source.
        title_hint: Caller-supplied title (e.g. video title); wins over model's.
        author: Attribution string passed through to ScrapedRecipeData.

    Returns:
        ScrapedRecipeData ready for the existing import path.

    Raises:
        NoRecipeFoundError: If the notes hold no ingredients and no actions.
        TranscriptTooLongError: If the merge prompt exceeds MERGE_INPUT_BUDGET.
        LLMUnavailableError: Propagated from the client.
        LLMResponseError: Propagated from the client.
    """
    all_actions: list[str] = [action for chunk in notes for action in chunk.actions]
    merged = merge_ingredients(notes)

    if not merged and not all_actions:
        raise NoRecipeFoundError("Notes contain no ingredients and no actions.")

    prompt = create_merge_prompt(
        ingredients=[m.name for m in merged],
        actions=all_actions,
        allowed_tags=_MERGE_ALLOWED_TAGS,
    )

    if len(prompt) > MERGE_INPUT_BUDGET:
        raise TranscriptTooLongError(
            f"Merge prompt is {len(prompt)} characters, exceeds budget of {MERGE_INPUT_BUDGET}."
        )

    draft: RecipeDraft = await client.complete(
        prompt=prompt,
        system_prompt=MERGE_SYSTEM_PROMPT,
        response_schema=RecipeDraft,
    )

    # Format ingredient strings: "<amount> <name>" or "<name>" when no amount.
    ingredient_strings: list[str] = [
        f"{m.amount} {m.name}" if m.amount else m.name
        for m in merged
    ]

    title = title_hint or draft.title or None

    return ScrapedRecipeData(
        source_url=source_url,
        source_type=SourceType.url_import.value,
        title=title,
        image_url=None,
        site_name=None,
        author=author,
        servings=draft.servings,
        ingredients=ingredient_strings,
        instructions=draft.steps[:30],
        tags=_build_tags(draft.tags, merged),
    )


async def transcript_to_recipe(
    raw: str,
    client: LLMClient,
    *,
    source_url: str,
    title_hint: Optional[str] = None,
    author: Optional[str] = None,
    skip_ranges: tuple = (),
) -> ScrapedRecipeData:
    """
    Full pipeline: condense transcript, extract chunk notes, merge into recipe.

    Args:
        raw: Raw transcript string (timestamped or plain text).
        client: LLMClient instance.
        source_url: URL to record as the recipe's source.
        title_hint: Caller-supplied title; wins over model's title.
        author: Attribution string passed through to ScrapedRecipeData.
        skip_ranges: Pairs of (start_seconds, end_seconds) to cut before filtering.

    Returns:
        ScrapedRecipeData ready for the existing import path.

    Raises:
        NoRecipeFoundError: If nothing cooking-related survives filtering.
        TranscriptTooLongError: If the merge prompt exceeds MERGE_INPUT_BUDGET.
        LLMUnavailableError: Propagated from the client.
    """
    condensed: CondensedTranscript = condense_transcript(raw, skip_ranges=skip_ranges)
    notes_result: NotesResult = await extract_all_notes(condensed.chunks, client)
    return await notes_to_recipe(
        notes_result.notes,
        client,
        source_url=source_url,
        title_hint=title_hint,
        author=author,
    )
