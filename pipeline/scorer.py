"""Module 3 — Clip scoring.

Scores candidate segments by hook/keyword matches, length, pauses,
audio energy, and a repetition penalty.

The signature below is the stable contract the orchestrator calls; Phase 3
fills in the body.
"""

from __future__ import annotations

from pathlib import Path


def score(transcript: dict, video_path: Path) -> list[dict]:
    """Score candidate clips drawn from a transcript.

    Args:
        transcript: transcript dict (see ``sample_transcript.json``).
        video_path: source video, for audio-energy analysis.

    Returns:
        A list of candidate clips, each at least ``{start, end, text, score}``.
    """
    raise NotImplementedError("Scoring not implemented yet (Phase 3).")
