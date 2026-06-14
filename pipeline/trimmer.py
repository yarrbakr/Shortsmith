"""Module B2 — Filler-word & silence removal ("magic cut").

Computes a *trim plan* for one selected clip: which source-timeline spans to
keep, and the clip's words remapped onto the spliced (clip-local) timeline so
burned captions and the SRT stay in sync. This module is **pure** — no moviepy,
no I/O — so it is fast to unit-test and the renderer stays in charge of cutting.

How the renderer uses it (see ``pipeline/renderer.py``): if ``plan_trim`` returns
a plan, the renderer cuts each ``keep_ranges`` span from the source and
concatenates them, then hands ``captions.apply_captions`` a shallow-copied clip
``{**clip, "start": 0.0, "end": duration, "words": plan["words"]}``. Because
``captions._local_words`` subtracts ``clip["start"]`` (now 0) and clamps to
``[0, duration]``, the remapped words pass straight through — so ``captions.py``
needs no changes and the locked ``renderer.render`` signature is untouched (B2
rides the clip dict, exactly like B1's ``caption_style``).

Everything is best-effort: ``plan_trim`` returns ``None`` whenever trimming is
disabled, there's nothing worth removing, or a guard trips — and ``None`` means
"render exactly as before" (single contiguous subclip, original words), so the
common case has zero behaviour change and a job never dies here.
"""

from __future__ import annotations

from config import CONFIG
from pipeline.scorer import _normalize  # identical filler matching to the scorer


def _enabled(clip: dict) -> bool:
    """Trimming runs if the per-job toggle is set or the global flag is on."""
    return bool(clip.get("trim_silence")) or CONFIG.SILENCE_TRIM_ENABLED


def _clean_words(clip: dict, clip_start: float, clip_end: float) -> list[dict]:
    """Sanitised, sorted words clamped into the clip, each with a ``norm`` token."""
    cleaned: list[dict] = []
    for word in clip.get("words", []):
        text = str(word.get("word", "")).strip()
        if not text:
            continue
        try:
            w_start = float(word["start"])
            w_end = float(word["end"])
        except (KeyError, TypeError, ValueError):
            continue
        w_start = max(clip_start, min(w_start, clip_end))
        w_end = max(clip_start, min(w_end, clip_end))
        if w_end <= w_start:
            continue
        cleaned.append({"word": text, "start": w_start, "end": w_end, "norm": _normalize(text)})
    cleaned.sort(key=lambda w: w["start"])
    return cleaned


def _filler_drop_flags(words: list[dict]) -> list[bool]:
    """Mark words that are filler (single words or multi-word phrases) for removal."""
    n = len(words)
    drop = [False] * n
    if not CONFIG.SILENCE_REMOVE_FILLERS:
        return drop

    norms = [w["norm"] for w in words]
    # Single filler words.
    for i, norm in enumerate(norms):
        if norm and norm in CONFIG.FILLER_WORDS:
            drop[i] = True
    # Filler phrases matched against consecutive normalized tokens.
    for phrase in CONFIG.FILLER_PHRASES:
        tokens = [t for t in (_normalize(p) for p in phrase.split()) if t]
        if not tokens:
            continue
        span = len(tokens)
        for i in range(0, n - span + 1):
            if norms[i:i + span] == tokens:
                for j in range(i, i + span):
                    drop[j] = True
    return drop


def plan_trim(clip: dict) -> dict | None:
    """Compute a keep-ranges + remapped-words trim plan for one clip, or ``None``.

    Returns ``None`` (→ render unchanged) when trimming is disabled, the clip has
    no usable words, nothing is removable, the result would drop below the kept
    floor, or the splice would be too fragmented. On success returns::

        {"keep_ranges": [(s_src, e_src), ...],   # source timeline, sorted, disjoint
         "words":       [{"word", "start", "end"}],  # clip-local times in [0, duration]
         "duration":    float,                    # == sum(e - s for s, e in keep_ranges)
         "removed":     float}                     # seconds removed (diagnostic)
    """
    if not _enabled(clip):
        return None

    try:
        clip_start = float(clip["start"])
        clip_end = float(clip["end"])
    except (KeyError, TypeError, ValueError):
        return None
    original = clip_end - clip_start
    if original <= 0:
        return None

    words = _clean_words(clip, clip_start, clip_end)
    if not words:
        return None

    drop = _filler_drop_flags(words)
    kept = [(i, w) for i, (w, d) in enumerate(zip(words, drop)) if not d]
    if not kept:
        return None

    pad = CONFIG.SILENCE_PAD
    gap_threshold = CONFIG.SILENCE_GAP_THRESHOLD

    # --- Build keep-ranges: pad each kept word, then split when either a real
    #     silence opens (gap > threshold) OR a filler was dropped between two
    #     kept words (so the filler's audio is physically removed, not just
    #     un-captioned); otherwise merge so natural rhythm survives. The pad +
    #     post-merge step coalesces splits that are too small to be worth a cut.
    first_idx, first_word = kept[0]
    ranges: list[list[float]] = []
    cur_start = first_word["start"] - pad
    cur_end = first_word["end"] + pad
    prev_idx, prev_end = first_idx, first_word["end"]
    for idx, w in kept[1:]:
        gap = w["start"] - prev_end  # inter-(kept-)word gap, scorer's formula
        dropped_between = idx - prev_idx > 1  # a filler sat between these kept words
        if gap > gap_threshold or dropped_between:
            ranges.append([cur_start, cur_end])
            cur_start = w["start"] - pad
        cur_end = w["end"] + pad
        prev_idx, prev_end = idx, w["end"]
    ranges.append([cur_start, cur_end])

    # Clamp into the clip and merge any ranges that overlap after padding.
    merged: list[list[float]] = []
    for s, e in ranges:
        s = max(clip_start, s)
        e = min(clip_end, e)
        if e <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    keep_ranges = [(s, e) for s, e in merged]

    # --- Guards: bail out (render unchanged) on degenerate / not-worth-it plans.
    if not keep_ranges:
        return None
    if len(keep_ranges) > CONFIG.SILENCE_MAX_FRAGMENTS:
        return None
    kept_duration = sum(e - s for s, e in keep_ranges)
    if original - kept_duration < CONFIG.SILENCE_MIN_SAVINGS:
        return None
    if kept_duration < CONFIG.SILENCE_MIN_KEPT_DURATION:
        return None

    # --- Remap surviving words onto the spliced clip-local timeline.
    offsets: list[float] = []
    acc = 0.0
    for s, e in keep_ranges:
        offsets.append(acc)
        acc += e - s

    local_words: list[dict] = []
    for _idx, w in kept:
        ws, we = w["start"], w["end"]
        for k, (s, e) in enumerate(keep_ranges):
            if ws <= e and we >= s:  # word overlaps this kept range
                cs = min(max(ws, s), e)
                ce = min(max(we, s), e)
                local_start = offsets[k] + (cs - s)
                local_end = offsets[k] + (ce - s)
                if local_end < local_start:
                    local_end = local_start
                local_words.append({
                    "word": w["word"],
                    "start": local_start,
                    "end": local_end,
                })
                break  # first containing range wins (ranges are disjoint)

    return {
        "keep_ranges": keep_ranges,
        "words": local_words,
        "duration": kept_duration,
        "removed": original - kept_duration,
    }
