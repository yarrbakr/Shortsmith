# AutoShorts AI — Project Progress Tracker

> **Purpose:** A single source of truth for where the project stands, so progress
> isn't lost across chats/sessions. Update this file at the end of every phase.

**Repo:** https://github.com/yarrbakr/Autoshort
**Goal:** 100% local, free, CPU-only web app that turns long videos into 9:16
vertical shorts with burned-in animated captions. Open-source.

**Hard rules (non-negotiable):**
- No paid APIs / cloud / subscriptions — everything runs locally on CPU.
- No hardcoded paths — use `config.py` (relative paths + env overrides).
- Must run on Windows 10+ **and** Ubuntu 22.04 without modification.
- Environment: **Python 3.12** (3.13 breaks `av`/`numpy` wheel installs).

---

## Status at a glance

| Phase | Module | Status | Depends on |
|------|--------|--------|-----------|
| 0 | Scaffold & Setup | ✅ **Done** | — |
| 1 | Backend & Upload | ✅ **Done** | 0 |
| 2 | Transcription | ✅ **Done** | 1 |
| 3 | Scoring & Selection | ✅ **Done** | 2 (or sample_transcript.json) |
| 4 | Rendering & Effects | ✅ **Done** | 3 |
| 5 | Animated Captions & SRT | ✅ **Done** | 4 |
| 6 | Frontend & Integration | ⬜ Not started | 1–5 |

Legend: ✅ Done · 🟡 In progress · ⬜ Not started

---

## Phase 0 — Scaffold & Setup ✅
**Depends on:** nothing.
**Goal:** Working environment, repo structure, and project skeleton.

- [x] Python 3.12 venv created
- [x] ffmpeg installed and on PATH (v8.1.1)
- [x] `config.py` — central config, no hardcoded paths, Win+Ubuntu safe
- [x] `requirements.txt` — all deps pinned, installed successfully
- [x] `.gitignore` — ignores venv, media, model cache, internal docs
- [x] Folder structure: `pipeline/`, `static/`, `templates/`, `uploads/`, `shorts_output/`
- [x] Module stub files in `pipeline/`
- [x] `README.md` + `RESEARCH.md`
- [x] `sample_transcript.json` — fake word-level transcript for offline Phase 3 testing
- [x] `app.py` boots; `/health` returns 200; runtime dirs auto-create
- [x] Git repo initialized and pushed to GitHub (`main`)

---

## Phase 1 — Backend & Upload Management ✅
**Module 1.** **Depends on:** Phase 0.
**Goal:** Accept a video, validate + store it, create a job, and expose the
processing lifecycle via routes. (No AI yet — this is the backbone.)

**Deliverables:**
- [x] Upload page (basic form — full UI is Phase 6)
- [x] `POST /upload` — validate extension + size, save to `uploads/` with safe unique name
- [x] `GET /status/<job_id>` — live progress as JSON
- [x] `GET /results/<job_id>` — finished clips for a job
- [x] `GET /download/<job_id>/<file>` — download a generated short (path-traversal guarded)
- [x] Job manager — in-memory job registry (id, status, progress %, message, error, results)
- [x] Background-thread processing so the request doesn't block
- [x] Stage orchestrator: transcribe → score → select → render (calls pipeline interface)
- [x] Defined pipeline function signatures (stable contract for Phases 2–5)

**Done when:** uploading a small `.mp4` validates + saves it, creates a job, and
`/status/<id>` reports progress (stopping cleanly at the first unimplemented stage).

---

## Phase 2 — AI Transcription ✅
**Module 2.** **Depends on:** Phase 1.
**Goal:** Convert a video's audio into a word-level transcript.

**Deliverables:**
- [x] `transcriber.py` using faster-whisper (CPU, int8)
- [x] Extract audio from the uploaded video (ffmpeg) → 16 kHz mono `audio.wav` in `work_dir`
- [x] Generate `transcript.json` matching `sample_transcript.json` schema
- [x] Word-level timestamps (`word_timestamps=True`) — required for caption sync
- [x] Model size configurable via `config.py` (default `base`)
- [x] Wired into the job orchestrator (real "transcribing" stage)

**Done when:** an uploaded video produces a valid word-level `transcript.json`. ✅

