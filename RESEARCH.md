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
  slower render.
- **Decision: Option B (moviepy `TextClip`).** Style = one large word at a time,
  centered in the lower third, drawn in accent **#7C3AED** with a thick black stroke,
  with a quick ease-out pop-in scale (classic viral-shorts look). Each word holds on
  screen until the next word starts (no flicker). Picked B because it gives full
  per-word color control with simple, deterministic, CPU-cheap compositing — a single
  active word avoids per-word horizontal layout/wrapping math.
- **Bundled font (important):** moviepy 2.x `TextClip(font, ...)` requires a font
  *file path* — there is no safe cross-platform system-font default. We commit an
  OFL-licensed font (**Anton**, single-weight bold display) under `assets/fonts/` so a
  fresh clone renders captions offline on Windows + Ubuntu. Overridable via
  `SHORTSMITH_CAPTION_FONT`.
- **SRT export** (`pysrt`): words are grouped into readable cues (≤7 words, breaking on
  sentence punctuation) on the clip-local timeline, saved next to the MP4 sharing its
  stem. Always written, even when the caption burn is disabled/empty.
- **Robustness:** caption building is best-effort — a missing/broken font or empty word
  list skips the burn but still produces the MP4 and an `.srt`; a job never dies here.
- Caption engine lives in `pipeline/captions.py` (text rendering + SRT I/O), kept out of
  `pipeline/effects.py` which stays focused on frame transforms.
- **Multi-style update (B1, 2026-06-13):** the single-word-pop limitation noted above was
  lifted. Added a **Hormozi** karaoke style — a short phrase (`_group_phrases`, ≤`CAPTION_HORMOZI_MAX_WORDS`,
  sentence-aware) laid out as a centered, wrap-capable line with the spoken word highlighted in
  #7C3AED over white siblings. The per-word horizontal layout/wrapping math that Option B
  originally avoided is done here by measuring each word's `TextClip.w/.h` (available
  pre-composite) and greedily packing/centering lines; the karaoke sweep is two clips per word
  (white base over the phrase window + a purple highlight over the spoken interval, composited on
  top — later = on top), so no per-word scaling that would shift the absolute layout. Style is
  chosen by `CONFIG.CAPTION_STYLE` (default `hormozi`) or per-job via the clip dict; word_pop stays
  available. SRT grouping is unchanged and style-independent.

## Effects (Module 4)
- Punch-in zoom 1.0x -> 1.15x over ~1.5s via frame transform (cv2.resize + center crop).
- 9:16 crop: detect/center subject; optional OpenCV face detection (stretch).
- **Fades:** moviepy `vfx.FadeIn/FadeOut` for video + `afx.AudioFadeIn/FadeOut` for audio, applied
  to the final composite. Capped at half the clip duration so short clips don't fade to permanent
  black. On by default (subtle 0.4s) — a softer in/out than a hard cut, the standard shorts look.
- **Watermark/logo:** an `ImageClip` PNG composited into a configurable corner (scaled to a width
  ratio of the 1080px canvas, with margin + opacity; the PNG's alpha is respected). Off by default
  with a bundled `assets/watermark.png` sample so it's testable. Applied *after* captions so the
  logo sits on top; fades run last so they cover the watermark too.
- **Order in the render chain:** `subclip → reframe → zoom → captions → watermark → fades → write`.
  Each step preserves audio and (watermark/fades) is a best-effort no-op when disabled, so a render
  never depends on them. Export uses `-movflags +faststart` for web-streamable MP4s.

## Frontend & Integration (Module 6)
- **Progress: polling, not SSE.** A 1-second `fetch('/status/<id>')` loop drives the
  UI. It's already proven from Phase 1, needs no new server deps or threading, and
  fits the in-memory job model — SSE/WebSockets would add complexity for no real gain
  at this single-user, local scale.
- **Inline previews via one query param.** The `/download` route gained an optional
  `?inline=1` that serves the file with `as_attachment=False`, so the results grid can
  play clips in a `<video>` element (Werkzeug still answers HTTP range requests, so
  seeking works) and read an `.srt` in-browser. The default (no param) keeps the
  download-as-attachment behavior. No new routes, no change to the pipeline contract.
- **SRT surfaced client-side.** Per the Phase-5 carry-forward, each clip's sibling
  `.srt` shares the MP4 stem, so the UI derives its name in JS (`.mp4` → `.srt`) and
  links/loads it through the existing download route — the orchestrator's `results`
  payload stays unchanged.
- **Built on the existing UI, not a rewrite.** The Phase-1 dark theme (`#0a0a0f` /
  `#7C3AED`) and upload+poll flow were extended into a dropzone, staged progress chips,
  and a responsive CSS-grid results layout — no framework, plain HTML/CSS/JS.

## Cross-platform notes
- All paths via `pathlib` + `config.py`; no `\\` or `/` hardcoding.
- ffmpeg is a system dependency on both Windows and Ubuntu.
