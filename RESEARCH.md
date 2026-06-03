# RESEARCH.md — Design Decisions & Trade-offs

Running log of why we chose each approach. Filled in as modules are built.

## Transcription (Module 2)
- **faster-whisper** over openai-whisper: 4x faster on CPU via CTranslate2, int8.
- Default model `base`: best speed/accuracy balance on an i5. Configurable.
- Word-level timestamps (`word_timestamps=True`) are required for caption sync.

## Clip Scoring (Module 3)
- Heuristic scoring (no LLM) to stay 100% local and fast:
  - Hook/keyword matching (English + Roman Urdu)
  - Sentence length filter (8–30 words)
  - Pause detection (>1.5s) for natural cut points
  - Audio RMS energy (librosa) — louder/energetic = more engaging
  - Repetition penalty
- Selection: greedy, non-overlapping, top-N by score.
- **Researched but deferred:** sentence-transformers semantic clustering,
  pyannote.audio diarization (heavier; not needed for v1).

## Captions (Module 5)
- **Option A** — ffmpeg `drawtext`: fast, but per-word color animation is hard.
- **Option B** — moviepy `TextClip` per word: full control over highlight/color,
  slower render. Leaning B for the animated look.
- Decision: TBD when Module 5 starts.

## Effects (Module 4)
- Punch-in zoom 1.0x -> 1.15x over ~1.5s via frame transform (cv2.resize + center crop).
- 9:16 crop: detect/center subject; optional OpenCV face detection (stretch).

## Cross-platform notes
- All paths via `pathlib` + `config.py`; no `\\` or `/` hardcoding.
- ffmpeg is a system dependency on both Windows and Ubuntu.
