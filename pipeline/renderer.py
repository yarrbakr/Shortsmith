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
from pipeline import captions, effects


def _output_name(start: float, end: float) -> str:
    """Deterministic, sortable filename for a clip's time range.

    Selected clips never overlap and are at least ``CLIP_MIN_DURATION`` apart,
    so the zero-padded start time is unique within a job. Centiseconds keep it
    unambiguous even if two starts share a whole second.
    """
    return f"clip_{int(round(start * 100)):08d}.mp4"


def render(video_path: Path, clip: dict, out_dir: Path) -> Path:
    """Render a single selected clip to an MP4 at the clip's chosen aspect.

    Args:
        video_path: source video to cut from.
        clip: a selected clip dict carrying at least ``start``/``end`` (seconds
            in the source timeline) and optionally ``aspect_ratio`` (a key in
            ``CONFIG.ASPECT_PRESETS``; defaults to ``CONFIG.ASPECT_RATIO`` = 9:16).
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
        # Per-job output aspect (B5) rides on the clip dict. Resolve it to a
        # concrete (w, h) preset and hand it to the reframe; everything after
        # reframe reads the actual frame size, so captions/watermark adapt.
        aspect = clip.get("aspect_ratio") or CONFIG.ASPECT_RATIO
        target_size = CONFIG.ASPECT_PRESETS.get(
            aspect, CONFIG.ASPECT_PRESETS[CONFIG.ASPECT_RATIO]
        )
        vertical = effects.reframe_to_vertical(
            subclip, focus_x_ratio=focus, target_size=target_size
        )
        final = effects.punch_in_zoom(vertical)

        out_path = out_dir / _output_name(start, end)
        # Burn word-synced captions (best-effort) and export the sibling .srt.
        final = captions.apply_captions(final, clip, out_dir, out_path)
        # Logo/watermark on top of everything (incl. captions), then fade the
        # whole composite in/out at the boundaries. Both are best-effort no-ops
        # when disabled, so the render never depends on them.
        final = effects.apply_watermark(final)
        final = effects.apply_fades(final)
        final.write_videofile(
            str(out_path),
            fps=CONFIG.FPS,
            codec=CONFIG.VIDEO_CODEC,
            audio_codec=CONFIG.AUDIO_CODEC,
            preset=CONFIG.RENDER_PRESET,
            # +faststart moves the moov atom to the front so browsers can stream
            # the clip inline (and decode its audio) without first fetching the
            # tail of the file. Harmless for downloaded playback.
            ffmpeg_params=["-crf", str(CONFIG.RENDER_CRF), "-movflags", "+faststart"],
            threads=os.cpu_count() or 2,
            logger=None,
        )
        return out_path
    finally:
        source.close()
