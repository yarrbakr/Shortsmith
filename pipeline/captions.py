"""Module 5 — Animated captions & subtitle export.

Burns word-synced captions onto a rendered clip and writes a matching ``.srt``.

Style (see RESEARCH.md, Option B): one large word at a time, centered, with a
quick pop-in scale — the classic viral-shorts look. moviepy's ``TextClip`` gives
full color control (the spoken word is drawn in the accent ``CAPTION_HIGHLIGHT_COLOR``
with a thick stroke for readability), at the cost of per-word compositing.

Contract & timeline (see progress.md ``[Phase 4 → Phase 5]`` carry-forward):
``apply_captions`` is called inside ``renderer.render`` *after* the clip has been
reframed + zoomed (so it is exactly ``TARGET_WIDTH x TARGET_HEIGHT``) and *before*
``write_videofile``. Each selected clip carries word-level timestamps in the
**source** timeline; we offset them by ``clip["start"]`` onto the cut clip's local
timeline. Everything degrades gracefully: a missing/broken font or empty words
skips the burn but the MP4 still renders and an ``.srt`` is still written — a job
must never die here.
"""

from __future__ import annotations

from pathlib import Path

from config import CONFIG

# Trailing sentence punctuation marks a natural SRT cue boundary.
_SENTENCE_END = (".", "?", "!", "…", ":")


def _local_words(clip: dict) -> list[dict]:
    """Map a clip's source-timeline words onto its local ``[0, duration]`` timeline.

    Subtracts ``clip["start"]`` from every word, clamps to the clip's duration,
    and drops empty / out-of-range entries. This is the single source of truth
    shared by the burned captions and the SRT export.
    """
    start = float(clip["start"])
    duration = float(clip["end"]) - start
    if duration <= 0:
        return []

    local: list[dict] = []
    for word in clip.get("words", []):
        text = str(word.get("word", "")).strip()
        if not text:
            continue
        w_start = max(0.0, float(word["start"]) - start)
        w_end = min(duration, float(word["end"]) - start)
        if w_end <= 0 or w_start >= duration:
            continue
        local.append({"word": text, "start": w_start, "end": max(w_start, w_end)})
    return local


def _pop_scale(t: float) -> float:
    """Ease-out scale for the pop-in: grows ``0.7 → 1.0`` over the pop window, then holds."""
    dur = CONFIG.CAPTION_POP_DURATION
    if dur <= 0:
        return 1.0
    p = min(max(t / dur, 0.0), 1.0)
    eased = 1.0 - (1.0 - p) * (1.0 - p)  # ease-out quad
    return 0.7 + 0.3 * eased


def _make_text_clip(text: str):
    """Build a single centered word ``TextClip``, shrinking the font if it overflows.

    Returns the TextClip (duration unset) or ``None`` if the font can't render it.
    """
    from moviepy import TextClip

    if CONFIG.CAPTION_UPPERCASE:
        text = text.upper()

    font = str(CONFIG.CAPTION_FONT)
    size = CONFIG.CAPTION_FONT_SIZE
    max_width = CONFIG.CAPTION_MAX_WIDTH_RATIO * CONFIG.TARGET_WIDTH

    def _build(font_size: int):
        return TextClip(
            font,
            text,
            font_size=font_size,
            color=CONFIG.CAPTION_HIGHLIGHT_COLOR,
            stroke_color=CONFIG.CAPTION_STROKE_COLOR,
            stroke_width=CONFIG.CAPTION_STROKE_WIDTH,
            method="label",
        )

    tc = _build(size)
    # Long single words can overflow the safe width — rebuild once, smaller.
    if tc.w > max_width:
        shrunk = max(16, int(size * max_width / tc.w))
        if shrunk < size:
            tc = _build(shrunk)
    return tc


def build_word_clips(words_local: list[dict], clip_duration: float) -> list:
    """Build positioned, timed, pop-in ``TextClip`` overlays for each word.

    Each word is shown from its own start until the next word's start (held, so
    there's no flicker between words), clamped to the clip. The very last word
    lingers to ``word.end + CAPTION_SYNC_TOLERANCE`` (capped at the clip end).
    Per-word failures are skipped rather than raised.
    """
    clips: list = []
    target_center_y = CONFIG.CAPTION_POSITION_RATIO * CONFIG.TARGET_HEIGHT
    n = len(words_local)

    for i, word in enumerate(words_local):
        w_start = word["start"]
        if i + 1 < n:
            w_end = words_local[i + 1]["start"]
        else:
            w_end = min(clip_duration, word["end"] + CONFIG.CAPTION_SYNC_TOLERANCE)
        w_end = min(w_end, clip_duration)
        duration = w_end - w_start
        if duration <= 0:
            continue

        try:
            tc = _make_text_clip(word["word"])
        except Exception:  # noqa: BLE001 - bad glyph/font → skip this word, keep going
            continue
        if tc is None:
            continue

        # Fixed top so the word's natural (unscaled) box is centered on the line;
        # the brief pop-in scale grows slightly downward, which is visually fine.
        y_top = int(round(target_center_y - tc.h / 2))
        tc = (
            tc.with_start(w_start)
            .with_duration(duration)
            .with_position(("center", y_top))
        )
        if CONFIG.CAPTION_POP_DURATION > 0:
            tc = tc.resized(_pop_scale)
        clips.append(tc)

    return clips


def write_srt(words_local: list[dict], out_path: Path) -> None:
    """Group local-timeline words into readable cues and save an ``.srt``.

    Cues break at ``SRT_MAX_WORDS_PER_LINE`` words or on sentence-ending
    punctuation. Empty input still writes a (valid, empty) ``.srt`` file so the
    "an .srt per clip" contract always holds.
    """
    import pysrt

    subs = pysrt.SubRipFile()
    group: list[dict] = []

    def _flush() -> None:
        if not group:
            return
        text = " ".join(w["word"] for w in group).strip()
        subs.append(pysrt.SubRipItem(
            index=len(subs) + 1,
            start=pysrt.SubRipTime.from_ordinal(int(group[0]["start"] * 1000)),
            end=pysrt.SubRipTime.from_ordinal(int(group[-1]["end"] * 1000)),
            text=text,
        ))

    for word in words_local:
        group.append(word)
        ends_sentence = word["word"].rstrip().endswith(_SENTENCE_END)
        if len(group) >= CONFIG.SRT_MAX_WORDS_PER_LINE or ends_sentence:
            _flush()
            group = []
    _flush()

    subs.save(str(out_path), encoding="utf-8")


def apply_captions(final_clip, clip: dict, out_dir: Path, mp4_path: Path):
    """Overlay word-synced captions on ``final_clip`` and export the sibling SRT.

    Always writes ``<mp4 stem>.srt`` into ``out_dir``. Returns the captioned
    ``CompositeVideoClip`` when captions are enabled and buildable, otherwise the
    original ``final_clip`` unchanged (any failure → no burn, MP4 still renders).
    """
    words_local = _local_words(clip)

    srt_path = mp4_path.with_suffix(".srt")
    try:
        write_srt(words_local, srt_path)
    except Exception:  # noqa: BLE001 - never let SRT failure kill the render
        pass

    if not CONFIG.CAPTION_ENABLED or not words_local:
        return final_clip
    if not Path(CONFIG.CAPTION_FONT).is_file():
        return final_clip

    try:
        from moviepy import CompositeVideoClip

        word_clips = build_word_clips(words_local, float(final_clip.duration))
        if not word_clips:
            return final_clip
        composite = CompositeVideoClip([final_clip, *word_clips])
        composite = composite.with_duration(final_clip.duration)
        if final_clip.audio is not None:
            composite = composite.with_audio(final_clip.audio)
        return composite
    except Exception:  # noqa: BLE001 - captions are best-effort; keep the MP4
        return final_clip
