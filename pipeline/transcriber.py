"""Module 2 — Transcription.

faster-whisper (CPU, int8) -> transcript.json with word-level timestamps.
Output schema matches sample_transcript.json.

Flow: extract the video's audio to a 16 kHz mono WAV with ffmpeg, transcribe
that WAV with word-level timestamps, then serialize to the shared schema. The
extracted ``audio.wav`` is intentionally left in ``work_dir`` so Module 3 can
reuse it for librosa RMS energy instead of re-extracting.

The ``transcribe`` signature is the stable contract the orchestrator calls.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path

from faster_whisper import WhisperModel

from config import CONFIG

# A WhisperModel is expensive to construct (loads weights into memory). The
# orchestrator runs jobs in background threads, so build it once and share it.
_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _get_model() -> WhisperModel:
    """Return the shared WhisperModel, constructing it on first use."""
    global _model
    with _model_lock:
        if _model is None:
            _model = WhisperModel(
                CONFIG.WHISPER_MODEL,
                device=CONFIG.WHISPER_DEVICE,
                compute_type=CONFIG.WHISPER_COMPUTE_TYPE,
            )
        return _model


def _extract_audio(video_path: Path, work_dir: Path) -> Path:
    """Extract a 16 kHz mono WAV from the video via ffmpeg.

    Returns the path to ``work_dir / "audio.wav"``. Raises ``RuntimeError`` if
    ffmpeg is missing or fails.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it (Windows: 'winget install "
            "Gyan.FFmpeg'; Ubuntu: 'sudo apt install ffmpeg')."
        )

    audio_path = work_dir / "audio.wav"
    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-vn",                              # drop video
        "-ac", "1",                         # mono
        "-ar", str(CONFIG.AUDIO_SAMPLE_RATE),  # 16 kHz
        "-f", "wav",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip().splitlines()[-10:]
        raise RuntimeError(
            "ffmpeg failed to extract audio from "
            f"{video_path.name}:\n" + "\n".join(stderr_tail)
        )
    return audio_path


def _probe_duration(audio_path: Path) -> float:
    """Return the audio duration in seconds via ffprobe, or 0.0 if unavailable."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 0.0
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True,
    )
    try:
        return round(float(proc.stdout.strip()), 2)
    except (ValueError, AttributeError):
        return 0.0


def transcribe(video_path: Path, work_dir: Path) -> dict:
    """Transcribe a video into a word-level transcript.

    Args:
        video_path: the uploaded source video.
        work_dir: per-job directory to write ``audio.wav`` and
            ``transcript.json`` into.

    Returns:
        The transcript dict matching ``sample_transcript.json`` (also written
        to ``work_dir / "transcript.json"``).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = _extract_audio(video_path, work_dir)

    model = _get_model()

    def _run(vad: bool):
        return model.transcribe(
            str(audio_path),
            word_timestamps=True,
            beam_size=CONFIG.WHISPER_BEAM_SIZE,
            vad_filter=vad,
        )

    # faster-whisper raises ValueError from language detection when the audio
    # has no speech (e.g. VAD stripped everything, or a silent/music-only clip).
    # Retry once with VAD off, then fall back to a valid empty transcript so the
    # job doesn't die on a cryptic error.
    try:
        segments, info = _run(CONFIG.WHISPER_VAD_FILTER)
        language = info.language
        duration = round(info.duration, 2)
    except ValueError:
        if CONFIG.WHISPER_VAD_FILTER:
            try:
                segments, info = _run(False)
                language = info.language
                duration = round(info.duration, 2)
            except ValueError:
                segments, language, duration = [], "unknown", _probe_duration(audio_path)
        else:
            segments, language, duration = [], "unknown", _probe_duration(audio_path)

    out_segments: list[dict] = []
    for index, segment in enumerate(segments):
        words = [
            {
                "word": word.word.strip(),
                "start": round(word.start, 2),
                "end": round(word.end, 2),
            }
            for word in (segment.words or [])
        ]
        out_segments.append({
            "id": index,
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": words,
        })

    transcript = {
        "language": language,
        "duration": duration,
        "segments": out_segments,
    }

    transcript_path = work_dir / "transcript.json"
    with transcript_path.open("w", encoding="utf-8") as fh:
        json.dump(transcript, fh, ensure_ascii=False, indent=2)

    return transcript
