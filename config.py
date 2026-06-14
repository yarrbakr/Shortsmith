"""
Central configuration for Shortsmith.

Hard rules enforced here:
  - No hardcoded absolute paths. Everything is relative to this file's
    location (the project root) and can be overridden via environment vars.
  - Must run identically on Windows 10+ and Ubuntu 22.04.
  - 100% local, CPU-only, no paid APIs.

Import this module anywhere with `from config import CONFIG`.
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root = directory containing this file. Never hardcode paths elsewhere.
BASE_DIR = Path(__file__).resolve().parent


def _env_path(var: str, default: Path) -> Path:
    """Resolve a path from an env var, falling back to a project-relative default."""
    value = os.environ.get(var)
    return Path(value).resolve() if value else default


class Config:
    # --- Directories -------------------------------------------------------
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = _env_path("SHORTSMITH_UPLOAD_DIR", BASE_DIR / "uploads")
    OUTPUT_DIR: Path = _env_path("SHORTSMITH_OUTPUT_DIR", BASE_DIR / "shorts_output")

    # --- Upload limits -----------------------------------------------------
    ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
    MAX_UPLOAD_MB = int(os.environ.get("SHORTSMITH_MAX_UPLOAD_MB", "1024"))  # 1 GB

    # --- Transcription (Module 2) -----------------------------------------
    # faster-whisper model: tiny/base/small/medium. base = good speed/accuracy on CPU.
    WHISPER_MODEL = os.environ.get("SHORTSMITH_WHISPER_MODEL", "base")
    WHISPER_COMPUTE_TYPE = os.environ.get("SHORTSMITH_COMPUTE_TYPE", "int8")  # CPU-friendly
    WHISPER_DEVICE = "cpu"  # hard rule: CPU only
    WHISPER_BEAM_SIZE = int(os.environ.get("SHORTSMITH_BEAM_SIZE", "5"))
    # VAD drops non-speech segments -> cleaner word timing. Override with "0"/"false".
    WHISPER_VAD_FILTER = os.environ.get("SHORTSMITH_VAD_FILTER", "1").lower() not in {"0", "false", "no"}
    AUDIO_SAMPLE_RATE = 16000  # Whisper's expected rate; also the WAV extraction rate.

    # --- Scoring / Selection (Module 3) -----------------------------------
    CLIP_MIN_WORDS = 8
    CLIP_MAX_WORDS = 30
    CLIP_MIN_DURATION = 12.0   # seconds
    CLIP_MAX_DURATION = 60.0   # seconds
    TOP_N_CLIPS = int(os.environ.get("SHORTSMITH_TOP_N", "3"))
    PAUSE_THRESHOLD = 1.5      # seconds of silence = natural cut point

    # Heuristic scoring is keyword/energy based (no LLM — stays local + fast).
    # Hook phrases score higher when they land in a clip's opening words.
    # Lower-cased; matched case-insensitively. Roman Urdu is first-class here.
    HOOK_KEYWORDS_EN = [
        "here's", "here is", "the secret", "nobody tells you", "biggest mistake",
        "let me show you", "did you know", "the truth", "you won't believe",
        "the reason", "this is why", "what if", "how to", "stop", "never",
        "always", "trust me", "listen", "imagine",
    ]
    HOOK_KEYWORDS_UR = [
        "dekhiye", "dekho", "suniye", "sun lo", "asli baat", "sach ye hai",
        "yaad rakhna", "sabse bari", "raaz", "dhyan se", "trust me",
        "yaqeen karo", "samjho", "ek baat",
    ]
    # Disfluencies/filler that signal low-quality, rambling speech.
    FILLER_WORDS = {
        "um", "umm", "uh", "uhh", "er", "erm", "like", "basically", "literally",
        "actually", "yaar", "matlab", "woh", "haan", "acha", "toh",
    }
    # Multi-word fillers + outro phrases checked against clip text (substring).
    FILLER_PHRASES = ["you know", "kind of", "sort of", "i mean", "you see"]
    OUTRO_PHRASES = [
        "thanks for watching", "rest of the video", "see you next",
        "see you in the next", "subscribe", "like and share", "hit the bell",
        "that's it for", "that's all for",
    ]
    # Score weights (sum ~= 1.0). Each sub-score is normalized to 0..1.
    W_HOOK = float(os.environ.get("SHORTSMITH_W_HOOK", "0.30"))
    W_LENGTH = float(os.environ.get("SHORTSMITH_W_LENGTH", "0.15"))
    W_PAUSE = float(os.environ.get("SHORTSMITH_W_PAUSE", "0.15"))
    W_ENERGY = float(os.environ.get("SHORTSMITH_W_ENERGY", "0.20"))
    W_REPETITION = float(os.environ.get("SHORTSMITH_W_REPETITION", "0.20"))

    # Virality grade (Module 3 → UI). The weights above sum to ~1.0, so a clip's
    # blended score is already a 0..1 fraction of the theoretical maximum; it is
    # surfaced in the UI as a 0-100 "clip strength" percentage bucketed into an
    # A-F letter via these (letter, min_pct) cutoffs, highest first. This is a
    # heuristic grade, NOT a prediction of real-world views.
    GRADE_THRESHOLDS = [("A", 80), ("B", 65), ("C", 50), ("D", 35), ("F", 0)]

    # --- Rendering (Module 4) ---------------------------------------------
    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920       # 9:16 vertical
    FPS = 30
    ZOOM_START = 1.0
    ZOOM_END = 1.15
    ZOOM_DURATION = 1.5        # seconds of punch-in
    # Encoder settings (passed to ffmpeg via moviepy). x264 + aac = universally
    # playable MP4. CRF 20 = visually lossless-ish; lower = bigger/better.
    VIDEO_CODEC = os.environ.get("SHORTSMITH_VIDEO_CODEC", "libx264")
    AUDIO_CODEC = os.environ.get("SHORTSMITH_AUDIO_CODEC", "aac")
    RENDER_PRESET = os.environ.get("SHORTSMITH_RENDER_PRESET", "medium")
    RENDER_CRF = int(os.environ.get("SHORTSMITH_RENDER_CRF", "20"))
    # Subject framing for the 9:16 crop. Off = center crop (fast, deterministic).
    # On = sample frames and bias the horizontal crop toward a detected face
    # (OpenCV Haar cascade; stretch goal). Override with "1"/"true".
    FACE_DETECT = os.environ.get("SHORTSMITH_FACE_DETECT", "0").lower() in {"1", "true", "yes"}

    # Fade in/out at the clip boundaries (video + audio), for a smoother,
    # more professional in/out than a hard cut. On by default; short and subtle.
    FADE_ENABLED = os.environ.get("SHORTSMITH_FADE", "1").lower() not in {"0", "false", "no"}
    FADE_DURATION = float(os.environ.get("SHORTSMITH_FADE_DURATION", "0.4"))  # seconds, each end

    # Logo / watermark overlay (branding). Off by default; supply a PNG (ideally
    # with transparency) and flip it on. A sample is bundled at assets/watermark.png.
    WATERMARK_ENABLED = os.environ.get("SHORTSMITH_WATERMARK", "0").lower() in {"1", "true", "yes"}
    WATERMARK_PATH: Path = _env_path(
        "SHORTSMITH_WATERMARK_PATH", BASE_DIR / "assets" / "watermark.png"
    )
    # Corner placement: top-left / top-right / bottom-left / bottom-right / center.
    WATERMARK_POSITION = os.environ.get("SHORTSMITH_WATERMARK_POSITION", "top-right").lower()
    WATERMARK_OPACITY = float(os.environ.get("SHORTSMITH_WATERMARK_OPACITY", "0.85"))
    WATERMARK_WIDTH_RATIO = float(os.environ.get("SHORTSMITH_WATERMARK_WIDTH", "0.22"))  # of TARGET_WIDTH
    WATERMARK_MARGIN = int(os.environ.get("SHORTSMITH_WATERMARK_MARGIN", "40"))  # px from edges

    # --- Captions / Subtitles (Module 5) ----------------------------------
    # Word-synced animated captions burned onto each clip + an SRT export.
    # Two styles are available (see CAPTION_STYLE below): "hormozi" (default) —
    # a short phrase on screen with the spoken word highlighted, karaoke-style —
    # and "word_pop" — one large word at a time with a quick pop-in scale (the
    # original Phase-5 look). All env-overridable; no hardcoded paths.
    CAPTION_ENABLED = os.environ.get("SHORTSMITH_CAPTIONS", "1").lower() not in {"0", "false", "no"}
    # moviepy 2.x TextClip needs a real font FILE. We bundle an OFL font so a
    # fresh clone works offline on Windows + Ubuntu without a system font.
    CAPTION_FONT: Path = _env_path(
        "SHORTSMITH_CAPTION_FONT", BASE_DIR / "assets" / "fonts" / "Anton-Regular.ttf"
    )
    CAPTION_FONT_SIZE = int(os.environ.get("SHORTSMITH_CAPTION_FONT_SIZE", "120"))
    CAPTION_COLOR = os.environ.get("SHORTSMITH_CAPTION_COLOR", "white")
    CAPTION_HIGHLIGHT_COLOR = os.environ.get("SHORTSMITH_CAPTION_HIGHLIGHT", "#7C3AED")
    CAPTION_STROKE_COLOR = os.environ.get("SHORTSMITH_CAPTION_STROKE", "black")
    CAPTION_STROKE_WIDTH = int(os.environ.get("SHORTSMITH_CAPTION_STROKE_WIDTH", "8"))
    # Vertical center of the caption as a fraction of height (0.72 = lower third).
    CAPTION_POSITION_RATIO = float(os.environ.get("SHORTSMITH_CAPTION_POSITION", "0.72"))
    # Keep a word inside this fraction of the width; shrink the font if it overflows.
    CAPTION_MAX_WIDTH_RATIO = float(os.environ.get("SHORTSMITH_CAPTION_MAX_WIDTH", "0.9"))
    CAPTION_UPPERCASE = os.environ.get("SHORTSMITH_CAPTION_UPPERCASE", "1").lower() not in {"0", "false", "no"}
    CAPTION_POP_DURATION = float(os.environ.get("SHORTSMITH_CAPTION_POP", "0.12"))  # scale-in seconds
    # ±tolerance used to hold a word on screen across tiny inter-word gaps (no flicker).
    CAPTION_SYNC_TOLERANCE = float(os.environ.get("SHORTSMITH_CAPTION_SYNC", "0.3"))
    # Words per SRT cue (readable subtitle grouping).
    SRT_MAX_WORDS_PER_LINE = int(os.environ.get("SHORTSMITH_SRT_MAX_WORDS", "7"))

    # --- Caption style selector (B1) --------------------------------------
    # "hormozi" = a short phrase on screen with the spoken word highlighted in
    # CAPTION_HIGHLIGHT_COLOR (karaoke feel; default). "word_pop" = one big word
    # with a pop-in (the original Phase-5 look). Env-overridable; validated
    # against CAPTION_STYLES (an unknown value falls back to "word_pop").
    CAPTION_STYLE = os.environ.get("SHORTSMITH_CAPTION_STYLE", "hormozi").lower()
    CAPTION_STYLES = ("word_pop", "hormozi")  # allowed registry
    # Hormozi: max words shown together before forcing a new phrase (also breaks
    # on sentence punctuation). Kept at 3 so lines stay short with comfortable
    # side margins; longer phrases still wrap within CAPTION_MAX_WIDTH_RATIO.
    CAPTION_HORMOZI_MAX_WORDS = int(os.environ.get("SHORTSMITH_HORMOZI_MAX_WORDS", "3"))
    # Horizontal gap between words in a phrase / vertical gap between wrapped lines (px).
    CAPTION_HORMOZI_WORD_SPACING = int(os.environ.get("SHORTSMITH_HORMOZI_WORD_SPACING", "24"))
    CAPTION_HORMOZI_LINE_SPACING = int(os.environ.get("SHORTSMITH_HORMOZI_LINE_SPACING", "16"))

    # --- Platform export presets (B5) -------------------------------------
    # One output aspect ratio per job, chosen from ASPECT_PRESETS (label ->
    # (width, height) in px). Each preset's dimensions are even (required by
    # libx264 yuv420p) and keep one side at the established 1080/1920 base. The
    # default "9:16" reuses TARGET_WIDTH/TARGET_HEIGHT, so that render path is
    # unchanged. Downstream caption/watermark geometry derives from the ACTUAL
    # rendered frame (see captions.py / effects.py), scaled by width vs
    # CAPTION_REFERENCE_WIDTH — never from TARGET_WIDTH/HEIGHT directly.
    ASPECT_PRESETS = {
        "9:16": (1080, 1920),  # vertical (default; identical to legacy render)
        "1:1": (1080, 1080),   # square (Instagram feed)
        "4:5": (1080, 1350),   # portrait (Instagram / Pinterest)
        "16:9": (1920, 1080),  # landscape (YouTube / web)
    }
    ASPECT_RATIOS = tuple(ASPECT_PRESETS.keys())  # allowed registry
    # Labels contain a colon and are case-sensitive — no .lower(). An unknown
    # value would break rendering (no size), so fall back hard to the default.
    ASPECT_RATIO = os.environ.get("SHORTSMITH_ASPECT_RATIO", "9:16")
    if ASPECT_RATIO not in ASPECT_PRESETS:
        ASPECT_RATIO = "9:16"
    # Reference width for proportional caption/watermark sizing. Fixed at the
    # legacy 9:16 width so the default render stays pixel-identical (ratio = 1.0).
    CAPTION_REFERENCE_WIDTH = 1080

    # --- App ---------------------------------------------------------------
    SECRET_KEY = os.environ.get("SHORTSMITH_SECRET_KEY", "dev-key-change-me")
    HOST = os.environ.get("SHORTSMITH_HOST", "127.0.0.1")
    PORT = int(os.environ.get("SHORTSMITH_PORT", "5000"))

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create runtime directories if missing. Safe to call repeatedly."""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


CONFIG = Config
