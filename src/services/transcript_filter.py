"""
Video transcript parser for FreshUp.

Turns a raw transcript string into ordered segments, passages, and chunks
suitable for passing to the local LLM. No text is dropped or reordered here;
content filtering (sponsor reads, asides) is a later stage.

Why chunked: MAX_LLM_INPUT_LENGTH in llm_input_sanitizer silently truncates
input over 16,000 characters. A full cooking video transcript can exceed that,
so we split it into chunks that each fit comfortably in a single LLM call.
"""

import re
from dataclasses import dataclass

SEGMENT_CHARS = 120
PASSAGE_CHARS = 320
# ~600 tokens, fits with a prompt+reply in a 2,048-token Ollama default window.
CHUNK_CHARS = 2400

# Full-line timestamp: m:ss, mm:ss, or h:mm:ss (no trailing text)
_TS_LINE_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
# Inline timestamp: "m:ss text" on a single line
_TS_INLINE_RE = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$")
# A line that is only a sound tag: [Music], (applause), etc.
_SOUND_TAG_RE = re.compile(r"^\s*[\[\(][^\[\]\(\)]+[\]\)]\s*$")


@dataclass(frozen=True)
class TranscriptSegment:
    """One caption unit, at most SEGMENT_CHARS wide."""
    start_seconds: int | None
    text: str


@dataclass(frozen=True)
class Passage:
    """A group of consecutive segments joined with spaces, at most PASSAGE_CHARS wide."""
    index: int
    start_seconds: int | None
    text: str


@dataclass(frozen=True)
class Chunk:
    """A group of consecutive passages joined with newlines, at most CHUNK_CHARS wide."""
    index: int
    start_seconds: int | None
    text: str


def _parse_ts(ts: str) -> int:
    """Convert 'm:ss' or 'h:mm:ss' string to integer seconds."""
    parts = ts.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return int(parts[0]) * 60 + int(parts[1])


def _emit_segments(
    text: str,
    start_seconds: int | None,
    out: list[TranscriptSegment],
) -> None:
    """Append text to out as one or more segments, splitting at whitespace when needed."""
    if len(text) <= SEGMENT_CHARS:
        out.append(TranscriptSegment(start_seconds=start_seconds, text=text))
        return
    words = text.split()
    current_parts: list[str] = []
    current_len = 0
    for word in words:
        wl = len(word)
        if current_parts:
            if current_len + 1 + wl > SEGMENT_CHARS:
                out.append(TranscriptSegment(
                    start_seconds=start_seconds,
                    text=" ".join(current_parts),
                ))
                current_parts = [word]
                current_len = wl
            else:
                current_parts.append(word)
                current_len += 1 + wl
        else:
            current_parts = [word]
            current_len = wl
    if current_parts:
        out.append(TranscriptSegment(
            start_seconds=start_seconds,
            text=" ".join(current_parts),
        ))


def parse_transcript(raw: str) -> list[TranscriptSegment]:
    """
    Parse a raw transcript string into ordered segments.

    Accepts four layouts:
    - YouTube panel copy: standalone timestamp line, then caption line
    - Inline: '0:00 caption text' on one line
    - No timestamps: plain caption lines
    - One long unbroken line

    Sound-tag-only lines ([Music], (applause)) are dropped. Empty lines are
    skipped. Segments longer than SEGMENT_CHARS are split at whitespace.
    """
    if not raw or not raw.strip():
        return []
    segments: list[TranscriptSegment] = []
    current_ts: int | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if _SOUND_TAG_RE.match(line):
            continue
        m = _TS_INLINE_RE.match(line)
        if m:
            current_ts = _parse_ts(m.group(1))
            caption = m.group(2).strip()
            if caption:
                _emit_segments(caption, current_ts, segments)
            continue
        if _TS_LINE_RE.match(line):
            current_ts = _parse_ts(line)
            continue
        _emit_segments(line, current_ts, segments)
    return segments


def group_passages(segments: list[TranscriptSegment]) -> list[Passage]:
    """
    Join consecutive segments with spaces into passages of at most PASSAGE_CHARS.

    A passage closes when the next segment would not fit. No text is lost.
    """
    if not segments:
        return []
    passages: list[Passage] = []
    current_parts: list[str] = []
    current_start: int | None = None
    current_len = 0
    for seg in segments:
        sl = len(seg.text)
        if current_parts:
            if current_len + 1 + sl > PASSAGE_CHARS:
                passages.append(Passage(
                    index=len(passages),
                    start_seconds=current_start,
                    text=" ".join(current_parts),
                ))
                current_parts = [seg.text]
                current_start = seg.start_seconds
                current_len = sl
            else:
                current_parts.append(seg.text)
                current_len += 1 + sl
        else:
            current_parts = [seg.text]
            current_start = seg.start_seconds
            current_len = sl
    if current_parts:
        passages.append(Passage(
            index=len(passages),
            start_seconds=current_start,
            text=" ".join(current_parts),
        ))
    return passages


def pack_chunks(passages: list[Passage]) -> list[Chunk]:
    """
    Join consecutive passages with newlines into chunks of at most CHUNK_CHARS.

    A passage is never split across two chunks. No text is lost.
    """
    if not passages:
        return []
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_start: int | None = None
    current_len = 0
    for passage in passages:
        pl = len(passage.text)
        if current_parts:
            if current_len + 1 + pl > CHUNK_CHARS:
                chunks.append(Chunk(
                    index=len(chunks),
                    start_seconds=current_start,
                    text="\n".join(current_parts),
                ))
                current_parts = [passage.text]
                current_start = passage.start_seconds
                current_len = pl
            else:
                current_parts.append(passage.text)
                current_len += 1 + pl
        else:
            current_parts = [passage.text]
            current_start = passage.start_seconds
            current_len = pl
    if current_parts:
        chunks.append(Chunk(
            index=len(chunks),
            start_seconds=current_start,
            text="\n".join(current_parts),
        ))
    return chunks
