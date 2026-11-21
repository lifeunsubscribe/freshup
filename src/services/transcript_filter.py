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
from collections.abc import Sequence
from dataclasses import dataclass

from src.services.ingredient_keys import keys_for

SEGMENT_CHARS = 120
PASSAGE_CHARS = 320
# ~600 tokens, fits with a prompt+reply in a 2,048-token Ollama default window.
CHUNK_CHARS = 2400

# --- Content-filter constants ---

SPONSOR_PHRASES: frozenset[str] = frozenset({
    "sponsored by", "sponsor of", "today's sponsor", "sponsoring",
    "use code", "promo code", "discount code", "coupon code",
    "percent off", "free trial",
})

# Only words rare outside cooking — everyday words like "can", "whole", "large",
# "half", "add", "mix", "put" are intentionally absent.
MEASURE_WORDS: frozenset[str] = frozenset({
    "cup", "tablespoon", "teaspoon", "ounce", "pound", "gram",
    "clove", "pinch", "handful", "degree",
})

COOKING_VERBS: frozenset[str] = frozenset({
    "stir", "simmer", "boil", "sear", "roast", "bake", "fry",
    "chop", "dice", "mince", "whisk", "season", "squeeze", "wilt",
})

KITCHEN_WORDS: frozenset[str] = frozenset({
    "oven", "pan", "skillet", "pot", "bowl", "heat", "stove", "lid",
})

# Two sponsor-phrase triggers this many segments apart (or fewer) bracket a read.
SPONSOR_WINDOW_SEGMENTS = 30

# Safety valve: keep all passages if fewer than this many have cooking signal.
MIN_KEPT_PASSAGES = 3

# --- Precompiled patterns ---

_NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    "twenty|thirty|forty|fifty|sixty"
)
_DURATION_RE = re.compile(
    rf'\b(?:\d+|{_NUMBER_WORDS})\s+(?:second|minute|hour)s?\b',
    re.IGNORECASE,
)

_SPONSOR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
    for phrase in SPONSOR_PHRASES
]

# One pattern per cooking-signal word; each tolerates -s, -es, -ed, -ing endings.
_SIGNAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'\b' + re.escape(word) + r'(?:s|es|ed|ing)?\b', re.IGNORECASE)
    for word in (*MEASURE_WORDS, *COOKING_VERBS, *KITCHEN_WORDS)
]

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


@dataclass(frozen=True)
class CondensedTranscript:
    """Result of condense_transcript: filtered chunks plus accounting of what was dropped."""
    chunks: list[Chunk]
    total_chars: int
    kept_chars: int
    dropped_chars: dict[str, int]
    bypassed: bool


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


def cooking_signal(text: str) -> int:
    """
    Return a non-negative integer measuring how much cooking content is in text.

    Counts: ingredient vocabulary keys, rare cooking words (with common inflections),
    and one point for any spoken duration (number + time unit).
    """
    score = len(keys_for(text))
    for pattern in _SIGNAL_PATTERNS:
        if pattern.search(text):
            score += 1
    if _DURATION_RE.search(text):
        score += 1
    return score


def _find_sponsor_triggers(segments: list[TranscriptSegment]) -> set[int]:
    """Return segment indices that contain or overlap a sponsor phrase."""
    if not segments:
        return set()

    # Build joined text and track each segment's char range within it.
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    pos = 0
    for seg in segments:
        offsets.append((pos, pos + len(seg.text)))
        parts.append(seg.text)
        pos += len(seg.text) + 1  # +1 for the space separator

    joined = " ".join(parts)
    triggers: set[int] = set()

    for pattern in _SPONSOR_PATTERNS:
        for m in pattern.finditer(joined):
            ms, me = m.start(), m.end()
            for i, (ss, se) in enumerate(offsets):
                # Match overlaps this segment's range [ss, se).
                if ms < se and me > ss:
                    triggers.add(i)

    return triggers