**Notes:**
- Cached `WhisperModel` singleton (thread-safe) so the model loads once across jobs.
- New config tunables: `WHISPER_BEAM_SIZE` (5), `WHISPER_VAD_FILTER` (on), `AUDIO_SAMPLE_RATE`
  (16000) — all env-overridable.
- No-speech robustness: VAD can strip all audio on silent/music-only clips, which makes
  faster-whisper's language detection raise `ValueError`. Handled by retrying once with VAD
  off, then falling back to a valid empty transcript (`language="unknown"`, duration via
  ffprobe) so a job never dies on a cryptic error.

---

## Phase 3 — AI Clip Selection & Scoring ✅
**Module 3.** **Depends on:** Phase 2 (can develop against `sample_transcript.json`).
**Goal:** Pick the best N candidate clips from the transcript.

**Deliverables:**
- [x] `scorer.py` — scores candidate segments by:
  - [x] Hook / keyword matching (English + Roman Urdu)
  - [x] Sentence length filter (8–30 words)
  - [x] Pause detection (>1.5s = natural cut point)
  - [x] Audio RMS energy (librosa)
  - [x] Repetition penalty
- [x] `selector.py` — greedy, non-overlapping selection of top-N clips
- [x] Output: ranked clip list with start/end times + scores
- [x] Wired into the job orchestrator (real "scoring/selecting" stage)

**Done when:** given a transcript, it returns the top-N non-overlapping clips ranked by score. ✅

**Notes:**
- **No new tunables hardcoded.** Hook lists (`HOOK_KEYWORDS_EN/UR`), `FILLER_WORDS`/`FILLER_PHRASES`,
  `OUTRO_PHRASES`, and the five score weights (`W_HOOK/_LENGTH/_PAUSE/_ENERGY/_REPETITION`, env-overridable)
  all live in `config.py` alongside the existing clip thresholds.
- **Candidate generation:** words are flattened across segments, split into sentence units at a
  `>PAUSE_THRESHOLD` gap *or* sentence punctuation, then a sliding window emits every duration-valid
  `[CLIP_MIN_DURATION, CLIP_MAX_DURATION]` run (de-duped). Over-long pause-free monologues are split into
  duration-bounded chunks so they still yield candidates.
- **Word/duration tension resolved:** duration is the hard clip bound; the 8–30 word range is a
  per-candidate *length sub-score* (peaks in-range, tapers outside), not a hard cap — 12 s clips
  routinely exceed 30 words.
- **Energy reuses Phase-2 `audio.wav`** at `video_path.parent/"audio.wav"` (loaded once via librosa,
  frame-wise RMS ÷ global mean, squashed to 0..1). Missing file / import error → neutral `0.5`, so
  offline scoring and empty-transcript jobs never crash.
- **Empty transcript → `[]`** from both `score()` and `select()`; the orchestrator then completes the
  job with "0 clip(s)" rather than erroring.
- Verified offline against `sample_transcript.json`: 14 candidates → top picks are the two strong hooks
  ("Let me show you the three steps…" 0.83, "Here is the secret nobody tells you…" 0.76); the filler
  ("So um, yeah, you know, like…") and outro segments are excluded; results are non-overlapping. The
  librosa energy path was confirmed with a synthetic quiet/loud WAV (0.10 vs 0.90). `/health` still 200.

---

## Phase 4 — Video Rendering & Effects ✅
**Module 4.** **Depends on:** Phase 3.
**Goal:** Turn selected clip time-ranges into 9:16 vertical video files.

**Deliverables:**
- [x] `renderer.py` — cut clip, reframe to 9:16 (1080×1920), export MP4
- [x] `effects.py` — punch-in zoom (1.0x → 1.15x over ~1.5s)
- [x] Center/subject crop (optional OpenCV face detection — stretch, off by default)
- [x] Output clips saved to `shorts_output/<job_id>/`
- [x] Wired into the job orchestrator (real "rendering" stage)

**Done when:** selected clips render as 9:16 MP4s with the zoom effect. ✅

**Notes:**
- **Reframe = scale-to-cover + crop.** Source is scaled (ceil) so it fully covers
  1080×1920 (no letterboxing), then cropped — vertically centered, horizontally on a
  `focus_x_ratio`. Done with moviepy's own `resized`/`cropped` so the clip's declared
  `size` stays correct for the encoder.
