"""Module 3 — Clip scoring.

Heuristic (no-LLM, CPU-only) scoring of candidate clips drawn from a word-level
transcript. Each candidate is scored by a weighted blend of:

  * hook / keyword matches (English + Roman Urdu), weighted toward the opening,
  * sentence length vs the ideal word range,
  * how cleanly the clip starts/ends on a natural pause,
  * audio RMS energy relative to the whole clip (librosa, reusing the Phase-2
    ``audio.wav`` next to the video — see the carry-forward in progress.md),
  * a repetition / filler penalty.

The ``score`` signature is the stable contract the orchestrator calls; the
weights and keyword lists live in ``config.py`` (no hardcoded tunables here).
"""

from __future__ import annotations

import re
from pathlib import Path

from config import CONFIG

# Trailing sentence punctuation marks a natural sentence boundary.
_SENTENCE_END = (".", "?", "!", "…")
# Strip punctuation for word-level comparisons (filler/unique-ratio checks).
_PUNCT_RE = re.compile(r"[^\w']+", re.UNICODE)


def _normalize(word: str) -> str:
    """Lower-case a word with surrounding punctuation removed."""
    return _PUNCT_RE.sub("", word.lower())


def _flatten_words(transcript: dict) -> list[dict]:
    """Collect every timestamped word across all segments into one stream."""
    words: list[dict] = []
    for segment in transcript.get("segments", []):
        for word in segment.get("words", []):
            text = str(word.get("word", "")).strip()
            if not text:
                continue
            words.append({
                "word": text,
                "start": float(word["start"]),
                "end": float(word["end"]),
            })
    return words


def _build_sentences(words: list[dict]) -> list[dict]:
    """Split the word stream into sentence-like units.

    A unit ends when either the gap to the next word exceeds
    ``PAUSE_THRESHOLD`` or the current word ends with sentence punctuation.
    Each unit records its words, time bounds, and the silent gap before/after
    it (used for the boundary score).
    """
    sentences: list[dict] = []
    current: list[dict] = []
    for index, word in enumerate(words):
        current.append(word)
        next_word = words[index + 1] if index + 1 < len(words) else None
        gap_after = (next_word["start"] - word["end"]) if next_word else float("inf")
        ends_sentence = word["word"].rstrip().endswith(_SENTENCE_END)
        if next_word is None or gap_after > CONFIG.PAUSE_THRESHOLD or ends_sentence:
            sentences.append({
                "words": current,
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "gap_after": gap_after,
            })
            current = []

    # Annotate the gap *before* each unit (gap_after of the previous one).
    for index, sentence in enumerate(sentences):
        prev = sentences[index - 1] if index > 0 else None
        sentence["gap_before"] = prev["gap_after"] if prev else float("inf")
    return sentences


def _make_clip(units: list[dict]) -> dict:
    """Assemble a candidate clip dict from a run of sentence units."""
    words = [w for unit in units for w in unit["words"]]
    text = " ".join(w["word"] for w in words).strip()
    return {
        "start": round(units[0]["start"], 2),
        "end": round(units[-1]["end"], 2),
        "text": text,
        "words": words,
        "gap_before": units[0]["gap_before"],
        "gap_after": units[-1]["gap_after"],
    }


def _split_long_unit(unit: dict) -> list[dict]:
    """Split a single over-long (pause-free) unit into duration-bounded chunks."""
    chunks: list[dict] = []
    current: list[dict] = []
    for word in unit["words"]:
        if current and (word["end"] - current[0]["start"]) > CONFIG.CLIP_MAX_DURATION:
            chunks.append({
                "words": current, "start": current[0]["start"],
                "end": current[-1]["end"], "gap_before": float("inf"),
                "gap_after": float("inf"),
            })
            current = []
        current.append(word)
    if current:
        chunks.append({
            "words": current, "start": current[0]["start"],
            "end": current[-1]["end"], "gap_before": float("inf"),
            "gap_after": float("inf"),
        })
    return chunks


