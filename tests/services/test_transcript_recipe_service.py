"""
Unit tests for transcript_recipe_service (Phase 2D).

All LLM calls use a synchronous stub that never touches Ollama.
"""

import pathlib
import pytest
from typing import Type
from unittest.mock import AsyncMock

from src.schemas.transcript import ChunkNotes, IngredientMention, NotesResult, RecipeDraft
from src.services.llm.client import LLMClient
from src.services.llm.exceptions import LLMResponseError, LLMUnavailableError
from src.services.recipe_themes import TAG_INDEX, normalize_tag
from src.services.transcript_filter import Chunk, condense_transcript
from src.services.transcript_recipe_service import (
    MERGE_INPUT_BUDGET,
    NoRecipeFoundError,
    TranscriptTooLongError,
    extract_all_notes,
    extract_chunk_notes,
    merge_ingredients,
    normalise_amount,
    notes_to_recipe,
    spoken_amount,
    transcript_to_recipe,
)

FIXTURE_PATH = (
    pathlib.Path(__file__).parent.parent / "fixtures" / "transcripts" / "weeknight_curry_panel.txt"
)


# ---------------------------------------------------------------------------
# Stub LLM client helpers
# ---------------------------------------------------------------------------

def _make_stub_client(return_value: ChunkNotes) -> LLMClient:
    """Return an AsyncMock LLMClient that always returns *return_value*."""
    stub = AsyncMock(spec=LLMClient)
    stub.complete = AsyncMock(return_value=return_value)
    return stub


def _make_error_stub(exc: Exception) -> LLMClient:
    """Return an AsyncMock LLMClient that always raises *exc*."""
    stub = AsyncMock(spec=LLMClient)
    stub.complete = AsyncMock(side_effect=exc)
    return stub


def _chunk(text: str, index: int = 0) -> Chunk:
    return Chunk(index=index, start_seconds=None, text=text)


def _make_merge_stub(draft: RecipeDraft) -> LLMClient:
    """
    Return an AsyncMock LLMClient that returns a RecipeDraft for the merge call
    and an empty ChunkNotes for any per-chunk call.
    """
    async def _side_effect(prompt, system_prompt, response_schema):
        if response_schema is RecipeDraft:
            return draft
        return ChunkNotes(ingredients=[], actions=[])

    stub = AsyncMock(spec=LLMClient)
    stub.complete = AsyncMock(side_effect=_side_effect)
    return stub


# ---------------------------------------------------------------------------
# normalise_amount
# ---------------------------------------------------------------------------

class TestNormaliseAmount:
    def test_two_tablespoons(self):
        assert normalise_amount("two tablespoons") == "2 tablespoons"

    def test_one_and_a_half_pounds(self):
        assert normalise_amount("one and a half pounds") == "1 1/2 pounds"

    def test_half_a_cup(self):
        assert normalise_amount("half a cup") == "1/2 cup"

    def test_a_tablespoon(self):
        assert normalise_amount("a tablespoon") == "1 tablespoon"

    def test_a_pinch(self):
        assert normalise_amount("a pinch") == "1 pinch"

    def test_two_big_handfuls(self):
        assert normalise_amount("two big handfuls") == "2 big handfuls"

    def test_already_digit(self):
        assert normalise_amount("2 tablespoons") == "2 tablespoons"

    def test_a_non_measure_word_unchanged(self):
        # "a splash" — splash is not in MEASURE_WORDS, so "a" is not rewritten
        result = normalise_amount("a splash")
        assert result == "a splash"


# ---------------------------------------------------------------------------
# spoken_amount — the eleven table rows
# ---------------------------------------------------------------------------

class TestSpokenAmount:
    # Row 1: "2 tablespoons" / "add two tablespoons of oil" → "2 tablespoons"
    def test_digit_matches_spoken_number(self):
        result = spoken_amount("2 tablespoons", "add two tablespoons of oil")
        assert result == "2 tablespoons"

    # Row 2: "1 cup" / "pour in some stock" → None
    def test_digit_not_in_chunk(self):
        result = spoken_amount("1 cup", "pour in some stock")
        assert result is None

    # Row 3: "a splash" / "add a splash of vinegar" → "a splash"
    def test_no_digit_phrase_present(self):
        result = spoken_amount("a splash", "add a splash of vinegar")
        assert result == "a splash"

    # Row 4: "a splash" / "add some vinegar" → None
    def test_no_digit_phrase_absent(self):
        result = spoken_amount("a splash", "add some vinegar")
        assert result is None

    # Row 5: "200 grams" / "two tablespoons of flour" → None
    def test_digit_number_mismatch(self):
        result = spoken_amount("200 grams", "two tablespoons of flour")
        assert result is None

    def test_none_amount_returns_none(self):
        result = spoken_amount(None, "add two tablespoons of oil")
        assert result is None

    def test_spoken_amount_returned_normalised(self):
        # The model returns "two cups"; it's in the chunk; result is normalised.
        result = spoken_amount("two cups", "add two cups of broth")
        assert result == "2 cups"


