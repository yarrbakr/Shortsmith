"""Module 4 — Rendering.

Cuts a clip, reframes to 9:16, applies effects, burns captions, exports MP4.

The signature below is the stable contract the orchestrator calls; Phase 4
fills in the body.
"""

from __future__ import annotations

from pathlib import Path


def render(video_path: Path, clip: dict, out_dir: Path) -> Path:
    """Render a single selected clip to a 9:16 MP4.

    Args:
        video_path: source video to cut from.
        clip: a selected clip (with ``start/end`` and metadata).
        out_dir: per-job output directory for the rendered file.

    Returns:
        Path to the rendered MP4.
    """
    raise NotImplementedError("Rendering not implemented yet (Phase 4).")
