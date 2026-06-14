"""Module 4 & 5 — Effects.

Video effects applied during rendering:

  * ``reframe_to_vertical`` — scale-to-cover + crop a clip to 9:16 (1080x1920),
    optionally biasing the horizontal crop toward a detected face.
  * ``punch_in_zoom`` — a constant-size frame transform that eases from
    ``ZOOM_START`` to ``ZOOM_END`` over ``ZOOM_DURATION`` seconds, then holds.
  * ``apply_fades`` — fade in/out at the clip boundaries (video + audio) for a
    smoother start/end than a hard cut.
  * ``apply_watermark`` — composite a logo/watermark PNG into a chosen corner.
  * ``detect_focus_x_ratio`` — OpenCV face detection (stretch) used to pick the
    crop's horizontal focus point.

Design (see RESEARCH.md): the reframe uses moviepy's own ``resized``/``cropped``
effects so the clip's declared ``size`` stays correct for the encoder. The zoom
is a custom cv2 frame transform whose output dimensions never change, so it is
safe to chain after the reframe without confusing the writer. Word-synced
animated captions (Phase 5) live in ``pipeline/captions.py`` (they need text
rendering + SRT file I/O, kept separate from these frame transforms).
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from config import CONFIG


def _zoom_factor(t: float) -> float:
    """Zoom multiplier at clip-local time ``t`` (seconds).

    Linear ramp from ``ZOOM_START`` to ``ZOOM_END`` across ``ZOOM_DURATION``,
    then held flat for the rest of the clip. A non-positive duration disables
    the ramp (constant ``ZOOM_END``).
    """
    start, end, dur = CONFIG.ZOOM_START, CONFIG.ZOOM_END, CONFIG.ZOOM_DURATION
    if dur <= 0:
        return end
    progress = min(max(t / dur, 0.0), 1.0)
    return start + (end - start) * progress


def reframe_to_vertical(clip, focus_x_ratio: float = 0.5, target_size: tuple | None = None):
    """Scale-to-cover and crop ``clip`` to ``target_size`` (default = CONFIG 9:16).

    The source is scaled so it fully covers the target (no letterboxing), then
    cropped: vertically centered, horizontally centered on ``focus_x_ratio``
    (0.0 = left edge, 1.0 = right edge) of the *scaled* frame.

    ``target_size`` is ``(width, height)`` in px; when omitted it falls back to
    ``(CONFIG.TARGET_WIDTH, CONFIG.TARGET_HEIGHT)`` so existing callers (and the
    9:16 default) are unaffected. The crop math is fully parametric on the
    target, so any aspect works (B5). Returns a clip whose ``size`` is exactly
    ``target_size``.
    """
    target_w, target_h = target_size or (CONFIG.TARGET_WIDTH, CONFIG.TARGET_HEIGHT)
    src_w, src_h = clip.size

    # max() => cover the whole target; ceil so rounding never leaves us a pixel
    # short of the crop box.
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, math.ceil(src_w * scale))
    new_h = max(target_h, math.ceil(src_h * scale))
    scaled = clip.resized((new_w, new_h))

    focus_center = focus_x_ratio * new_w
    x1 = int(round(focus_center - target_w / 2))
    x1 = max(0, min(x1, new_w - target_w))
    y1 = max(0, (new_h - target_h) // 2)
    return scaled.cropped(x1=x1, y1=y1, width=target_w, height=target_h)


def punch_in_zoom(clip):
    """Apply an eased punch-in zoom, keeping the frame size constant.

    Each frame is scaled up by ``_zoom_factor(t)`` and center-cropped back to
    the original size, so the clip's declared ``size`` is unchanged.
    """
    frame_w, frame_h = clip.size

    def zoom(get_frame, t):
        frame = get_frame(t)
        factor = _zoom_factor(t)
        if factor <= 1.0:
            return frame
        zoomed_w = max(frame_w, int(round(frame_w * factor)))
        zoomed_h = max(frame_h, int(round(frame_h * factor)))
        resized = cv2.resize(frame, (zoomed_w, zoomed_h), interpolation=cv2.INTER_LINEAR)
        x0 = (zoomed_w - frame_w) // 2
        y0 = (zoomed_h - frame_h) // 2
        return resized[y0:y0 + frame_h, x0:x0 + frame_w]

    return clip.transform(zoom)


def apply_fades(clip):
    """Fade the clip in and out at both ends (video + audio).

    Best-effort and config-gated: returns ``clip`` unchanged when fades are
    disabled, the duration is non-positive, or the clip has no duration. On very
    short clips the fade is capped at half the duration so the in/out don't
    overlap into a permanently-dark clip. Audio (when present) is faded too.
    """
    if not CONFIG.FADE_ENABLED:
        return clip
    if clip.duration is None or CONFIG.FADE_DURATION <= 0:
        return clip

    fade = min(CONFIG.FADE_DURATION, clip.duration / 2.0)
    if fade <= 0:
        return clip

    from moviepy import afx, vfx

    clip = clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)])
    if clip.audio is not None:
        faded_audio = clip.audio.with_effects(
            [afx.AudioFadeIn(fade), afx.AudioFadeOut(fade)]
        )
        clip = clip.with_audio(faded_audio)
    return clip


def _watermark_position(logo_w: int, logo_h: int, frame_w: int, frame_h: int,
                        margin: int) -> tuple:
    """Pixel ``(x, y)`` for the watermark given the configured corner + margin.

    Positions are relative to the *actual* composited frame (``frame_w`` x
    ``frame_h``) so the logo lands correctly for any aspect preset (B5).
    """
    pos = CONFIG.WATERMARK_POSITION
    if pos == "center":
        return ("center", "center")
    x = margin if "left" in pos else frame_w - logo_w - margin
    y = margin if "top" in pos else frame_h - logo_h - margin
    return (int(x), int(y))


def apply_watermark(clip):
    """Composite the configured logo/watermark PNG onto ``clip``.

    Best-effort and config-gated: returns ``clip`` unchanged when the watermark
    is disabled or the file is missing/unreadable. The logo is scaled to
    ``WATERMARK_WIDTH_RATIO`` of the target width, placed in the configured
    corner with ``WATERMARK_MARGIN`` padding, and drawn at ``WATERMARK_OPACITY``.
    A PNG's own alpha channel is respected. Audio is preserved.
    """
    if not CONFIG.WATERMARK_ENABLED:
        return clip
    if not Path(CONFIG.WATERMARK_PATH).is_file():
        return clip

    try:
        from moviepy import CompositeVideoClip, ImageClip

        logo = ImageClip(str(CONFIG.WATERMARK_PATH))
        # Size + margin scale to the actual frame, not the 9:16 constants, so
        # the watermark stays proportional across aspect presets (B5).
        frame_w, frame_h = clip.size
        width_ratio = frame_w / CONFIG.CAPTION_REFERENCE_WIDTH
        target_logo_w = int(CONFIG.WATERMARK_WIDTH_RATIO * frame_w)
        if logo.w and target_logo_w > 0:
            logo = logo.resized(width=target_logo_w)
        scaled_margin = int(round(CONFIG.WATERMARK_MARGIN * width_ratio))
        logo = (
            logo.with_duration(clip.duration)
            .with_opacity(CONFIG.WATERMARK_OPACITY)
            .with_position(_watermark_position(logo.w, logo.h, frame_w, frame_h, scaled_margin))
        )
        out = CompositeVideoClip([clip, logo]).with_duration(clip.duration)
        if clip.audio is not None:
            out = out.with_audio(clip.audio)
        return out
    except Exception:  # noqa: BLE001 - watermark is best-effort; keep the render
        return clip


_FACE_CASCADE = None


def _face_cascade():
    """Lazily load the bundled OpenCV frontal-face Haar cascade (or ``None``)."""
    global _FACE_CASCADE
    if _FACE_CASCADE is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(path)
        _FACE_CASCADE = cascade if not cascade.empty() else False
    return _FACE_CASCADE or None


def detect_focus_x_ratio(clip, samples: int = 3) -> float:
    """Estimate the subject's horizontal position as a 0..1 ratio of width.

    Samples a few frames across the clip, runs face detection on each, and
    averages the horizontal center of the largest face found. Returns ``0.5``
    (centered) when the cascade is unavailable or no face is detected, so the
    caller always gets a usable focus point.
    """
    cascade = _face_cascade()
    if cascade is None or clip.duration is None or clip.duration <= 0:
        return 0.5

    centers: list[float] = []
    times = [clip.duration * (i + 1) / (samples + 1) for i in range(samples)]
    for t in times:
        frame = clip.get_frame(t)
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) == 0:
            continue
        x, _y, w, _h = max(faces, key=lambda f: f[2] * f[3])
        centers.append((x + w / 2) / frame.shape[1])

    if not centers:
        return 0.5
    return float(np.clip(np.mean(centers), 0.0, 1.0))
