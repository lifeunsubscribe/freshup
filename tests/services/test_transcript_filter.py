"""
Unit tests for transcript_filter service.

Tests cover:
- parse_transcript: four input layouts, timestamp formats, sound tag dropping, segment splitting
- group_passages: size limit, no text loss
- pack_chunks: size limit, passage integrity, no text loss
- Empty and whitespace-only inputs
- condense_transcript: sponsor/skip/cooking-signal filtering, bypass safety valve
- cooking_signal: ingredient vocabulary, measure/verb/kitchen words, durations
"""

import pathlib
import re

import pytest

from src.services.transcript_filter import (
    CHUNK_CHARS,
    MIN_KEPT_PASSAGES,
    PASSAGE_CHARS,
    SEGMENT_CHARS,
    Chunk,
    CondensedTranscript,
    Passage,
    TranscriptSegment,
    condense_transcript,
    cooking_signal,
    group_passages,
    pack_chunks,
    parse_transcript,
)

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "transcripts"
FIXTURE_PATH = FIXTURES_DIR / "weeknight_curry_panel.txt"

_TS_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_TAG_RE = re.compile(r"^\s*[\[\(][^\[\]\(\)]+[\]\)]\s*$")


def _captions_only(fixture_text: str) -> list[str]:
    """Return caption lines only — no timestamps, no sound tags."""
    result = []
    for line in fixture_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _TS_RE.match(line) or _TAG_RE.match(line):
            continue
        result.append(line)
    return result


def _as_inline(fixture_text: str) -> str:
    """Convert panel-format fixture to 'ts caption' single-line-per-segment format."""
    out = []
    pending_ts: str | None = None
    for raw_line in fixture_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _TS_RE.match(line):
            pending_ts = line
        elif _TAG_RE.match(line):
            # Sound tag consumes its timestamp slot without producing a caption
            pending_ts = None
        else:
            if pending_ts:
                out.append(f"{pending_ts} {line}")
                pending_ts = None
            else:
                out.append(line)
    return "\n".join(out)


def _words(segments: list[TranscriptSegment]) -> list[str]:
    return " ".join(s.text for s in segments).split()