- **Zoom is a constant-size cv2 transform.** `punch_in_zoom` scales each frame by an eased
  `ZOOM_START→ZOOM_END` factor (held flat after `ZOOM_DURATION`) and center-crops back to the
  same dimensions — so chaining it after the reframe never changes `clip.size`. This is *why*
  the reframe uses moviepy effects (size-tracking) and the zoom uses a raw frame transform.
- **Subject framing resolved:** center crop is the default (fast, deterministic). Optional
  Haar-cascade face detection (`AUTOSHORTS_FACE_DETECT=1`) samples 3 frames and biases the
  horizontal crop toward the largest detected face; falls back to center when no face/cascade.
- New `config.py` tunables (all env-overridable): `VIDEO_CODEC` (libx264), `AUDIO_CODEC` (aac),
  `RENDER_PRESET` (medium), `RENDER_CRF` (20), `FACE_DETECT` (off).
- No `app.py`/`orchestrator.py` changes — the `render(video_path, clip, out_dir)` stage contract
  was already wired; this just fills the stub body.
- Verified: 20s 1280×720 test source → clip `[3.0, 16.5]` rendered to a 1080×1920 h264/30fps MP4,
  13.5s, stereo aac. End past source duration is clamped; non-positive duration raises. Zoom factor
  ramps 1.0→1.075@0.75s→1.15 (held); transform is identity at t=0 and magnifies later, shape
  preserved. `/health` still 200.

---

## Phase 5 — Animated Captions & Subtitle System ✅
**Module 5.** **Depends on:** Phase 4.
**Goal:** Burn word-synced animated captions onto the rendered clips + export SRT.

**Deliverables:**
- [x] Caption overlay engine (moviepy `TextClip`) — **Option B**, in `pipeline/captions.py`
- [x] Word-level highlight/animation synced to timestamps (±0.3s hold tolerance)
- [x] Captions burned into the final video
- [x] SRT subtitle export per clip (`pysrt`)
- [x] Wired into the render stage

**Done when:** final clips have animated word-synced captions burned in + an `.srt` file. ✅

**Notes:**
- **Style = single-word pop** (Option B resolved): one large word at a time, centered in the
  lower third (`CAPTION_POSITION_RATIO` 0.72), drawn in accent **#7C3AED** with a thick black
  stroke, with an ease-out pop-in scale (`_pop_scale`, 0.7→1.0 over `CAPTION_POP_DURATION`).
  Each word holds until the next word starts (no flicker); the last word lingers
  `CAPTION_SYNC_TOLERANCE` (0.3s). Chose single active word over phrase-karaoke to avoid
  per-word horizontal layout/wrapping while keeping full color control.
- **Bundled font (cross-platform):** moviepy 2.x `TextClip(font, …)` needs a font *file path* —
  no safe system default. Committed **Anton** (OFL, bold display) under `assets/fonts/`; path is
  `CONFIG.CAPTION_FONT`, env-overridable via `AUTOSHORTS_CAPTION_FONT`. `assets/` is not gitignored
  so a fresh clone renders captions offline.
- **`pipeline/captions.py`** (new module, not in `effects.py`): `_local_words` offsets each clip's
  source-timeline words by `clip["start"]` and clamps to `[0, duration]` (single source of truth for
  both burn + SRT); `build_word_clips` makes positioned/timed pop-in `TextClip`s (shrinks font once if
  a long word overflows `CAPTION_MAX_WIDTH_RATIO`); `write_srt` groups words into ≤`SRT_MAX_WORDS_PER_LINE`
  cues (breaking on sentence punctuation) via `pysrt`; `apply_captions` composites + always writes the
  sibling `.srt`.
- **Robustness:** caption build is best-effort — disabled/empty words or a missing/broken font skip the
  burn but still write the MP4 **and** an `.srt`; per-word `TextClip` failures are skipped. A job never
  dies in this stage (mirrors the Phase-2/3 fallback pattern).
