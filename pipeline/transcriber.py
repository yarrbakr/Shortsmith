"""Module 2 — Transcription.

faster-whisper (CPU, int8) -> transcript.json with word-level timestamps.
Output schema matches sample_transcript.json.

The signature below is the stable contract the orchestrator calls; Phase 2
fills in the body.
"""

from __future__ import annotations

from pathlib import Path


def transcribe(video_path: Path, work_dir: Path) -> dict:
    """Transcribe a video into a word-level transcript.

    Args:
        video_path: the uploaded source video.
        work_dir: per-job directory to write ``transcript.json`` into.

    Returns:
        The transcript dict matching ``sample_transcript.json`` (also written
        to ``work_dir / "transcript.json"``).
    """
    raise NotImplementedError("Transcription not implemented yet (Phase 2).")
