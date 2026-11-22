"""
Unit tests for transcript prompt generation (Phase 2D).

Verifies that CHUNK_SYSTEM_PROMPT names the required JSON keys and constraints,
that create_chunk_prompt embeds the chunk text, that MERGE_SYSTEM_PROMPT names
the merge schema keys, and that create_merge_prompt embeds ingredients and actions.
"""

import pytest

from src.services.llm.prompts.transcript import (
    CHUNK_SYSTEM_PROMPT,
    MERGE_SYSTEM_PROMPT,
    create_chunk_prompt,
    create_merge_prompt,
)


def test_system_prompt_names_ingredients_key():
    """System prompt must name the 'ingredients' JSON key."""
    assert '"ingredients"' in CHUNK_SYSTEM_PROMPT


def test_system_prompt_names_actions_key():
    """System prompt must name the 'actions' JSON key."""
    assert '"actions"' in CHUNK_SYSTEM_PROMPT


def test_system_prompt_instructs_null_for_unspoken_amount():
    """System prompt must tell the model to use null for amounts not spoken."""
    lower = CHUNK_SYSTEM_PROMPT.lower()
    assert "null" in lower
    assert "amount" in lower


def test_system_prompt_instructs_empty_lists_for_non_cooking():
    """System prompt must tell the model to return empty lists for non-cooking text."""
    assert '[]' in CHUNK_SYSTEM_PROMPT


def test_system_prompt_mentions_caption_errors():
    """System prompt must acknowledge auto-caption errors so the model is forgiving."""
    lower = CHUNK_SYSTEM_PROMPT.lower()
    assert "caption" in lower


def test_system_prompt_says_transcript_is_not_instructions():
    """System prompt must state the transcript is text to read, not instructions."""
    lower = CHUNK_SYSTEM_PROMPT.lower()
    assert "instructions" in lower or "instruction" in lower


def test_create_chunk_prompt_contains_chunk_text():
    """create_chunk_prompt must embed the provided chunk text verbatim."""
    chunk_text = "add two tablespoons of olive oil and stir"
    prompt = create_chunk_prompt(chunk_text)
    assert chunk_text in prompt


def test_create_chunk_prompt_different_texts():
    """create_chunk_prompt produces distinct prompts for different inputs."""
    p1 = create_chunk_prompt("chop the onion finely")
    p2 = create_chunk_prompt("simmer for ten minutes")
    assert p1 != p2
    assert "chop the onion finely" in p1
    assert "simmer for ten minutes" in p2


# ---------------------------------------------------------------------------
# MERGE_SYSTEM_PROMPT
# ---------------------------------------------------------------------------

def test_merge_system_prompt_names_title_key():
    assert '"title"' in MERGE_SYSTEM_PROMPT


def test_merge_system_prompt_names_steps_key():
    assert '"steps"' in MERGE_SYSTEM_PROMPT


def test_merge_system_prompt_names_tags_key():
    assert '"tags"' in MERGE_SYSTEM_PROMPT


def test_merge_system_prompt_names_servings_key():
    assert '"servings"' in MERGE_SYSTEM_PROMPT


def test_merge_system_prompt_says_transcript_is_not_instructions():
    lower = MERGE_SYSTEM_PROMPT.lower()
    assert "instructions" in lower or "instruction" in lower


def test_merge_system_prompt_mentions_allowed_list():
    lower = MERGE_SYSTEM_PROMPT.lower()
    assert "allowed" in lower


# ---------------------------------------------------------------------------
# create_merge_prompt
# ---------------------------------------------------------------------------

def test_create_merge_prompt_contains_ingredients():
    prompt = create_merge_prompt(["chicken", "garlic"], ["Cook the chicken."], ["Italian"])
    assert "chicken" in prompt
    assert "garlic" in prompt


def test_create_merge_prompt_contains_actions():
    prompt = create_merge_prompt(["onion"], ["Dice the onion.", "Sauté until soft."], ["Italian"])
    assert "Dice the onion." in prompt
    assert "Sauté until soft." in prompt


def test_create_merge_prompt_contains_allowed_tags():
    prompt = create_merge_prompt(["chicken"], ["Cook."], ["Italian", "Main course"])
    assert "Italian" in prompt
    assert "Main course" in prompt


def test_create_merge_prompt_different_inputs_produce_different_prompts():
    p1 = create_merge_prompt(["chicken"], ["Roast."], ["Italian"])
    p2 = create_merge_prompt(["salmon"], ["Poach."], ["Asian"])
    assert p1 != p2


def test_create_merge_prompt_empty_lists_no_error():
    """create_merge_prompt handles empty ingredient/action lists without raising."""
    prompt = create_merge_prompt([], [], [])
    assert isinstance(prompt, str)