- **No `app.py`/`orchestrator.py`/`renderer.render`-signature changes** — captions slot into the render
  chain via one call before `write_videofile`. New `config.py` tunables (all env-overridable):
  `CAPTION_ENABLED`, `CAPTION_FONT`, `CAPTION_FONT_SIZE`, `CAPTION_COLOR`, `CAPTION_HIGHLIGHT_COLOR`,
  `CAPTION_STROKE_COLOR`/`_WIDTH`, `CAPTION_POSITION_RATIO`, `CAPTION_MAX_WIDTH_RATIO`, `CAPTION_UPPERCASE`,
  `CAPTION_POP_DURATION`, `CAPTION_SYNC_TOLERANCE`, `SRT_MAX_WORDS_PER_LINE`.
- Verified: `sample_transcript.json` segment → 25 local words (first @0.0, monotonic, clamped) → 5 SRT
  cues; full render of a 20s synthetic source → 1080×1920 h264/aac/12.37s MP4 with ~18.5k accent-purple +
  ~10k black-stroke caption pixels in the lower band, sibling `.srt` with cues. Robustness: empty words →
  MP4 + 0-byte `.srt`; bad font path → MP4 + valid `.srt` (burn skipped), no error. `/health` still 200.

---

## Phase 6 — Frontend UI, Integration & Testing ⬜
**Module 6.** **Depends on:** Phases 1–5.
**Goal:** Polished UI and a fully integrated, end-to-end working app.

> **Carry-forward from Phase 1:** a *minimal* upload form + `/status` polling already
> exists (`templates/index.html`, `static/app.js`, `static/style.css`, dark `#0a0a0f` /
> `#7C3AED` palette). Phase 6 **expands/replaces** it into the full UI — this is not a
> fresh build. See the Carry-forward decisions log below.

**Deliverables:**
- [ ] `templates/index.html` — full UI (dark theme `#0a0a0f`, accent `#7C3AED`)
- [ ] `static/style.css` — responsive, mobile-friendly
- [ ] `static/app.js` — upload, live progress (polling/SSE), results grid, transcript view
- [ ] End-to-end test: 15-min video → 3 shorts in under ~15 min on an i5
- [ ] Final `README.md` (usage, screenshots) + `RESEARCH.md` (decisions)
- [ ] MIT license added before public release

**Done when:** a non-technical user can upload a video and download finished shorts from the UI.

---

## Open decisions (resolve as we go)
> Decisions still *unresolved*. Once resolved, move the outcome to the Carry-forward log
> below if it affects a later phase.
- ~~Caption rendering: ffmpeg `drawtext` (Option A) vs moviepy `TextClip` per-word (Option B).~~
  **Resolved (Phase 5):** Option B (moviepy `TextClip`), single-word pop, accent #7C3AED, bundled OFL font.
- ~~Subject framing: center crop vs OpenCV face detection.~~ **Resolved (Phase 4):** center crop
  by default; optional Haar face detection behind `AUTOSHORTS_FACE_DETECT`.
- ~~Default Whisper model size (`base` for now).~~ **Resolved (Phase 2):** `base`, env-overridable via `AUTOSHORTS_WHISPER_MODEL`.

## Carry-forward decisions (cross-phase)
> A running log of decisions made in one phase that constrain or pre-do work in a later
> phase. **Rule:** whenever a phase makes a choice that affects a future phase, add a row
> here *and* a short note under that future phase's section. Format: `[made in → affects]`.

- **[Phase 1 → Phase 6] Minimal UI is a starting point, not throwaway.** `index.html`,
  `app.js`, `style.css` already do upload + live `/status` polling + a results list with
  download links, using the Phase 6 palette. Phase 6 builds *on top of* these, not from scratch.
- **[Phase 1 → Phases 2–5] Pipeline stage contract is fixed.** Stages are plain functions
  with stable signatures the orchestrator calls uniformly:
  `transcriber.transcribe(video_path, work_dir) -> dict`,
  `scorer.score(transcript, video_path) -> list[dict]`,
  `selector.select(scored, top_n) -> list[dict]`,
  `renderer.render(video_path, clip, out_dir) -> Path`.
  Implementing a phase = filling the stub body; **do not change these signatures** (the
  orchestrator and later phases depend on them).
- **[Phase 2 → Phase 3] `audio.wav` (16 kHz mono) is pre-extracted in `work_dir`.** The
  transcriber leaves the extracted WAV on disk next to `transcript.json`. Module 3 should
  **reuse it for librosa RMS energy** rather than re-extracting audio from the source video.