# ---------------------------------------------------------------------------
# extract_chunk_notes
# ---------------------------------------------------------------------------

class TestExtractChunkNotes:
    @pytest.mark.asyncio
    async def test_amount_not_spoken_becomes_none(self):
        """Ingredient amount the stub returns but the chunk never says → amount is None."""
        stub_result = ChunkNotes(
            ingredients=[IngredientMention(name="flour", amount="200 grams")],
            actions=["mix well"],
        )
        client = _make_stub_client(stub_result)
        chunk = _chunk("add a cup of flour and mix well")

        notes = await extract_chunk_notes(chunk, client)

        assert len(notes.ingredients) == 1
        assert notes.ingredients[0].name == "flour"
        assert notes.ingredients[0].amount is None

    @pytest.mark.asyncio
    async def test_spoken_amount_kept_normalised(self):
        stub_result = ChunkNotes(
            ingredients=[IngredientMention(name="oil", amount="two tablespoons")],
            actions=[],
        )
        client = _make_stub_client(stub_result)
        chunk = _chunk("add two tablespoons of olive oil")

        notes = await extract_chunk_notes(chunk, client)

        assert notes.ingredients[0].amount == "2 tablespoons"

    @pytest.mark.asyncio
    async def test_empty_name_ingredient_dropped(self):
        stub_result = ChunkNotes(
            ingredients=[
                IngredientMention(name="", amount=None),
                IngredientMention(name="salt", amount=None),
            ],
            actions=[],
        )
        client = _make_stub_client(stub_result)
        chunk = _chunk("add a pinch of salt")

        notes = await extract_chunk_notes(chunk, client)

        assert len(notes.ingredients) == 1
        assert notes.ingredients[0].name == "salt"

    @pytest.mark.asyncio
    async def test_empty_actions_dropped(self):
        stub_result = ChunkNotes(
            ingredients=[],
            actions=["", "stir well", "  "],
        )
        client = _make_stub_client(stub_result)
        chunk = _chunk("stir well")

        notes = await extract_chunk_notes(chunk, client)

        assert notes.actions == ["stir well"]

    @pytest.mark.asyncio
    async def test_llm_response_error_propagates(self):
        client = _make_error_stub(LLMResponseError("bad response"))
        chunk = _chunk("some text")

        with pytest.raises(LLMResponseError):
            await extract_chunk_notes(chunk, client)

    @pytest.mark.asyncio
    async def test_llm_unavailable_error_propagates(self):
        client = _make_error_stub(LLMUnavailableError("offline"))
        chunk = _chunk("some text")

        with pytest.raises(LLMUnavailableError):
            await extract_chunk_notes(chunk, client)


# ---------------------------------------------------------------------------
# extract_all_notes
# ---------------------------------------------------------------------------

class TestExtractAllNotes:
    @pytest.mark.asyncio
    async def test_three_chunks_second_raises_response_error(self):
        """
        Over three chunks where the second raises LLMResponseError,
        extract_all_notes returns two notes in order with failed_chunks == 1.
        """
        notes_a = ChunkNotes(ingredients=[IngredientMention(name="onion", amount=None)], actions=[])
        notes_c = ChunkNotes(ingredients=[IngredientMention(name="garlic", amount=None)], actions=[])

        call_count = 0

        async def _side_effect(prompt, system_prompt, response_schema):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise LLMResponseError("chunk 2 failed")
            return notes_a if call_count == 1 else notes_c

        stub = AsyncMock(spec=LLMClient)
        stub.complete = AsyncMock(side_effect=_side_effect)

        chunks = [_chunk("chunk a", 0), _chunk("chunk b", 1), _chunk("chunk c", 2)]

        result = await extract_all_notes(chunks, stub)

        assert result.failed_chunks == 1
        assert len(result.notes) == 2
        assert result.notes[0].ingredients[0].name == "onion"
        assert result.notes[1].ingredients[0].name == "garlic"

    @pytest.mark.asyncio
    async def test_first_chunk_unavailable_propagates_no_further_calls(self):
        """
        When the first chunk raises LLMUnavailableError it propagates and the
        other two chunks are never sent.
        """
        call_count = 0

        async def _side_effect(prompt, system_prompt, response_schema):
            nonlocal call_count
            call_count += 1
            raise LLMUnavailableError("model offline")

        stub = AsyncMock(spec=LLMClient)
        stub.complete = AsyncMock(side_effect=_side_effect)

        chunks = [_chunk("a", 0), _chunk("b", 1), _chunk("c", 2)]

        with pytest.raises(LLMUnavailableError):
            await extract_all_notes(chunks, stub)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_all_successful_returns_all_notes(self):
        notes = ChunkNotes(ingredients=[], actions=["stir"])
        client = _make_stub_client(notes)
        chunks = [_chunk("a", 0), _chunk("b", 1)]

        result = await extract_all_notes(chunks, client)

        assert result.failed_chunks == 0
        assert len(result.notes) == 2

    @pytest.mark.asyncio
    async def test_empty_chunks_list(self):
        client = _make_stub_client(ChunkNotes())
        result = await extract_all_notes([], client)
        assert result.failed_chunks == 0
        assert result.notes == []


