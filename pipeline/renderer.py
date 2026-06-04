"""Module 4 — Rendering.

Cuts a selected clip from the source video, reframes it to 9:16, applies the
punch-in zoom, and exports a playable MP4 into the per-job output directory.

Phase 5 will extend this to burn word-synced captions and export an SRT; the
``render`` signature is the stable contract the orchestrator calls and must not
change (see progress.md carry-forward log).
"""

from __future__ import annotations

import os
from pathlib import Path

from moviepy import VideoFileClip

from config import CONFIG
from pipeline import effects


def _output_name(start: float, end: float) -> str:
    """Deterministic, sortable filename for a clip's time range.

    Selected clips never overlap and are at least ``CLIP_MIN_DURATION`` apart,
    so the zero-padded start time is unique within a job. Centiseconds keep it
    unambiguous even if two starts share a whole second.
    """
    return f"clip_{int(round(start * 100)):08d}.mp4"


def render(video_path: Path, clip: dict, out_dir: Path) -> Path:
    """Render a single selected clip to a 9:16 MP4.

    Args:
        video_path: source video to cut from.
        clip: a selected clip dict carrying at least ``start``/``end`` (seconds
            in the source timeline).
        out_dir: per-job output directory for the rendered file.

    Returns:
        Path to the rendered MP4.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    start = float(clip["start"])
    end = float(clip["end"])

    source = VideoFileClip(str(video_path))
    try:
        # Guard against a selection that runs past the real media (e.g. a
        # transcript word timestamped slightly beyond the decoded duration).
        if source.duration is not None:
            end = min(end, source.duration)
        if end <= start:
            raise ValueError(
                f"Clip has non-positive duration after clamping: "
                f"start={start}, end={end}, source duration={source.duration}."
            )

        subclip = source.subclipped(start, end)
        focus = effects.detect_focus_x_ratio(subclip) if CONFIG.FACE_DETECT else 0.5
        vertical = effects.reframe_to_vertical(subclip, focus_x_ratio=focus)
        final = effects.punch_in_zoom(vertical)

        out_path = out_dir / _output_name(start, end)
        final.write_videofile(
            str(out_path),
            fps=CONFIG.FPS,
            codec=CONFIG.VIDEO_CODEC,
            audio_codec=CONFIG.AUDIO_CODEC,
            preset=CONFIG.RENDER_PRESET,
            ffmpeg_params=["-crf", str(CONFIG.RENDER_CRF)],
            threads=os.cpu_count() or 2,
            logger=None,
        )
        return out_path
    finally:
        source.close()