- **[Phase 1 → Phases 2–5] Unimplemented stages raise `NotImplementedError`.** The
  orchestrator catches it and stops the job cleanly with `status="error"` + a message.
  When you implement a stage, replace the `raise` with a real return value of the
  contracted type — no orchestrator change needed.
- **[Phase 3 → Phases 4–5] Clip dicts carry word-level timestamps.** Each selected clip is
  `{start, end, text, score, words, components}`. `renderer.render` (Phase 4) only needs
  `start`/`end` to cut; the per-clip `words` list (each `{word, start, end}`, with timestamps
  in the **source video's** timeline) is preserved specifically so Phase 5 can burn word-synced
  captions without re-running transcription. **Phase 5 must offset word times by the clip
  `start`** to map them onto the cut clip's local timeline. `components` (per-signal score
  breakdown) is debug/tuning metadata — safe to ignore downstream.

- **[Phase 4 → Phase 5] The render builds a final clip, then writes it — captions slot in
  before the write.** `renderer.render` chains `subclipped → reframe_to_vertical → punch_in_zoom`
  into a 1080×1920 clip and only then calls `write_videofile`. Phase 5 should add a caption
  overlay step in this same chain *before* `write_videofile` (e.g. `CompositeVideoClip([final,
  *word_clips])`) and export the SRT alongside the MP4 in `out_dir`. **Caption word times must be
  offset by the clip `start`** (per the Phase-3 carry-forward) to map onto the cut clip's local
  timeline. Effects live in `pipeline/effects.py`; the punch-in zoom is a *constant-size* frame
  transform, so the post-zoom clip is exactly `(TARGET_WIDTH, TARGET_HEIGHT)` — caption layout can
  assume those dimensions. Output filename is `clip_<start*100, zero-padded>.mp4`; the SRT should
  share that stem.

- **[Phase 5 → Phase 6] Each clip emits a sibling `.srt` in `out_dir`, sharing the MP4 stem.**
  `renderer.render` now writes `clip_<start>.mp4` *and* `clip_<start>.srt` (clip-local timeline,
  ≤7-word cues). It's already downloadable via `/download/<job_id>/<file>`, but the orchestrator's
  `results` list only carries the MP4 name — **Phase 6 should surface the `.srt`** (download link /
  transcript view) by deriving it from the MP4 name (swap suffix) rather than changing the stage
  contract. A clip with no words still yields a valid (empty) `.srt`. Captions are burned in by
  default and toggle off via `AUTOSHORTS_CAPTIONS=0`; the bundled font lives at
  `assets/fonts/Anton-Regular.ttf` (`CONFIG.CAPTION_FONT`).

## Changelog
- **2026-06-05** — Phase 5 completed. Added `pipeline/captions.py` (caption engine + SRT) and a
  bundled OFL font (`assets/fonts/Anton-Regular.ttf`). `apply_captions` offsets each clip's
  source-timeline words to local time, burns one large accent-#7C3AED word at a time (centered lower
  third, black stroke, ease-out pop-in, word held until the next) via moviepy `TextClip` composited
  before `write_videofile`, and always writes a sibling `.srt` (`pysrt`, ≤7-word sentence-aware cues).
  Resolved the Caption A/B open decision → **Option B**. Added `config.py` caption tunables (font/size/
  colors/stroke/position/width/uppercase/pop/sync/srt-words, all env-overridable). Updated `effects.py`
  docstring + `RESEARCH.md`. No `app.py`/`orchestrator.py`/`render`-signature changes. Logged the
  `[Phase 5 → Phase 6]` carry-forward (surface the `.srt` in the UI). Verified end-to-end: 1080×1920
  h264/aac MP4 with burned captions + SRT cues; robustness for empty words (empty `.srt`) and a bad font
  path (burn skipped, MP4 + `.srt` still produced); `/health` 200.
- **2026-06-04** — Phase 4 completed. Implemented `pipeline/renderer.py` and `pipeline/effects.py`.
  `effects.reframe_to_vertical` scale-covers + crops to 1080×1920 (moviepy `resized`/`cropped`, so
  `size` stays correct), biased by an optional `focus_x_ratio`; `effects.punch_in_zoom` is a
  constant-size cv2 frame transform easing `ZOOM_START→ZOOM_END` over `ZOOM_DURATION` then holding;
  `effects.detect_focus_x_ratio` is a stretch Haar-cascade face detector (off by default) that
  samples 3 frames. `renderer.render` cuts the clip, clamps `end` to the real media duration,
  reframes, zooms, and writes an x264/aac MP4 to `shorts_output/<job_id>/clip_<start>.mp4`. Added
  `config.py` tunables (`VIDEO_CODEC`, `AUDIO_CODEC`, `RENDER_PRESET`, `RENDER_CRF`, `FACE_DETECT`).
  No `app.py`/`orchestrator.py` changes — the stage contract was already wired. Resolved the
  subject-framing open decision (center crop default + optional face detect). Logged the
  `[Phase 4 → Phase 5]` carry-forward (overlay captions before the write; SRT shares the file stem;
  offset word times by clip `start`; post-zoom clip is exactly the target dimensions). Verified a
  20s test source → 1080×1920 h264/30fps/13.5s/stereo-aac MP4, zoom ramp correct, over-duration
  clamp works, `/health` still 200.
- **2026-06-04** — Phase 3 completed. Implemented heuristic, no-LLM clip scoring + selection.
  `pipeline/scorer.py`: flattens transcript words → sentence units (split on `>PAUSE_THRESHOLD`
  gaps or sentence punctuation) → sliding-window duration-valid candidates, each scored by a
  weighted blend of hook/keyword match (English + Roman Urdu, opening-weighted), per-clip length,
  pause-clean boundaries, librosa RMS energy (reusing Phase-2 `audio.wav`, neutral 0.5 fallback),
  and a filler/repetition/outro penalty. `pipeline/selector.py`: greedy non-overlapping top-N by
  score. Added `config.py` tunables (`HOOK_KEYWORDS_EN/UR`, `FILLER_WORDS`/`FILLER_PHRASES`,
  `OUTRO_PHRASES`, `W_*` weights). No `app.py`/`orchestrator.py` changes — the stage contract was
  already wired. Logged `[Phase 3 → Phases 4–5]` carry-forward (clips carry word-level timestamps
  for caption sync; offset by clip `start`). Verified offline against `sample_transcript.json`
  (hooks rank top, filler/outro excluded, non-overlapping), empty transcript → `[]` (no crash),
  librosa energy path on a synthetic WAV (0.10 quiet vs 0.90 loud), and `/health` still 200.
- **2026-06-04** — Phase 2 completed. Implemented `pipeline/transcriber.py`: ffmpeg
  extracts a 16 kHz mono `audio.wav` into the job `work_dir`, then a cached (thread-safe)
  faster-whisper `base`/int8 model transcribes it with `word_timestamps=True` into
  `transcript.json` matching `sample_transcript.json`. Added config tunables
  `WHISPER_BEAM_SIZE`, `WHISPER_VAD_FILTER`, `AUDIO_SAMPLE_RATE`. Added no-speech robustness
  (VAD-empty → retry without VAD → valid empty transcript). Logged the
  `[Phase 2 → Phase 3]` carry-forward (reuse `audio.wav` for librosa). Verified end-to-end:
  tone clip → schema-valid empty transcript (no crash); real offline-TTS speech clip → 20
  words with monotonic word timestamps; orchestrator ran transcription, wrote
  `transcript.json`, and stopped cleanly at the Phase-3 scorer stub; `/health` still 200.
- **2026-06-04** — Added a **Carry-forward decisions (cross-phase)** section + workflow
  rule (in `CLAUDE.md`) so decisions in one phase that affect later phases are tracked.
  Logged Phase 1's carry-forwards (minimal UI → Phase 6; stage contract + clean-stop →
  Phases 2–5) and noted the existing minimal UI under Phase 6.
- **2026-06-04** — Phase 1 completed. Added `pipeline/jobs.py` (thread-safe in-memory
  job registry) and `pipeline/orchestrator.py` (background stage runner). Wired
  `/`, `/upload`, `/status/<id>`, `/results/<id>`, `/download/<id>/<file>` routes in
  `app.py`. Defined stable pipeline signatures (`transcribe/score/select/render`) as
  stubs raising `NotImplementedError`. Minimal upload UI with live status polling.
  Verified: upload validates + saves, job runs, stops cleanly at transcription; bad
  ext → 400, unknown job → 404, path traversal → 404.
- **2026-06-03** — Phase 0 completed and pushed. Environment fixed to Python 3.12.