# ---------------------------------------------------------------------------
# merge_ingredients
# ---------------------------------------------------------------------------

class TestMergeIngredients:
    def _notes(self, *chunk_data) -> list[ChunkNotes]:
        """Build ChunkNotes list from (name, amount) tuples per chunk."""
        result = []
        for items in chunk_data:
            ings = [IngredientMention(name=n, amount=a) for n, a in items]
            result.append(ChunkNotes(ingredients=ings, actions=[]))
        return result

    def test_same_key_merges_keeps_first_amount(self):
        """garlic with 3 cloves + garlic cloves with no amount → one entry with the amount."""
        notes = self._notes(
            [("garlic", "3 cloves")],
            [("garlic cloves", None)],
        )
        merged = merge_ingredients(notes)
        assert len(merged) == 1
        assert merged[0].amount == "3 cloves"

    def test_same_key_first_amount_none_then_has_amount(self):
        """First mention has no amount; second has one — second amount is kept."""
        notes = self._notes(
            [("garlic cloves", None)],
            [("garlic", "3 cloves")],
        )
        merged = merge_ingredients(notes)
        assert len(merged) == 1
        assert merged[0].amount == "3 cloves"

    def test_order_follows_first_mention(self):
        """Ingredients appear in the order they were first mentioned across chunks."""
        notes = self._notes(
            [("onion", "1"), ("garlic", "3 cloves")],
            [("onion", None), ("chicken", None)],
        )
        merged = merge_ingredients(notes)
        names = [m.name for m in merged]
        assert names[0] == "onion"
        assert names[1] == "garlic"
        assert names[2] == "chicken"

    def test_lowercased_name_identity_when_no_keys(self):
        """Unknown ingredients match by lowercase name."""
        notes = self._notes(
            [("Truffle Oil", "1 tsp")],
            [("truffle oil", None)],
        )
        merged = merge_ingredients(notes)
        assert len(merged) == 1
        assert merged[0].amount == "1 tsp"

    def test_different_ingredients_stay_separate(self):
        notes = self._notes(
            [("chicken", None), ("onion", "1")],
        )
        merged = merge_ingredients(notes)
        assert len(merged) == 2

    def test_empty_name_ingredient_skipped(self):
        notes = self._notes([("", None), ("salt", None)])
        merged = merge_ingredients(notes)
        assert len(merged) == 1
        assert merged[0].name == "salt"

    def test_empty_notes_returns_empty(self):
        assert merge_ingredients([]) == []

    def test_no_ingredients_in_notes_returns_empty(self):
        notes = [ChunkNotes(ingredients=[], actions=["stir well"])]
        assert merge_ingredients(notes) == []


# ---------------------------------------------------------------------------
# notes_to_recipe
# ---------------------------------------------------------------------------

