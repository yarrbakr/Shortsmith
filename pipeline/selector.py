"""Module 3 — Clip selection.

Greedy, non-overlapping selection of the top-N highest-scoring clips.

The signature below is the stable contract the orchestrator calls; Phase 3
fills in the body.
"""

from __future__ import annotations


def select(scored: list[dict], top_n: int) -> list[dict]:
    """Pick the top-N non-overlapping clips from scored candidates.

    Args:
        scored: candidate clips from ``scorer.score`` (with ``start/end/score``).
        top_n: maximum number of clips to return.

    Returns:
        The selected clips, ranked by score, none overlapping in time.
    """
    raise NotImplementedError("Selection not implemented yet (Phase 3).")