def _generate_candidates(sentences: list[dict]) -> list[dict]:
    """Sliding window over sentence units → duration-valid candidate clips."""
    candidates: list[dict] = []
    seen: set[tuple[float, float]] = set()

    def _emit(units: list[dict]) -> None:
        clip = _make_clip(units)
        key = (clip["start"], clip["end"])
        if key not in seen:
            seen.add(key)
            candidates.append(clip)

    for i in range(len(sentences)):
        units: list[dict] = []
        for j in range(i, len(sentences)):
            units.append(sentences[j])
            duration = units[-1]["end"] - units[0]["start"]
            if duration > CONFIG.CLIP_MAX_DURATION:
                # A single unit alone is already too long: split it instead.
                if len(units) == 1:
                    for chunk in _split_long_unit(units[0]):
                        if chunk["end"] - chunk["start"] >= CONFIG.CLIP_MIN_DURATION:
                            _emit([chunk])
                break
            if duration >= CONFIG.CLIP_MIN_DURATION:
                _emit(list(units))
    return candidates


# --- Sub-scores (each returns 0..1) ---------------------------------------

def _hook_score(words: list[dict]) -> float:
    """Reward hook phrases, weighting matches in the opening words higher."""
    tokens = [w["word"].lower() for w in words]
    opening = " ".join(tokens[:8])
    full = " ".join(tokens)
    score = 0.0
    for phrase in (*CONFIG.HOOK_KEYWORDS_EN, *CONFIG.HOOK_KEYWORDS_UR):
        if phrase in opening:
            score = max(score, 1.0)
        elif phrase in full:
            score = max(score, 0.5)
    return score


def _length_score(word_count: int) -> float:
    """Peak inside [CLIP_MIN_WORDS, CLIP_MAX_WORDS], taper linearly outside."""
    lo, hi = CONFIG.CLIP_MIN_WORDS, CONFIG.CLIP_MAX_WORDS
    if lo <= word_count <= hi:
        return 1.0
    if word_count < lo:
        return max(0.0, word_count / lo)
    # Above the ideal max: decay, reaching 0 at ~2x the max.
    return max(0.0, 1.0 - (word_count - hi) / hi)


def _boundary_score(clip: dict) -> float:
    """Reward clips that begin and end on a real pause (clean cut points)."""
    threshold = CONFIG.PAUSE_THRESHOLD
    starts_clean = clip["gap_before"] >= threshold
    ends_clean = clip["gap_after"] >= threshold
    return 0.5 * float(starts_clean) + 0.5 * float(ends_clean)


def _repetition_score(words: list[dict]) -> float:
    """1.0 = clean/varied content; low = filler-heavy, repetitive, or outro."""
    tokens = [_normalize(w["word"]) for w in words]
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0.0

    filler = sum(1 for t in tokens if t in CONFIG.FILLER_WORDS)
    filler_ratio = filler / len(tokens)
    unique_ratio = len(set(tokens)) / len(tokens)

    text = " ".join(w["word"].lower() for w in words)
    phrase_penalty = 0.1 * sum(1 for p in CONFIG.FILLER_PHRASES if p in text)
    outro_penalty = 0.6 if any(p in text for p in CONFIG.OUTRO_PHRASES) else 0.0

    score = (1.0 - filler_ratio) * unique_ratio - phrase_penalty - outro_penalty
    return max(0.0, min(1.0, score))


class _EnergyAnalyzer:
    """Loads ``audio.wav`` once and answers per-clip relative RMS energy.

    Degrades to a neutral 0.5 for every clip when the WAV is missing or librosa
    is unavailable (offline dev against ``sample_transcript.json``, or an empty
    transcript with no extracted audio) — scoring must never crash here.
    """

    def __init__(self, video_path: Path) -> None:
        self._ok = False
        try:
            import librosa  # imported lazily; heavy and optional at score time
            import numpy as np

            audio_path = video_path.parent / "audio.wav"
            if not audio_path.is_file():
                return
            samples, sr = librosa.load(str(audio_path), sr=None, mono=True)
            if samples.size == 0:
                return
            rms = librosa.feature.rms(y=samples)[0]
            self._times = librosa.frames_to_time(range(len(rms)), sr=sr)
            self._rms = rms
            self._global_mean = float(np.mean(rms)) or 1.0
            self._np = np
            self._ok = True
        except Exception:  # noqa: BLE001 - any failure → neutral fallback
            self._ok = False

    def energy(self, start: float, end: float) -> float:
        if not self._ok:
            return 0.5
        np = self._np
        mask = (self._times >= start) & (self._times <= end)
        if not mask.any():
            return 0.5
        clip_mean = float(np.mean(self._rms[mask]))
        ratio = clip_mean / self._global_mean
        # ratio 1.0 → 0.5; squash to 0..1 (≈2x average energy saturates to 1).
        return max(0.0, min(1.0, ratio / 2.0))


# --- Virality grade (score → UI) ------------------------------------------