class TestParseTranscript:
    """Tests for parse_transcript — run with -k parse."""

    def test_fixture_segment_count(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        assert len(segments) == 113

    def test_fixture_first_segment(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        assert segments[0].start_seconds == 2
        assert segments[0].text == "hey everyone welcome back to the channel i"

    def test_fixture_last_segment_starts_at_388(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        assert segments[-1].start_seconds == 388

    def test_fixture_no_music_segments(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        assert all("[Music]" not in s.text for s in segments)

    def test_all_layouts_same_words_in_order(self):
        raw = FIXTURE_PATH.read_text()
        captions = _captions_only(raw)

        panel_segs = parse_transcript(raw)
        inline_segs = parse_transcript(_as_inline(raw))
        no_ts_segs = parse_transcript("\n".join(captions))
        one_line_segs = parse_transcript(" ".join(captions))

        ref = _words(panel_segs)
        assert _words(inline_segs) == ref
        assert _words(no_ts_segs) == ref
        assert _words(one_line_segs) == ref

    def test_no_timestamp_layouts_give_none_start_seconds(self):
        raw = FIXTURE_PATH.read_text()
        captions = _captions_only(raw)

        no_ts_segs = parse_transcript("\n".join(captions))
        one_line_segs = parse_transcript(" ".join(captions))

        assert all(s.start_seconds is None for s in no_ts_segs)
        assert all(s.start_seconds is None for s in one_line_segs)

    def test_one_line_no_segment_exceeds_segment_chars(self):
        raw = FIXTURE_PATH.read_text()
        captions = _captions_only(raw)
        segments = parse_transcript(" ".join(captions))
        assert all(len(s.text) <= SEGMENT_CHARS for s in segments)

    def test_hours_timestamp_parses_to_seconds(self):
        segments = parse_transcript("1:02:03\nsome caption text")
        assert len(segments) == 1
        assert segments[0].start_seconds == 3723


class TestGroupPassages:
    """Tests for group_passages — run with -k passages."""

    def test_every_passage_within_limit(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        passages = group_passages(segments)
        assert all(len(p.text) <= PASSAGE_CHARS for p in passages)

    def test_passages_text_equals_segments_text(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        passages = group_passages(segments)
        assert " ".join(p.text for p in passages) == " ".join(s.text for s in segments)

    def test_passage_indices_are_sequential(self):
        segments = parse_transcript(FIXTURE_PATH.read_text())
        passages = group_passages(segments)
        assert [p.index for p in passages] == list(range(len(passages)))


class TestPackChunks:
    """Tests for pack_chunks — run with -k chunks."""

    def test_every_chunk_within_limit(self):
        passages = group_passages(parse_transcript(FIXTURE_PATH.read_text()))
        chunks = pack_chunks(passages)
        assert all(len(c.text) <= CHUNK_CHARS for c in chunks)

    def test_no_passage_split_across_chunks(self):
        passages = group_passages(parse_transcript(FIXTURE_PATH.read_text()))
        chunks = pack_chunks(passages)
        # Each chunk.text is '\n'.join of whole passage texts; splitting recovers them
        reconstructed = []
        for chunk in chunks:
            reconstructed.extend(chunk.text.split("\n"))
        assert reconstructed == [p.text for p in passages]

    def test_no_text_lost(self):
        passages = group_passages(parse_transcript(FIXTURE_PATH.read_text()))
        chunks = pack_chunks(passages)
        assert "\n".join(c.text for c in chunks) == "\n".join(p.text for p in passages)

    def test_chunk_indices_are_sequential(self):
        passages = group_passages(parse_transcript(FIXTURE_PATH.read_text()))
        chunks = pack_chunks(passages)
        assert [c.index for c in chunks] == list(range(len(chunks)))


class TestEmpty:
    """Tests for empty and whitespace-only inputs — run with -k empty."""

    def test_empty_string_parse_returns_empty(self):
        assert parse_transcript("") == []

    def test_whitespace_string_parse_returns_empty(self):
        assert parse_transcript("   \n  \t  ") == []

    def test_empty_segments_passages_returns_empty(self):
        assert group_passages([]) == []

    def test_empty_passages_chunks_returns_empty(self):
        assert pack_chunks([]) == []

    def test_whitespace_full_pipeline_returns_empty(self):
        segs = parse_transcript("   ")
        passages = group_passages(segs)
        chunks = pack_chunks(passages)
        assert segs == []
        assert passages == []
        assert chunks == []

    def test_empty_full_pipeline_does_not_raise(self):
        segs = parse_transcript("")
        passages = group_passages(segs)
        chunks = pack_chunks(passages)
        assert segs == []
        assert passages == []
        assert chunks == []


class TestCookingSignal:
    """Tests for cooking_signal — run with -k signal."""

    def test_signal_zero_for_unrelated_personal_story(self):
        assert cooking_signal(
            "my sister called me last week and she is moving across the country"
        ) == 0

    def test_signal_zero_for_common_words_not_in_lists(self):
        # "can", "whole", "large" are intentionally excluded from MEASURE_WORDS
        assert cooking_signal("you can do a whole lot with a large family") == 0

    def test_signal_nonzero_for_spoken_duration(self):
        assert cooking_signal("let it go for about ten minutes") >= 1

    def test_signal_nonzero_for_kitchen_word_lid(self):
        assert cooking_signal("put a lid on it") >= 1

    def test_signal_nonzero_for_measure_word_tablespoons(self):
        assert cooking_signal("two tablespoons") >= 1

    def test_signal_nonzero_for_cooking_verb_simmer(self):
        assert cooking_signal("simmer for fifteen minutes") >= 1

    def test_signal_nonzero_for_ingredient_key(self):
        assert cooking_signal("add the spinach and stir") >= 1


class TestCondenseTranscriptKeeps:
    """Tests that condense_transcript keeps the cooking content — run with -k condense_keeps."""

    def test_condense_keeps_dish_name(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "chicken curry with coconut milk and spinach" in kept

    def test_condense_keeps_oil(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "two tablespoons of oil" in kept

    def test_condense_keeps_onion(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "one large onion" in kept

    def test_condense_keeps_garlic(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "three cloves of garlic" in kept

    def test_condense_keeps_curry_powder(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "two tablespoons of curry powder" in kept

    def test_condense_keeps_chicken_thighs(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "one and a half pounds of chicken thighs" in kept

    def test_condense_keeps_coconut_milk(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "one can of coconut milk" in kept

    def test_condense_keeps_chicken_stock(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "one cup of chicken stock" in kept

    def test_condense_keeps_simmer_duration(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "simmer for fifteen minutes" in kept

    def test_condense_keeps_spinach(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "handfuls of spinach" in kept

    def test_condense_keeps_lime(self):
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "half a lime" in kept


class TestCondenseTranscriptDrops:
    """Tests that condense_transcript drops sponsor/chatter — run with -k condense_drops."""

    def _kept(self, result: CondensedTranscript) -> str:
        return " ".join(c.text for c in result.chunks)

    def test_condense_drops_sponsor_product_name(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "larder box" not in self._kept(result)

    def test_condense_drops_sponsor_phrase_use_code(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "use code" not in self._kept(result)

    def test_condense_drops_sponsor_phrase_percent_off(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "percent off" not in self._kept(result)

    def test_condense_drops_food_in_sponsor_window(self):
        # "lemon chicken pasta" is between sponsor triggers — must be cut
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "lemon chicken pasta" not in self._kept(result)

    def test_condense_drops_location_in_personal_story(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "denver" not in self._kept(result)

    def test_condense_drops_subscribe_in_signoff(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "subscribe" not in self._kept(result)

    def test_condense_drops_welcome_back_greeting(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert "welcome back" not in self._kept(result)

    def test_condense_kept_chars_under_60_percent(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert result.kept_chars < result.total_chars * 0.60

    def test_condense_not_bypassed(self):
        result = condense_transcript(FIXTURE_PATH.read_text())
        assert result.bypassed is False


class TestSkipRange:
    """Tests for skip_ranges behaviour — run with -k skip_range."""

    def test_skip_range_removes_timestamped_segment(self):
        # 2:27 = 147 s is inside [143, 212); "two tablespoons of oil" lives there
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw, skip_ranges=[(143, 212)])
        kept = " ".join(c.text for c in result.chunks)
        assert "two tablespoons of oil" not in kept

    def test_skip_range_keeps_segment_outside_range(self):
        # 4:59 = 299 s is outside [143, 212); "one can of coconut milk" lives there
        raw = FIXTURE_PATH.read_text()
        result = condense_transcript(raw, skip_ranges=[(143, 212)])
        kept = " ".join(c.text for c in result.chunks)
        assert "one can of coconut milk" in kept

    def test_skip_range_no_cut_without_timestamps(self):
        # Remove all timestamps: skip_ranges must not cut anything
        raw = FIXTURE_PATH.read_text()
        captions = [
            line.strip()
            for line in raw.splitlines()
            if line.strip() and not _TS_RE.match(line.strip()) and not _TAG_RE.match(line.strip())
        ]
        no_ts_raw = "\n".join(captions)
        result_with = condense_transcript(no_ts_raw, skip_ranges=[(143, 212)])
        result_without = condense_transcript(no_ts_raw)
        kept_with = " ".join(c.text for c in result_with.chunks)
        kept_without = " ".join(c.text for c in result_without.chunks)
        assert kept_with == kept_without


class TestSponsor:
    """Tests for sponsor-read detection — run with -k sponsor."""

    _CROSS_SEG = (
        "0:01\nhere is a recipe for you today and use\n"
        "0:03\ncode freshup to get fifty percent off your first order\n"
        "0:05\nstir the onion in the pan for two minutes\n"
    )

    def test_sponsor_cross_segment_phrase_both_segments_cut(self):
        # "use" ends segment 0, "code" starts segment 1 — the phrase spans the join
        result = condense_transcript(self._CROSS_SEG)
        kept = " ".join(c.text for c in result.chunks)
        assert "and use" not in kept
        assert "code freshup" not in kept

    def test_sponsor_food_between_two_triggers_is_cut(self):
        # "fifty percent off" (second trigger) is in the same segment as food words;
        # the whole block from first trigger to last is cut
        raw = (
            "0:01\nsponsored by freshmarket get your groceries delivered\n"
            "0:03\nlemon pasta and beef tacos are on the menu this week\n"
            "0:05\nuse code fresh10 to save ten percent off your order\n"
            "0:07\nnow heat a pan and add two tablespoons of olive oil\n"
        )
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "lemon pasta" not in kept
        assert "two tablespoons of olive oil" in kept

    def test_sponsor_lone_trigger_cuts_only_own_segment(self):
        # Only one sponsor phrase present — no second trigger within the window
        raw = (
            "0:01\nhey everyone welcome to the channel\n"
            "0:03\nuse code tasty to get a discount today\n"
            "0:05\nadd two tablespoons of butter to a hot pan\n"
            "0:07\nstir the garlic for thirty seconds\n"
        )
        result = condense_transcript(raw)
        kept = " ".join(c.text for c in result.chunks)
        assert "use code" not in kept
        assert "two tablespoons of butter" in kept

    def test_sponsor_passages_do_not_span_cut(self):
        # Text before a cut and text after it must be in separate passages
        result = condense_transcript(self._CROSS_SEG)
        for chunk in result.chunks:
            for passage_text in chunk.text.split("\n"):
                assert "and use" not in passage_text or "stir" not in passage_text


class TestBypass:
    """Tests for the MIN_KEPT_PASSAGES safety valve — run with -k bypass."""

    def test_bypass_too_few_cooking_passages_returns_whole(self):
        # Only one passage has cooking signal; safety valve must keep everything
        raw = (
            "0:01\nstir the onion in the pan for two minutes\n"
            "0:10\nmy sister just called me today about her new apartment\n"
            "0:20\nit is really nice weather outside today is it not\n"
        )
        result = condense_transcript(raw)
        assert result.bypassed is True
        kept = " ".join(c.text for c in result.chunks)
        assert "my sister" in kept
        assert "stir the onion" in kept

    def test_bypass_enough_cooking_passages_not_bypassed(self):
        # Enough cooking passages: safety valve must NOT fire
        raw = (
            "0:01\nstir the onion in the pan for two minutes\n"
            "0:10\nadd three cloves of garlic and a teaspoon of salt\n"
            "0:20\nsimmer for fifteen minutes then stir in the spinach\n"
            "0:30\nsome random chatter that has nothing to do with cooking\n"
        )
        result = condense_transcript(raw)
        assert result.bypassed is False
        kept = " ".join(c.text for c in result.chunks)
        assert "random chatter" not in kept
