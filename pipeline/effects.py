"""Module 4 & 5 — Effects.

Video effects applied during rendering:

  * ``reframe_to_vertical`` — scale-to-cover + crop a clip to 9:16 (1080x1920),
    optionally biasing the horizontal crop toward a detected face.
  * ``punch_in_zoom`` — a constant-size frame transform that eases from
    ``ZOOM_START`` to ``ZOOM_END`` over ``ZOOM_DURATION`` seconds, then holds.
  * ``detect_focus_x_ratio`` — OpenCV face detection (stretch) used to pick the
    crop's horizontal focus point.

Design (see RESEARCH.md): the reframe uses moviepy's own ``resized``/``cropped``
effects so the clip's declared ``size`` stays correct for the encoder. The zoom
is a custom cv2 frame transform whose output dimensions never change, so it is
safe to chain after the reframe without confusing the writer. Word-synced
animated captions (Phase 5) will live here too.
"""

from __future__ import annotations

import math

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


def reframe_to_vertical(clip, focus_x_ratio: float = 0.5):
    """Scale-to-cover and crop ``clip`` to the configured 9:16 dimensions.

    The source is scaled so it fully covers the target (no letterboxing), then
    cropped: vertically centered, horizontally centered on ``focus_x_ratio``
    (0.0 = left edge, 1.0 = right edge) of the *scaled* frame.

    Returns a clip whose ``size`` is exactly ``(TARGET_WIDTH, TARGET_HEIGHT)``.
    """
    target_w, target_h = CONFIG.TARGET_WIDTH, CONFIG.TARGET_HEIGHT
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