class TestNotesToRecipe:
    @pytest.mark.asyncio
    async def test_returns_scraped_recipe_data(self):
        """notes_to_recipe returns ScrapedRecipeData with merged ingredients and steps."""
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="chicken", amount="500g")],
                actions=["Season the chicken."],
            )
        ]
        draft = RecipeDraft(
            title="Chicken Dish",
            servings=4,
            steps=["Season the chicken.", "Cook for 20 minutes."],
            tags=[],
        )
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://example.com/video")

        assert result.source_type == "url_import"
        assert result.source_url == "https://example.com/video"
        assert len(result.ingredients) == 1
        assert result.ingredients[0] == "500g chicken"
        assert result.instructions == ["Season the chicken.", "Cook for 20 minutes."]
        assert result.servings == 4

    @pytest.mark.asyncio
    async def test_title_hint_wins_over_model_title(self):
        """title_hint takes precedence over the RecipeDraft title."""
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="onion", amount=None)],
                actions=["Chop the onion."],
            )
        ]
        draft = RecipeDraft(title="Model Title", steps=["Chop the onion."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(
            notes, client, source_url="https://x.com", title_hint="My Video Title"
        )
        assert result.title == "My Video Title"

    @pytest.mark.asyncio
    async def test_model_title_used_when_no_hint(self):
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=["Add salt."],
            )
        ]
        draft = RecipeDraft(title="Salty Recipe", steps=["Add salt."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert result.title == "Salty Recipe"

    @pytest.mark.asyncio
    async def test_no_title_hint_and_no_model_title_gives_none(self):
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=["Add salt."],
            )
        ]
        draft = RecipeDraft(title=None, steps=["Add salt."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert result.title is None

    @pytest.mark.asyncio
    async def test_image_url_and_site_name_are_none(self):
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=["Add salt."],
            )
        ]
        draft = RecipeDraft(steps=["Add salt."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert result.image_url is None
        assert result.site_name is None

    @pytest.mark.asyncio
    async def test_author_passed_through(self):
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=["Add salt."],
            )
        ]
        draft = RecipeDraft(steps=["Add salt."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(
            notes, client, source_url="https://x.com", author="Test Author"
        )
        assert result.author == "Test Author"

    @pytest.mark.asyncio
    async def test_ingredient_without_amount_formatted_as_name_only(self):
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=["Season generously."],
            )
        ]
        draft = RecipeDraft(steps=["Season generously."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert result.ingredients == ["salt"]

    @pytest.mark.asyncio
    async def test_steps_capped_at_30(self):
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="onion", amount=None)],
                actions=[f"Step {i}." for i in range(35)],
            )
        ]
        draft = RecipeDraft(steps=[f"Step {i}." for i in range(35)], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert len(result.instructions) == 30


# ---------------------------------------------------------------------------
# Tag filtering and ingredient tag injection
# ---------------------------------------------------------------------------

class TestTags:
    def _make_notes_with(self, ingredient_name: str, action: str = "Cook.") -> list[ChunkNotes]:
        return [
            ChunkNotes(
                ingredients=[IngredientMention(name=ingredient_name, amount=None)],
                actions=[action],
            )
        ]

    @pytest.mark.asyncio
    async def test_reply_tag_outside_vocabulary_is_dropped(self):
        """A tag the model returns that is not in TAG_INDEX must not appear in results."""
        notes = self._make_notes_with("salt")
        draft = RecipeDraft(steps=["Cook."], tags=["NotARealTag99"])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert "NotARealTag99" not in result.tags

    @pytest.mark.asyncio
    async def test_chicken_ingredient_adds_chicken_tag(self):
        """An ingredient that maps to a VALUE_LABELS['ingredient'] key adds that tag."""
        notes = self._make_notes_with("chicken thighs")
        draft = RecipeDraft(steps=["Cook the chicken."], tags=[])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        assert "chicken" in result.tags

    @pytest.mark.asyncio
    async def test_all_returned_tags_in_tag_index(self):
        """Every tag in the result passes normalize_tag(tag) in TAG_INDEX."""
        notes = self._make_notes_with("chicken")
        draft = RecipeDraft(steps=["Cook."], tags=["Italian", "Pasta", "NotValid"])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        for tag in result.tags:
            assert normalize_tag(tag) in TAG_INDEX, f"Tag '{tag}' not in TAG_INDEX"

    @pytest.mark.asyncio
    async def test_tags_deduplicated(self):
        """The same canonical value from model and ingredient keys appears only once."""
        # salmon maps to VALUE_LABELS["ingredient"]["salmon"] = "Salmon"
        # If the model also returns "Salmon", we should only have one entry.
        notes = self._make_notes_with("salmon fillet")
        draft = RecipeDraft(steps=["Cook."], tags=["Salmon"])
        client = _make_merge_stub(draft)
        result = await notes_to_recipe(notes, client, source_url="https://x.com")
        # Count how many tags resolve to "salmon"
        salmon_count = sum(1 for t in result.tags if normalize_tag(t) == "salmon")
        assert salmon_count == 1


# ---------------------------------------------------------------------------
# Error cases (NoRecipeFoundError, TranscriptTooLongError)
# ---------------------------------------------------------------------------

class TestErrors:
    @pytest.mark.asyncio
    async def test_empty_notes_raises_no_recipe_found(self):
        """Notes with no ingredients and no actions raise NoRecipeFoundError."""
        client = _make_merge_stub(RecipeDraft(steps=[], tags=[]))
        with pytest.raises(NoRecipeFoundError):
            await notes_to_recipe([], client, source_url="https://x.com")

    @pytest.mark.asyncio
    async def test_notes_with_only_empty_chunks_raises_no_recipe_found(self):
        """ChunkNotes with empty ingredients and actions raise NoRecipeFoundError."""
        notes = [ChunkNotes(ingredients=[], actions=[])]
        client = _make_merge_stub(RecipeDraft(steps=[], tags=[]))
        with pytest.raises(NoRecipeFoundError):
            await notes_to_recipe(notes, client, source_url="https://x.com")

    @pytest.mark.asyncio
    async def test_empty_notes_does_not_call_client(self):
        """When NoRecipeFoundError is raised, the LLM client must not be called."""
        client = _make_merge_stub(RecipeDraft(steps=[], tags=[]))
        with pytest.raises(NoRecipeFoundError):
            await notes_to_recipe([], client, source_url="https://x.com")
        client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_over_budget_prompt_raises_transcript_too_long(self):
        """A merge prompt longer than MERGE_INPUT_BUDGET raises TranscriptTooLongError."""
        long_action = "x" * (MERGE_INPUT_BUDGET + 1)
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=[long_action],
            )
        ]
        client = _make_merge_stub(RecipeDraft(steps=[], tags=[]))
        with pytest.raises(TranscriptTooLongError):
            await notes_to_recipe(notes, client, source_url="https://x.com")

    @pytest.mark.asyncio
    async def test_over_budget_does_not_call_client(self):
        """When TranscriptTooLongError is raised, the LLM client must not be called."""
        long_action = "x" * (MERGE_INPUT_BUDGET + 1)
        notes = [
            ChunkNotes(
                ingredients=[IngredientMention(name="salt", amount=None)],
                actions=[long_action],
            )
        ]
        client = _make_merge_stub(RecipeDraft(steps=[], tags=[]))
        with pytest.raises(TranscriptTooLongError):
            await notes_to_recipe(notes, client, source_url="https://x.com")
        client.complete.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-end: transcript_to_recipe with the fixture
