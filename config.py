"""
Central configuration for AutoShorts AI.

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
    UPLOAD_DIR: Path = _env_path("AUTOSHORTS_UPLOAD_DIR", BASE_DIR / "uploads")
    OUTPUT_DIR: Path = _env_path("AUTOSHORTS_OUTPUT_DIR", BASE_DIR / "shorts_output")

    # --- Upload limits -----------------------------------------------------
    ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
    MAX_UPLOAD_MB = int(os.environ.get("AUTOSHORTS_MAX_UPLOAD_MB", "1024"))  # 1 GB

    # --- Transcription (Module 2) -----------------------------------------
    # faster-whisper model: tiny/base/small/medium. base = good speed/accuracy on CPU.
    WHISPER_MODEL = os.environ.get("AUTOSHORTS_WHISPER_MODEL", "base")
    WHISPER_COMPUTE_TYPE = os.environ.get("AUTOSHORTS_COMPUTE_TYPE", "int8")  # CPU-friendly
    WHISPER_DEVICE = "cpu"  # hard rule: CPU only
    WHISPER_BEAM_SIZE = int(os.environ.get("AUTOSHORTS_BEAM_SIZE", "5"))
    # VAD drops non-speech segments -> cleaner word timing. Override with "0"/"false".
    WHISPER_VAD_FILTER = os.environ.get("AUTOSHORTS_VAD_FILTER", "1").lower() not in {"0", "false", "no"}
    AUDIO_SAMPLE_RATE = 16000  # Whisper's expected rate; also the WAV extraction rate.

    # --- Scoring / Selection (Module 3) -----------------------------------
    CLIP_MIN_WORDS = 8
    CLIP_MAX_WORDS = 30
    CLIP_MIN_DURATION = 12.0   # seconds
    CLIP_MAX_DURATION = 60.0   # seconds
    TOP_N_CLIPS = int(os.environ.get("AUTOSHORTS_TOP_N", "3"))
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
    W_HOOK = float(os.environ.get("AUTOSHORTS_W_HOOK", "0.30"))
    W_LENGTH = float(os.environ.get("AUTOSHORTS_W_LENGTH", "0.15"))
    W_PAUSE = float(os.environ.get("AUTOSHORTS_W_PAUSE", "0.15"))
    W_ENERGY = float(os.environ.get("AUTOSHORTS_W_ENERGY", "0.20"))
    W_REPETITION = float(os.environ.get("AUTOSHORTS_W_REPETITION", "0.20"))

    # --- Rendering (Module 4) ---------------------------------------------
    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920       # 9:16 vertical
    FPS = 30
    ZOOM_START = 1.0
    ZOOM_END = 1.15
    ZOOM_DURATION = 1.5        # seconds of punch-in
    # Encoder settings (passed to ffmpeg via moviepy). x264 + aac = universally
    # playable MP4. CRF 20 = visually lossless-ish; lower = bigger/better.
    VIDEO_CODEC = os.environ.get("AUTOSHORTS_VIDEO_CODEC", "libx264")
    AUDIO_CODEC = os.environ.get("AUTOSHORTS_AUDIO_CODEC", "aac")
    RENDER_PRESET = os.environ.get("AUTOSHORTS_RENDER_PRESET", "medium")
    RENDER_CRF = int(os.environ.get("AUTOSHORTS_RENDER_CRF", "20"))
    # Subject framing for the 9:16 crop. Off = center crop (fast, deterministic).
    # On = sample frames and bias the horizontal crop toward a detected face
    # (OpenCV Haar cascade; stretch goal). Override with "1"/"true".
    FACE_DETECT = os.environ.get("AUTOSHORTS_FACE_DETECT", "0").lower() in {"1", "true", "yes"}

    # --- App ---------------------------------------------------------------
    SECRET_KEY = os.environ.get("AUTOSHORTS_SECRET_KEY", "dev-key-change-me")
    HOST = os.environ.get("AUTOSHORTS_HOST", "127.0.0.1")
    PORT = int(os.environ.get("AUTOSHORTS_PORT", "5000"))

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create runtime directories if missing. Safe to call repeatedly."""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


CONFIG = Config
