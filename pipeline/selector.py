"""Module 3 — Clip selection.

Greedy, non-overlapping selection of the top-N highest-scoring clips. The
scorer emits many overlapping candidate windows; this picks the best ones that
don't collide in time, so each chunk of the source video is used at most once.

The ``select`` signature is the stable contract the orchestrator calls.
"""

from __future__ import annotations


def _overlaps(clip: dict, chosen: list[dict]) -> bool:
    """True if ``clip`` shares any time range with an already-selected clip."""
    start, end = clip["start"], clip["end"]
    return any(start < other["end"] and other["start"] < end for other in chosen)


def select(scored: list[dict], top_n: int) -> list[dict]:
    """Pick the top-N non-overlapping clips from scored candidates.

    Args:
        scored: candidate clips from ``scorer.score`` (with ``start/end/score``).
        top_n: maximum number of clips to return.

    Returns:
        The selected clips, ranked by score, none overlapping in time. Returns
        an empty list when given no candidates or a non-positive ``top_n``.
    """
    if not scored or top_n <= 0:
        return []

    ranked = sorted(scored, key=lambda c: c["score"], reverse=True)
    chosen: list[dict] = []
    for clip in ranked:
        if len(chosen) >= top_n:
            break
        if not _overlaps(clip, chosen):
            chosen.append(clip)
    return chosen