# Human-readable labels for the per-signal score components.
SIGNAL_LABELS = {
    "hook": "Hook",
    "length": "Length",
    "pause": "Clean cut",
    "energy": "Energy",
    "repetition": "Clarity",
}

# Weight each component carries in the blended total (mirrors ``score``).
_SIGNAL_WEIGHTS = {
    "hook": CONFIG.W_HOOK,
    "length": CONFIG.W_LENGTH,
    "pause": CONFIG.W_PAUSE,
    "energy": CONFIG.W_ENERGY,
    "repetition": CONFIG.W_REPETITION,
}


def grade(score_value: float) -> dict:
    """Map a 0..1 blended clip score to a 0-100 percentage + A-F letter.

    The CONFIG weights sum to ~1.0, so ``score_value`` is already a fraction of
    the theoretical maximum; we surface it as a percentage and bucket it into a
    letter via ``CONFIG.GRADE_THRESHOLDS``. This is a heuristic *clip-strength*
    grade, not a prediction of real-world views.
    """
    pct = max(0, min(100, round(float(score_value) * 100)))
    letter = CONFIG.GRADE_THRESHOLDS[-1][0]  # fallback = lowest grade
    for cutoff_letter, min_pct in CONFIG.GRADE_THRESHOLDS:
        if pct >= min_pct:
            letter = cutoff_letter
            break
    return {"pct": pct, "letter": letter}


def top_signal(components: dict | None, peers: list[dict] | None = None) -> str | None:
    """Label of the signal that best characterises a clip.

    With ``peers`` (the component dicts of every clip in the same batch,
    including this one), name the signal on which this clip most **stands out
    from its peers** — skipping signals that don't vary across the batch, since
    a signal that's identical everywhere (e.g. a hook keyword every clip hits)
    can't distinguish one clip from another. This is what makes per-clip labels
    actually differ instead of all collapsing onto the highest-weight signal.

    Without ``peers`` (a lone clip, or an all-identical batch) fall back to the
    signal that contributed most to the blended score, weighted by its CONFIG
    weight. ``None`` for empty input.
    """
    if not components:
        return None

    if peers:
        keys = list(components.keys())
        means = {k: sum(p.get(k, 0.0) for p in peers) / len(peers) for k in keys}
        varying = [
            k for k in keys
            if max(p.get(k, 0.0) for p in peers) - min(p.get(k, 0.0) for p in peers) > 1e-6
        ]
        if varying:
            # Largest positive deviation above the batch mean; CONFIG weight
            # only breaks ties between equally-distinctive signals.
            best = max(
                varying,
                key=lambda k: (components.get(k, 0.0) - means[k], _SIGNAL_WEIGHTS.get(k, 0.0)),
            )
            return SIGNAL_LABELS.get(best, best.title())

    best = max(components, key=lambda k: _SIGNAL_WEIGHTS.get(k, 0.0) * components[k])
    return SIGNAL_LABELS.get(best, best.title())


def score(transcript: dict, video_path: Path) -> list[dict]:
    """Score candidate clips drawn from a transcript.

    Args:
        transcript: transcript dict (see ``sample_transcript.json``).
        video_path: source video; ``audio.wav`` next to it is reused for energy.

    Returns:
        Candidate clips sorted by descending ``score``, each carrying at least
        ``{start, end, text, score}`` plus ``words`` (for Phase-5 captions) and
        a ``components`` breakdown.
    """
    words = _flatten_words(transcript)
    if not words:
        return []

    sentences = _build_sentences(words)
    candidates = _generate_candidates(sentences)
    if not candidates:
        return []

    analyzer = _EnergyAnalyzer(video_path)

    scored: list[dict] = []
    for clip in candidates:
        clip_words = clip["words"]
        components = {
            "hook": _hook_score(clip_words),
            "length": _length_score(len(clip_words)),
            "pause": _boundary_score(clip),
            "energy": analyzer.energy(clip["start"], clip["end"]),
            "repetition": _repetition_score(clip_words),
        }
        total = (
            CONFIG.W_HOOK * components["hook"]
            + CONFIG.W_LENGTH * components["length"]
            + CONFIG.W_PAUSE * components["pause"]
            + CONFIG.W_ENERGY * components["energy"]
            + CONFIG.W_REPETITION * components["repetition"]
        )
        scored.append({
            "start": clip["start"],
            "end": clip["end"],
            "text": clip["text"],
            "score": round(total, 4),
            "words": clip_words,
            "components": {k: round(v, 4) for k, v in components.items()},
        })

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored
