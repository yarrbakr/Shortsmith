"""Module 5 — Animated captions & subtitle export.

Burns word-synced captions onto a rendered clip and writes a matching ``.srt``.

Two styles (B1, selected by ``CONFIG.CAPTION_STYLE`` or a per-clip
``clip["caption_style"]``): "hormozi" (default) shows a short phrase with the
spoken word highlighted in the accent ``CAPTION_HIGHLIGHT_COLOR`` (karaoke feel);
"word_pop" shows one large word at a time with a quick pop-in scale (the original
Phase-5 look). Both use moviepy's ``TextClip`` for full per-word colour control
with a thick stroke for readability, at the cost of per-word compositing.

Contract & timeline (see progress.md ``[Phase 4 → Phase 5]`` carry-forward):
``apply_captions`` is called inside ``renderer.render`` *after* the clip has been
reframed + zoomed and *before* ``write_videofile``. Caption geometry is derived
from the *actual* ``final_clip.size`` (the chosen aspect preset, B5), not the
9:16 CONFIG constants. Each selected clip carries word-level timestamps in the
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


def _make_text_clip(text: str, frame_w: int, scale: float, color: str | None = None):
    """Build a single centered word ``TextClip``, shrinking the font if it overflows.

    ``frame_w`` is the actual rendered frame width and ``scale`` is
    ``frame_w / CAPTION_REFERENCE_WIDTH`` — together they keep the font, stroke,
    and safe width proportional across aspect presets (B5). On the 9:16 default
    ``scale == 1.0`` and ``frame_w == TARGET_WIDTH``, so sizing is unchanged.

    ``color`` defaults to the accent ``CAPTION_HIGHLIGHT_COLOR`` (the word_pop
    look); the hormozi style passes the inactive (``CAPTION_COLOR``) or active
    (highlight) colour explicitly. Returns the TextClip (duration unset) or
    ``None`` if the font can't render it.
    """
    from moviepy import TextClip

    if CONFIG.CAPTION_UPPERCASE:
        text = text.upper()

    color = color or CONFIG.CAPTION_HIGHLIGHT_COLOR
    font = str(CONFIG.CAPTION_FONT)
    size = max(16, int(round(CONFIG.CAPTION_FONT_SIZE * scale)))
    stroke = max(1, int(round(CONFIG.CAPTION_STROKE_WIDTH * scale)))
    max_width = CONFIG.CAPTION_MAX_WIDTH_RATIO * frame_w

    def _build(font_size: int):
        return TextClip(
            font,
            text,
            font_size=font_size,
            color=color,
            stroke_color=CONFIG.CAPTION_STROKE_COLOR,
            stroke_width=stroke,
            method="label",
        )

    tc = _build(size)
    # Long single words can overflow the safe width — rebuild once, smaller.
    if tc.w > max_width:
        shrunk = max(16, int(size * max_width / tc.w))
        if shrunk < size:
            tc = _build(shrunk)
    return tc


def build_word_clips(words_local: list[dict], clip_duration: float,
                     frame_w: int, frame_h: int) -> list:
    """Build positioned, timed, pop-in ``TextClip`` overlays for each word.

    Each word is shown from its own start until the next word's start (held, so
    there's no flicker between words), clamped to the clip. The very last word
    lingers to ``word.end + CAPTION_SYNC_TOLERANCE`` (capped at the clip end).
    ``frame_w``/``frame_h`` are the actual rendered dimensions, so the caption
    band tracks the chosen aspect preset (B5). Per-word failures are skipped
    rather than raised.
    """
    clips: list = []
    scale = frame_w / CONFIG.CAPTION_REFERENCE_WIDTH
    target_center_y = CONFIG.CAPTION_POSITION_RATIO * frame_h
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
            tc = _make_text_clip(word["word"], frame_w, scale)
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


def _group_phrases(words_local: list[dict], max_words: int) -> list[list[dict]]:
    """Group local words into short phrases for the hormozi line display.

    Breaks a phrase when it reaches ``max_words`` *or* a word ends a sentence
    (reusing ``_SENTENCE_END``). Returns a list of word-lists; ``[]`` for empty
    input. Hormozi-only — ``write_srt`` keeps its own (7-word) grouping so the
    locked SRT contract is untouched.
    """
    if max_words < 1:
        max_words = 1
    phrases: list[list[dict]] = []
    group: list[dict] = []
    for word in words_local:
        group.append(word)
        ends_sentence = word["word"].rstrip().endswith(_SENTENCE_END)
        if len(group) >= max_words or ends_sentence:
            phrases.append(group)
            group = []
    if group:
        phrases.append(group)
    return phrases


def build_hormozi_clips(words_local: list[dict], clip_duration: float,
                        frame_w: int, frame_h: int) -> list:
    """Build positioned, timed multi-word "karaoke" caption overlays.

    Each phrase (short word group) is laid out as a centered, wrap-capable line
    in the lower third. Every word gets a white BASE clip spanning the phrase's
    whole visible window, plus a highlight clip (accent ``CAPTION_HIGHLIGHT_COLOR``)
    at the *same* (x, y) spanning only that word's spoken interval, composited on
    top — so the highlight sweeps word to word. ``frame_w``/``frame_h`` are the
    actual rendered dimensions, so layout (center, wrap width, spacing) tracks
    the chosen aspect preset (B5). Per-word / per-phrase failures are skipped
    rather than raised.
    """
    if clip_duration <= 0:
        return []

    phrases = _group_phrases(words_local, CONFIG.CAPTION_HORMOZI_MAX_WORDS)
    if not phrases:
        return []

    scale = frame_w / CONFIG.CAPTION_REFERENCE_WIDTH
    target_center_y = CONFIG.CAPTION_POSITION_RATIO * frame_h
    max_width = CONFIG.CAPTION_MAX_WIDTH_RATIO * frame_w
    word_spacing = int(round(CONFIG.CAPTION_HORMOZI_WORD_SPACING * scale))
    line_spacing = int(round(CONFIG.CAPTION_HORMOZI_LINE_SPACING * scale))

    clips: list = []
    num_phrases = len(phrases)

    for pi, phrase in enumerate(phrases):
        # --- Phrase visible window: hold until the next phrase appears (no flicker).
        phrase_start = phrase[0]["start"]
        if pi + 1 < num_phrases:
            phrase_end = phrases[pi + 1][0]["start"]
        else:
            phrase_end = min(clip_duration, phrase[-1]["end"] + CONFIG.CAPTION_SYNC_TOLERANCE)
        phrase_end = min(phrase_end, clip_duration)
        phrase_window = phrase_end - phrase_start
        if phrase_window <= 0:
            continue

        # --- Build the white base clip for each word and measure it.
        built: list[dict] = []  # {idx, word, base, w, h}
        for idx, word in enumerate(phrase):
            try:
                base = _make_text_clip(word["word"], frame_w, scale, color=CONFIG.CAPTION_COLOR)
            except Exception:  # noqa: BLE001 - bad glyph/font → drop this word
                continue
            if base is None:
                continue
            built.append({"idx": idx, "word": word, "base": base, "w": base.w, "h": base.h})
        if not built:
            continue

        # --- Greedy wrap into lines that fit the safe width.
        lines: list[list[dict]] = []
        current: list[dict] = []
        current_w = 0.0
        for item in built:
            add_w = item["w"] + (word_spacing if current else 0)
            if current and current_w + add_w > max_width:
                lines.append(current)
                current = [item]
                current_w = item["w"]
            else:
                current.append(item)
                current_w += add_w
        if current:
            lines.append(current)

        # --- Vertical stack: center the whole block on the lower-third line.
        line_heights = [max(it["h"] for it in line) for line in lines]
        total_h = sum(line_heights) + line_spacing * (len(lines) - 1)
        block_top = target_center_y - total_h / 2.0

        y_cursor = block_top
        for li, line in enumerate(lines):
            line_h = line_heights[li]
            line_w = sum(it["w"] for it in line) + word_spacing * (len(line) - 1)
            x_cursor = (frame_w - line_w) / 2.0
            y = int(round(y_cursor))

            for it in line:
                x = int(round(x_cursor))
                word = it["word"]
                idx = it["idx"]

                # Base (white) for the full phrase window.
                base = (
                    it["base"]
                    .with_start(phrase_start)
                    .with_duration(phrase_window)
                    .with_position((x, y))
                )
                clips.append(base)

                # Highlight (accent) only while this word is spoken. The phrase's
                # last word stays lit until the phrase swaps out.
                hl_start = word["start"]
                if idx + 1 < len(phrase):
                    hl_end = phrase[idx + 1]["start"]
                else:
                    hl_end = phrase_end
                hl_start = max(hl_start, phrase_start)
                hl_end = min(hl_end, phrase_end)
                if hl_end - hl_start > 0:
                    try:
                        hl = _make_text_clip(word["word"], frame_w, scale, color=CONFIG.CAPTION_HIGHLIGHT_COLOR)
                    except Exception:  # noqa: BLE001 - keep the white base, skip highlight
                        hl = None
                    if hl is not None:
                        hl = (
                            hl.with_start(hl_start)
                            .with_duration(hl_end - hl_start)
                            .with_position((x, y))
                        )
                        clips.append(hl)  # after base → drawn on top

                x_cursor += it["w"] + word_spacing
            y_cursor += line_h + line_spacing

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

        style = (clip.get("caption_style") or CONFIG.CAPTION_STYLE or "word_pop").lower()
        if style not in CONFIG.CAPTION_STYLES:
            style = "word_pop"  # defensive: never trust an unknown style
        frame_w, frame_h = final_clip.size
        builder = build_hormozi_clips if style == "hormozi" else build_word_clips
        word_clips = builder(words_local, float(final_clip.duration), frame_w, frame_h)
        if not word_clips:
            return final_clip
        composite = CompositeVideoClip([final_clip, *word_clips])
        composite = composite.with_duration(final_clip.duration)
        if final_clip.audio is not None:
            composite = composite.with_audio(final_clip.audio)
        return composite
    except Exception:  # noqa: BLE001 - captions are best-effort; keep the MP4
        return final_clip