# ---------------------------------------------------------------------------

class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_fixture_calls_once_per_chunk_plus_merge(self):
        """transcript_to_recipe calls client once per chunk and once for merge."""
        raw = FIXTURE_PATH.read_text()
        condensed = condense_transcript(raw)
        expected_calls = len(condensed.chunks) + 1

        received_prompts: list[str] = []

        async def _side_effect(prompt, system_prompt, response_schema):
            received_prompts.append(prompt)
            if response_schema is RecipeDraft:
                return RecipeDraft(
                    title="Weeknight Chicken Curry",
                    servings=4,
                    steps=["Cook the chicken."],
                    tags=["Asian"],
                )
            return ChunkNotes(
                ingredients=[IngredientMention(name="chicken", amount=None)],
                actions=["Cook."],
            )

        stub = AsyncMock(spec=LLMClient)
        stub.complete = AsyncMock(side_effect=_side_effect)

        result = await transcript_to_recipe(
            raw,
            stub,
            source_url="https://youtube.com/watch?v=test",
            title_hint="Weeknight Chicken Curry",
        )

        assert stub.complete.call_count == expected_calls
        assert result.source_type == "url_import"

    @pytest.mark.asyncio
    async def test_fixture_no_prompt_contains_larder_box(self):
        """No prompt sent to the client contains the sponsor phrase 'larder box'."""
        raw = FIXTURE_PATH.read_text()

        received_prompts: list[str] = []

        async def _side_effect(prompt, system_prompt, response_schema):
            received_prompts.append(prompt)
            if response_schema is RecipeDraft:
                return RecipeDraft(steps=["Cook."], tags=[])
            return ChunkNotes(
                ingredients=[IngredientMention(name="chicken", amount=None)],
                actions=["Cook."],
            )

        stub = AsyncMock(spec=LLMClient)
        stub.complete = AsyncMock(side_effect=_side_effect)

        await transcript_to_recipe(
            raw,
            stub,
            source_url="https://youtube.com/watch?v=test",
        )

        for prompt in received_prompts:
            assert "larder box" not in prompt.lower(), (
                f"Prompt contained 'larder box': {prompt[:200]!r}"
            )
