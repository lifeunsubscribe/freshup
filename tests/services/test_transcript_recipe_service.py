"""
Unit tests for transcript_recipe_service (Phase 2D).

All LLM calls use a synchronous stub that never touches Ollama.
"""

import pytest
from typing import Type
from unittest.mock import AsyncMock

from src.schemas.transcript import ChunkNotes, IngredientMention, NotesResult
from src.services.llm.client import LLMClient
from src.services.llm.exceptions import LLMResponseError, LLMUnavailableError
from src.services.transcript_filter import Chunk
from src.services.transcript_recipe_service import (
    normalise_amount,
    spoken_amount,
    extract_chunk_notes,
    extract_all_notes,
)


# ---------------------------------------------------------------------------
# Stub LLM client
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