def _expand_sponsor_blocks(sorted_triggers: list[int]) -> set[int]:
    """
    Return the set of segment indices to cut for sponsor reads.

    Consecutive triggers within SPONSOR_WINDOW_SEGMENTS are chained into one
    block; every index from the block's first to its last trigger is cut.
    A lone trigger cuts only itself.
    """
    cut: set[int] = set()
    n = len(sorted_triggers)
    i = 0
    while i < n:
        j = i
        while (
            j + 1 < n
            and sorted_triggers[j + 1] - sorted_triggers[j] <= SPONSOR_WINDOW_SEGMENTS
        ):
            j += 1
        if j > i:
            cut.update(range(sorted_triggers[i], sorted_triggers[j] + 1))
        else:
            cut.add(sorted_triggers[i])
        i = j + 1
    return cut


def _group_surviving_segments(
    segments: list[TranscriptSegment],
    cut: dict[int, str],
) -> list[Passage]:
    """
    Group the segments NOT in cut into passages, starting a new group at each cut.

    This ensures no passage spans a gap where segments were removed.
    """
    passages: list[Passage] = []
    run: list[TranscriptSegment] = []

    def _flush() -> None:
        if run:
            for p in group_passages(run):
                passages.append(Passage(
                    index=len(passages),
                    start_seconds=p.start_seconds,
                    text=p.text,
                ))
            run.clear()

    for i, seg in enumerate(segments):
        if i in cut:
            _flush()
        else:
            run.append(seg)
    _flush()
    return passages


def condense_transcript(
    raw: str,
    skip_ranges: Sequence[tuple[int, int]] = (),
) -> CondensedTranscript:
    """
    Parse raw, drop off-topic passages, and return packed chunks with accounting.

    Steps (in order):
    1. Parse to segments.
    2. Cut segments whose timestamp falls in a skip_ranges entry [start, end).
       Segments with no timestamp are never cut by this rule.
    3. Cut sponsor reads identified by SPONSOR_PHRASES in the joined segment text.
    4. Group surviving segments into passages within each uninterrupted run.
    5. Drop passages with cooking_signal == 0.
    6. Safety valve: if step 5 would leave fewer than MIN_KEPT_PASSAGES passages,
       skip step 5 and set bypassed=True.
    7. Pack surviving passages into chunks.
    """
    segments = parse_transcript(raw)
    total_chars = sum(len(s.text) for s in segments)

    cut: dict[int, str] = {}

    # Step 2: skip_ranges
    for i, seg in enumerate(segments):
        if seg.start_seconds is not None:
            for rs, re_ in skip_ranges:
                if rs <= seg.start_seconds < re_:
                    cut[i] = "skip_range"
                    break

    # Step 3: sponsor reads
    triggers = _find_sponsor_triggers(segments)
    if triggers:
        for idx in _expand_sponsor_blocks(sorted(triggers)):
            if idx not in cut:
                cut[idx] = "sponsor"

    # Step 4: group surviving segments into passages, respecting cut boundaries
    passages = _group_surviving_segments(segments, cut)

    # Steps 5 & 6
    zero_signal_passages = [p for p in passages if cooking_signal(p.text) == 0]
    positive_signal_passages = [p for p in passages if cooking_signal(p.text) > 0]
    bypassed = False
    if len(positive_signal_passages) < MIN_KEPT_PASSAGES:
        kept_passages = passages
        bypassed = True
    else:
        kept_passages = positive_signal_passages

    # Step 7
    chunks = pack_chunks(kept_passages)

    # Accounting
    kept_chars = sum(len(p.text) for p in kept_passages)
    dropped_chars: dict[str, int] = {}
    for i, seg in enumerate(segments):
        reason = cut.get(i)
        if reason:
            dropped_chars[reason] = dropped_chars.get(reason, 0) + len(seg.text)
    if not bypassed:
        no_cooking_chars = sum(len(p.text) for p in zero_signal_passages)
        if no_cooking_chars > 0:
            dropped_chars["no_cooking_signal"] = no_cooking_chars

    return CondensedTranscript(
        chunks=chunks,
        total_chars=total_chars,
        kept_chars=kept_chars,
        dropped_chars=dropped_chars,
        bypassed=bypassed,
    )
