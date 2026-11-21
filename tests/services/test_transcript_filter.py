"""
Unit tests for transcript_filter service.

Tests cover:
- parse_transcript: four input layouts, timestamp formats, sound tag dropping, segment splitting
- group_passages: size limit, no text loss
- pack_chunks: size limit, passage integrity, no text loss
- Empty and whitespace-only inputs
"""

import pathlib
import re

import pytest

from src.services.transcript_filter import (
    CHUNK_CHARS,
    PASSAGE_CHARS,
    SEGMENT_CHARS,
    Chunk,
    Passage,
    TranscriptSegment,
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
