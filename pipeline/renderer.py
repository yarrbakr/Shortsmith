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

from moviepy import VideoFileClip, concatenate_videoclips

from config import CONFIG
from pipeline import captions, effects, trimmer


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
    fragments: list = []  # spliced sub-ranges (B2); closed in finally
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

        out_path = out_dir / _output_name(start, end)

        # B2 — filler-word & silence removal. Best-effort: if a trim plan exists,
        # cut its keep-ranges and concatenate them (before reframe/zoom, so the
        # effects + size contract run once on the spliced clip), and feed captions
        # a clip-local, pre-remapped word list (start=0) so subtitles stay synced
        # without touching captions.py. Any failure falls back to the single subclip.
        plan = None
        try:
            plan = trimmer.plan_trim(clip)
        except Exception:  # noqa: BLE001 - trim planning must never kill a render
            plan = None

        caption_clip = clip
        try:
            if plan and plan.get("keep_ranges"):
                fragments = [source.subclipped(s, e) for s, e in plan["keep_ranges"]]
                base = concatenate_videoclips(fragments, method="chain")
                caption_clip = {**clip, "start": 0.0, "end": plan["duration"],
                                "words": plan["words"]}
            else:
                base = source.subclipped(start, end)
        except Exception:  # noqa: BLE001 - any splice failure → full subclip
            for frag in fragments:
                try:
                    frag.close()
                except Exception:  # noqa: BLE001
                    pass
            fragments = []
            base = source.subclipped(start, end)
            caption_clip = clip

        focus = effects.detect_focus_x_ratio(base) if CONFIG.FACE_DETECT else 0.5
        vertical = effects.reframe_to_vertical(base, focus_x_ratio=focus)
        final = effects.punch_in_zoom(vertical)

        # Burn word-synced captions (best-effort) and export the sibling .srt.
        final = captions.apply_captions(final, caption_clip, out_dir, out_path)
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
        for frag in fragments:
            try:
                frag.close()
            except Exception:  # noqa: BLE001
                pass
        source.close()
