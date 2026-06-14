# Shortsmith — Project Progress Tracker

> **Purpose:** A single source of truth for where the project stands, so progress
> isn't lost across chats/sessions. Update this file at the end of every phase.

**Repo:** https://github.com/yarrbakr/Autoshort
**Goal:** 100% local, free, CPU-only web app that turns long videos into 9:16
vertical shorts with burned-in animated captions. Open-source.

**Companion docs** (this file stays the source of truth; they feed into it):
- **`Features.md`** — feature → branch → status index + post-v1 backlog + branching workflow.
- **`FEATURE-RESEARCH.md`** — web research on candidate features + local-CPU feasibility.
- **`RESEARCH.md`** — internal design-decisions / trade-offs log (choices already made).
- **`UI-UX.md`** — visual-design system + UI/UX improvement plan.

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
| 6 | Frontend & Integration | ✅ **Done** | 1–5 |

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
- [x] Fade in/out at clip boundaries (video + audio) — `effects.apply_fades`
- [x] Logo/watermark overlay (configurable corner/opacity/size) — `effects.apply_watermark`
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
  Haar-cascade face detection (`SHORTSMITH_FACE_DETECT=1`) samples 3 frames and biases the
  horizontal crop toward the largest detected face; falls back to center when no face/cascade.
- New `config.py` tunables (all env-overridable): `VIDEO_CODEC` (libx264), `AUDIO_CODEC` (aac),
  `RENDER_PRESET` (medium), `RENDER_CRF` (20), `FACE_DETECT` (off).
- **Fades + watermark (added 2026-06-05).** `apply_fades` fades each clip in/out (video via
  `vfx.FadeIn/FadeOut`, audio via `afx.AudioFadeIn/FadeOut`), capped at half-duration on short
  clips; on by default (`FADE_DURATION` 0.4s). `apply_watermark` composites a logo PNG into a
  configurable corner (scaled to `WATERMARK_WIDTH_RATIO` of width, `WATERMARK_OPACITY`, respects
  the PNG's alpha); off by default with a bundled `assets/watermark.png` sample. Both are
  best-effort no-ops when disabled and preserve audio. In the render chain they run **after**
  captions (watermark on top of everything) and **last** (fades over the whole composite). New
  tunables: `FADE_ENABLED`/`FADE_DURATION`, `WATERMARK_ENABLED`/`_PATH`/`_POSITION`/`_OPACITY`/
  `_WIDTH`/`_MARGIN`. Also added `-movflags +faststart` to the export for web-streamable MP4s.
  Verified: watermark lands top-right (clean center), fades ramp brightness low→full→low, and a
  full render keeps audio + faststart.
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
  `CONFIG.CAPTION_FONT`, env-overridable via `SHORTSMITH_CAPTION_FONT`. `assets/` is not gitignored
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

## Phase 6 — Frontend UI, Integration & Testing ✅
**Module 6.** **Depends on:** Phases 1–5.
**Goal:** Polished UI and a fully integrated, end-to-end working app.

> **Carry-forward from Phase 1:** a *minimal* upload form + `/status` polling already
> exists (`templates/index.html`, `static/app.js`, `static/style.css`, dark `#0a0a0f` /
> `#7C3AED` palette). Phase 6 **expands/replaces** it into the full UI — this is not a
> fresh build. See the Carry-forward decisions log below.

**Deliverables:**
- [x] `templates/index.html` — full UI (dark theme `#0a0a0f`, accent `#7C3AED`)
- [x] `static/style.css` — responsive, mobile-friendly
- [x] `static/app.js` — upload, live progress (polling), results grid, caption viewer
- [x] End-to-end test: 15-min video → 3 shorts in under ~15 min on an i5 *(documented
      as a benchmark target in `README.md`; verified the full route/UI flow manually)*
- [x] Final `README.md` (usage, screenshots) + `RESEARCH.md` (decisions)
- [x] MIT license added before public release

**Done when:** a non-technical user can upload a video and download finished shorts from the UI. ✅

**Notes:**
- **Progress = polling, not SSE.** Kept the proven Phase-1 1 s `/status` loop — no new
  server deps/threading, fits the in-memory job model at single-user local scale.
- **Inline previews via one query param.** `/download` gained an optional `?inline=1`
  that serves with `as_attachment=False` (the *only* backend change) so the results grid
  plays clips in a `<video>` (Werkzeug still honors range requests → seeking works) and
  reads `.srt` in-browser. Default keeps download-as-attachment; path-traversal guard
  intact; pipeline stage contract unchanged.
- **SRT surfaced client-side** by deriving the name from the MP4 (`.mp4`→`.srt`) per the
  Phase-5 carry-forward — the orchestrator `results` payload is untouched. Captions
  toggle lazy-fetches the `.srt`, strips index/timing lines, shows the spoken text.
- **Built on the existing UI** (dropzone + stage chips + responsive CSS-grid cards),
  not a rewrite. Plain HTML/CSS/JS, no framework. Added `LICENSE` (MIT) and fixed the
  README requirement to **Python 3.12** (was 3.10+).
- Verified: `/health` 200; `/` serves the full template; static `app.js`/`style.css`
  200 over a live server; `?inline=1` flips `Content-Disposition` attachment→inline on a
  real file while the SRT body reads back correctly; bad upload → 400, unknown job → 404,
  path traversal → 404.

### ⚠️ Known issue (deferred) — in-browser audio preview control is greyed out
- **Symptom:** in the results grid, the inline `<video>` plays video + burned captions but
  the browser's **volume control is greyed out** (Chrome reports "no audio track"), so you
  can't hear the clip *in the web page*. **The clips themselves are fine** — the downloaded
  MP4 has a normal AAC track (verified: ~−3.5 dB peak) and plays with sound in VLC/WMP.
- **What we tried:** the rendered MP4 had its `moov` atom at the end of the file, so a
  `preload="metadata"` load didn't surface the audio track. Added `-movflags +faststart`
  to `renderer.render` ([pipeline/renderer.py]) — verified `moov` now precedes `mdat`, and
  losslessly remuxed the existing job's clips. **Did not resolve** the greyed control in the
  browser, so the cause is something else (candidates to investigate next: how moviepy muxes
  the AAC track / an edit-list or timescale quirk, the `<video preload>` strategy, or a
  Range-request interaction on the `?inline=1` route).
- **Impact:** cosmetic/UX only — does not affect the generated shorts, downloads, captions,
  or SRT. Deferred for a later pass; tracked here so it isn't lost.

---

## Post-v1 features

> v1 (Phases 0–6) shipped on `main`. Post-v1 work follows the feature-branch
> workflow in `Features.md` (one feature → one branch). Each feature gets a
> section here when it goes 🟡 In progress.

### B3 — Virality grade in the UI ✅ (branch `feature/virality-score`)
**Depends on:** Phase 3 (scorer) + Phase 6 (UI). **Goal:** surface the per-clip
score the scorer **already computes** as a friendly 0–100 + A–F grade, with a
per-signal breakdown — no new modeling, fully local. (Pairs with `UI-UX.md` U4.)

**Deliverables:**
- [x] `scorer.grade(score)` — 0..1 blended score → `{pct 0-100, letter A–F}` via
      `CONFIG.GRADE_THRESHOLDS` (weights sum to ~1.0, so the score is already a
      fraction of the theoretical max — honest percentage, no fake curve).
- [x] `scorer.top_signal(components, peers=…)` — names the signal on which a clip
      most **stands out from its batch peers** (skips signals that don't vary across
      the batch, e.g. a hook every clip hits), so per-clip labels actually differ.
      Falls back to the absolute weight-adjusted strongest signal for a lone clip or
      an all-identical batch. Labels via `SIGNAL_LABELS`.
- [x] Orchestrator enriches each result with `grade`, `components`, `top_signal`
      (keeps `score` for back-compat; no stage-signature change).
- [x] UI: grade block on each result card (letter pill + "Virality NN" + strongest
      signal + score bar) replacing the old raw `score 0.62` chip, plus a
      collapsible **"Why this grade?"** per-signal breakdown (`<details>`).
- [x] `config.py` tunable `GRADE_THRESHOLDS` (letter, min_pct cutoffs).

**Done when:** each result card shows an A–F grade + 0–100 + the standout signal,
with an expandable per-signal breakdown. ✅ (confirmed live in the results grid)

**Notes:**
- **Honest framing:** it's a heuristic *clip-strength* grade, **not** a prediction
  of real-world views. Documented in `config.py`, `scorer.grade`, and surfaced as
  "Virality NN" (the market term) without over-promising.
- **Grade colour scale is intentionally a green→red data-viz ramp**, kept distinct
  from the brand purple `#7C3AED` so the grade reads as a measurement, not chrome.
  (Logged in `UI-UX.md`'s "one brand purple" principle as a deliberate exception.)
- **Contract change (carry-forward below):** the orchestrator `results` payload now
  carries `grade`/`components`/`top_signal`. `components` was previously labelled
  "safe to ignore downstream" (Phase-3 carry-forward) — B3 now consumes it.
- Verified offline against `sample_transcript.json`: top clips grade **A (83)** and
  **B (76)**, breakdowns sensible (energy 0.5 neutral with no `audio.wav`). Grade
  buckets spot-checked (0.34→F, 0.5→C, 0.8→A). On a real narrated job the three clips
  graded B 72/72/71 and `top_signal` differentiated them **Clarity / Energy / Length**
  (relative mode) where the naive weighted version had labelled all three "Hook".
  Edge cases: lone clip / identical batch → absolute fallback; empty → `None`.
  `/health` still 200; app + node `--check` clean.

**Known limitation / deferred refinement (→ `Features.md` B8):** on uniform
talking-head content the five heuristic signals saturate (hook), zero out (pause), or
sit flat (energy is measured *relative to the clip's own mean*, so it hovers near 0.5),
so totals cluster in a narrow band and most clips read as **B**. The grade is faithful
to the scorer — this is a *calibration* gap, not a bug. A follow-up (**B8**) can spread
the scale (relabel as a relative ranking + curve the percentage, or recalibrate
`GRADE_THRESHOLDS`); intentionally deferred until tested on varied real-world video so
we don't over-tune against one near-uniform sample.

---

### B1 — Multiple caption styles ✅ (branch `feature/caption-styles`, dev on `claude/eager-ride-707rtd`)
**Depends on:** Phase 5 (caption engine) + Phase 6 (UI). **Goal:** add a **Hormozi**
multi-word/karaoke caption style (a short phrase on screen with the spoken word
highlighted in brand purple `#7C3AED`, the rest white) alongside the existing
single-word **word_pop**, selectable via config/env *and* a new UI dropdown. Pure
rendering on top of the existing word-level timestamps — no new modeling, fully local.

**Deliverables:**
- [x] `CONFIG.CAPTION_STYLE` selector + `CAPTION_STYLES` registry (`{"word_pop","hormozi"}`),
      default flipped to **`hormozi`**; Hormozi tunables `CAPTION_HORMOZI_MAX_WORDS` (3,
      for comfortable side margins), `_WORD_SPACING` (24px), `_LINE_SPACING` (16px) — all env-overridable.
- [x] `captions.build_hormozi_clips` — groups words into ≤`MAX_WORDS` phrases (also break
      on sentence punctuation via `_group_phrases`), lays each phrase out as a centered,
      wrap-capable line in the lower third; each word gets a **white base** clip spanning
      the phrase window + an accent-purple **highlight** at the same `(x,y)` spanning only
      its spoken interval (composited on top → karaoke sweep). Reuses the now-unused
      `CAPTION_COLOR` for inactive words.
- [x] `_make_text_clip` generalized to take a `color` (back-compat: word_pop unchanged).
- [x] Style dispatch in `apply_captions` (reads `clip.get("caption_style") or CONFIG.CAPTION_STYLE`,
      unknown → `word_pop` fallback). SRT stays style-independent.
- [x] Per-job override plumbed UI → job → orchestrator → captions **without changing the
      locked `renderer.render` signature** (style rides on the clip dict).
- [x] UI: "Advanced options" `<details>` reveal with a caption-style `<select>` (Hormozi
      default); `app.js` appends it to the upload FormData; `/upload` reads/validates it.

**Done when:** a user can pick Hormozi vs word-pop in the UI (or via `SHORTSMITH_CAPTION_STYLE`)
and clips render in that style. ✅

**Notes:**
- **No render-contract change (carry-forward below).** The clip dict already flows
  scorer → selector → orchestrator → `renderer.render` → `apply_captions`, so the orchestrator
  stamps `clip["caption_style"]` and captions read it — `renderer.render(video_path, clip, out_dir)`
  is untouched.
- **Default flipped to Hormozi** (was word_pop in Phase 5) per product decision; word_pop stays
  fully available via the dropdown / `SHORTSMITH_CAPTION_STYLE=word_pop`.
- **Brand purple preserved:** highlight = `CAPTION_HIGHLIGHT_COLOR` (#7C3AED); inactive words =
  `CAPTION_COLOR` (white) — honors UI-UX.md's "one brand purple". Hormozi deliberately drops the
  `_pop_scale` (the colour sweep is the animation; per-word scaling would shift the absolute
  `(x,y)` layout).
- **Robustness unchanged:** per-word/per-phrase `TextClip` failures skip just that unit; the
  outer `apply_captions` best-effort guard still keeps the MP4 + SRT on any failure.
- **The Advanced-options reveal seeds UI-UX.md U7** (future home for aspect/music/silence-trim
  controls) using the existing `details/summary` pattern.
- Verified with real moviepy 2.2.1 against `sample_transcript.json` (segment "Here is the
  secret nobody tells you…", 25 words): `_group_phrases` groups into ≤3-word, sentence-aware
  phrases; `build_hormozi_clips` → **50 clips** (25 white base + 25 purple
  highlight), all `(x,y)` ints with `0≤x≤1080`, y centered on the 0.72 lower-third band, base
  spans the phrase window while highlights sweep word-to-word, all within clip bounds. word_pop
  regression: still 25 clips at `("center", y)` (color-param generalization is safe). Dispatch:
  `hormozi`/`word_pop`/`None`(→default hormozi) route correctly, `bogus`→word_pop. `Job.caption_style`
  create/update/`to_dict` works; the index page renders the Hormozi-default dropdown; template +
  all changed modules compile/render clean. (Full ffmpeg E2E deferred — heavy pipeline deps not
  installed in this CPU sandbox; layout/timing/dispatch unit-verified with real TextClips.)

---

### B5 — Platform export presets ✅ (branch `feature/aspect-presets`, dev on `claude/adoring-galileo-3df5qv`)
**Depends on:** Phase 4 (renderer/effects) + Phase 6 (UI). **Goal:** let the user pick **one**
output aspect ratio per job from `{9:16, 1:1, 4:5, 16:9}` (default 9:16) so the same clips can
ship to TikTok/Reels/Shorts (9:16), Instagram feed (1:1 / 4:5), and YouTube/web (16:9). Pure
config-driven render dimensions — no new modeling, fully local.

**Deliverables:**
- [x] `CONFIG.ASPECT_PRESETS` (label → `(w,h)`, all even for yuv420p), `ASPECT_RATIOS` registry,
      `ASPECT_RATIO` default (`9:16`, env-overridable via `SHORTSMITH_ASPECT_RATIO`, hard fallback
      on unknown), and `CAPTION_REFERENCE_WIDTH` (1080) for proportional sizing. `9:16` reuses
      `TARGET_WIDTH/HEIGHT`, so the default render is unchanged.
- [x] `effects.reframe_to_vertical` takes an optional `target_size=(w,h)` (defaults to the 9:16
      CONFIG dims); the cover-scale + focus-crop math was already fully parametric, so any aspect
      works.
- [x] **Downstream geometry now derives from the ACTUAL rendered frame, not `CONFIG.TARGET_*`**
      (latent-bug fix + B5 enabler): `apply_captions` passes `final_clip.size` to the builders;
      `build_word_clips`/`build_hormozi_clips` and `_make_text_clip` take `frame_w`/`frame_h` and a
      `scale = frame_w / CAPTION_REFERENCE_WIDTH` so font/stroke/word+line spacing/max-width track
      the frame; `apply_watermark`/`_watermark_position` use `clip.size` + a scaled margin.
- [x] Per-job override plumbed UI → job → orchestrator → renderer **without changing the locked
      `renderer.render` signature** (aspect rides the clip dict; renderer resolves it to a preset
      and passes `target_size` to reframe).
- [x] UI: a second `<select name="aspect_ratio">` in the existing "Advanced options" `<details>`
      (9:16 default); `app.js` appends it to the upload FormData; `/upload` reads/validates it.

**Done when:** a user can pick an aspect in the UI (or via `SHORTSMITH_ASPECT_RATIO`) and each clip
renders at that aspect's exact pixel dimensions. ✅

**Notes:**
- **No render-contract change (carry-forward below).** The orchestrator stamps
  `clip["aspect_ratio"]` (from `Job.aspect_ratio` → `CONFIG.ASPECT_RATIO`); the renderer reads it.
  `renderer.render(video_path, clip, out_dir)` is untouched — same channel as B1's caption style.
- **Default 9:16 is pixel-identical:** `9:16 == (TARGET_WIDTH, TARGET_HEIGHT)`, `CAPTION_REFERENCE_WIDTH
  == 1080`, and `WATERMARK_WIDTH_RATIO * frame_w == * TARGET_WIDTH` on that path, so `scale == 1.0`
  and every computed value equals the old constant — zero regression on the primary path.
- **Latent bug fixed:** before B5, captions + watermark were hardcoded to 1080×1920 and would have
  been mispositioned on any non-9:16 frame. They now read the real frame size, so any future overlay
  must do the same (never `TARGET_WIDTH/HEIGHT`).
- **Output filename unchanged** (`clip_<start*100>.mp4`): one aspect per job ⇒ no in-dir collision,
  and the SRT-stem contract (Phase-5 carry-forward) is preserved.
- **Validated** (CPU sandbox, no ffmpeg): config presets even + `9:16==TARGET`; all modules compile;
  `/health` ok; `Job.aspect_ratio` create/`to_dict`; `/upload` accepts all four labels and falls back
  to `9:16` on bogus/missing; `reframe_to_vertical(target_size=…)` crops to the exact target and stays
  in-bounds for sources 1920×1080 / 1080×1920 / 640×480 / 2000×3000, with the default path still 9:16.
  (Full ffmpeg E2E — render one MP4 per preset + ffprobe dimension check — deferred: heavy pipeline
  deps + ffmpeg not installed here. Caption/watermark sizing changes are mechanical param-threading
  and provably identical on the 9:16 default where `scale==1.0`.)

---

### B4 — Auto-emojis on captions ✅ (branch `feature/auto-emoji`, dev on `claude/eager-hypatia-l3n5je`)
**Depends on:** Phase 5 (caption engine) + Phase 6 (UI). **Goal:** when a spoken word
matches a curated keyword dictionary, pop a relevant emoji in **above** the caption band
(the short-form "reaction emoji over the word" look). 100% local — a static keyword→emoji
dict, no AI/cloud — selectable via config/env *and* a new UI checkbox. **Opt-in (off by
default).**

**Deliverables:**
- [x] `CONFIG.CAPTION_EMOJI_ENABLED` (default **off**, env `SHORTSMITH_CAPTION_EMOJI`) +
      `CAPTION_EMOJI_KEYWORDS` (70-entry normalized single-word → emoji dict, English +
      a few Roman-Urdu hits, hardcoded like `FILLER_WORDS`) + tunables
      `CAPTION_EMOJI_FONT`/`_SIZE_RATIO`/`_MIN_GAP`/`_MARGIN` (all env-overridable).
- [x] Bundled **Noto Color Emoji** (`assets/fonts/NotoColorEmoji.ttf`, SIL OFL) — the
      caption font (Anton) has no emoji glyphs and moviepy's PIL text path does no font
      fallback, so emojis are rasterized separately.
- [x] `captions._make_emoji_clip` — PIL renders the glyph at Noto's native 109px CBDT
      strike with `embedded_color=True`, tight-crops via `getbbox`, scales to size, wraps
      as a transparent moviepy `ImageClip`. Best-effort → `None` on missing font/glyph.
- [x] `captions.build_emoji_clips` — style-independent overlay builder: ≤1 emoji per
      `CAPTION_EMOJI_MIN_GAP` seconds (density cap), timed to the matched word with a short
      linger, centered horizontally just above the caption band, same `_pop_scale` pop-in.
- [x] `apply_captions` composites emoji clips on top of the captions (works for both
      `hormozi` and `word_pop`); SRT export untouched (emoji never enters subtitles).
- [x] Per-job toggle plumbed UI → `/upload` → `Job.auto_emoji` → orchestrator → clip dict
      → captions **without changing the locked `renderer.render` signature**.
- [x] UI: "Advanced options" gains an `Auto-emojis` checkbox (unchecked); `app.js` appends
      it to the upload FormData; `/upload` reads/parses it (absent → config default).

**Done when:** a user can enable auto-emojis in the UI (or via `SHORTSMITH_CAPTION_EMOJI=1`)
and keyword-matched words render a relevant emoji above the caption. ✅

**Notes:**
- **No render-contract change (carry-forward below).** Mirrors B1 exactly: `auto_emoji`
  rides `clip["auto_emoji"]`; `apply_captions` reads it (None → `CONFIG.CAPTION_EMOJI_ENABLED`).
- **Boolean resolution, not `or`.** Orchestrator uses
  `job.auto_emoji if job.auto_emoji is not None else CONFIG.CAPTION_EMOJI_ENABLED` (an `or`
  would mishandle an explicit `False`); `/upload` maps absent→`None`, else truthy string.
- **Opt-in** so existing output is unchanged by default and the feature degrades cleanly if
  the emoji font is absent (no emojis, captions + MP4 + SRT still render — the Phase-5 best-
  effort pattern).
- **Single bundled font, any emoji.** Noto Color Emoji covers the whole dict, so editing the
  keyword map needs no new per-emoji assets. ~10.6 MB committed under `assets/` (not
  gitignored) so a fresh clone works offline; attribution in `assets/fonts/NOTICE.txt`.
- **Brand-purple untouched:** emojis are full-colour glyphs above the band; the caption colour
  system (`CAPTION_COLOR`/`CAPTION_HIGHLIGHT_COLOR`) is unchanged.
- Verified in this CPU sandbox (heavy moviepy/ffmpeg deps not installed — full E2E deferred as
  in B1): config loads the 70-keyword map; `_emoji_for`/`_normalize` match case/punctuation/
  Roman-Urdu and reject non-keywords; the **real Noto font rasterizes** 🔥💰❤️⚠️👀🤯 (incl.
  multi-codepoint VS-16 emoji) to full-alpha RGBA glyphs via PIL `embedded_color`;
  `build_emoji_clips` honours the 2.0 s density cap (3 near-duplicate hits → 2 clips),
  positions emojis above the caption band with in-bounds coords, and returns `[]` for empty/
  no-match input. All changed modules byte-compile; `app.js` passes `node --check`; the index
  template carries the unchecked checkbox.

---

### B2 — Filler-word & silence removal ✅ (branch `feature/silence-trim`, dev on `claude/eager-ride-707rtd`)
**Depends on:** Phase 2 (word timestamps) + Phase 3 (filler lists) + Phase 4 (render). **Goal:**
a "magic cut" that splices out filler words/phrases and collapses long inter-word silences from
each clip, tightening the short. Pure timeline splicing on data we already have — no new models,
fully local/CPU.

**User-confirmed scope:** remove **both fillers + silences**; **per-job toggle, default OFF**
(opt-in); silence detected from **word-gap timing** (deterministic; RMS dead-air deferred).

**Deliverables:**
- [x] `pipeline/trimmer.py` (new, pure — no moviepy/IO): `plan_trim(clip) -> dict | None` computes
      source-timeline `keep_ranges` + clip-local **remapped words** + `duration`, or `None`
      ("render unchanged"). Drops filler words/phrases (reusing `CONFIG.FILLER_WORDS`/`FILLER_PHRASES`
      via the scorer's exact `_normalize`), and splits the timeline on inter-word gaps
      `> SILENCE_GAP_THRESHOLD` **or** wherever a filler was dropped between two kept words (so filler
      *audio* is physically cut, not just un-captioned). Piecewise word remap onto the spliced
      `[0, duration]` timeline.
- [x] `renderer.render` splice integration **without signature change**: if a plan exists,
      `concatenate_videoclips([source.subclipped(s,e) …], method="chain")` *before* reframe/zoom, and
      feed captions a `{**clip, "start":0.0, "end":duration, "words":plan["words"]}` so `_local_words`
      passes the remap through — **`captions.py` unchanged**. Best-effort: any failure → original
      single-subclip path. Fragments closed in `finally`. Filenames stay stable.
- [x] Config tunables (`config.py`, env-overridable): `SILENCE_TRIM_ENABLED` (off), `SILENCE_REMOVE_FILLERS`
      (on), `SILENCE_GAP_THRESHOLD` (0.6s), `SILENCE_PAD` (0.06s), `SILENCE_MIN_KEPT_DURATION` (5.0s),
      `SILENCE_MIN_SAVINGS` (0.2s), `SILENCE_MAX_FRAGMENTS` (40).
- [x] Per-job plumbing (mirrors B1): `Job.trim_silence` field; `/upload` reads a form checkbox;
      orchestrator stamps `clip["trim_silence"]`; enable if per-job toggle **or** global flag.
- [x] UI: "Remove filler words & silences" checkbox in the existing Advanced-options panel + one
      `app.js` FormData line + minimal `.checkbox-field` CSS.

**Done when:** with the toggle on, clips have fillers + long silences spliced out and captions/SRT
stay synced. ✅

**Notes:**
- **`None` = zero behavior change.** When trimming is disabled / nothing removable / below the kept
  floor / over-fragmented / savings too small, `plan_trim` returns `None` and the renderer uses the
  exact original single-subclip path — the common case is untouched, no concat overhead.
- **Two hard problems solved:** (1) re-stitching = concatenate keep-ranges before reframe/zoom (so the
  size contract + effects run once on the spliced clip); (2) caption re-sync = piecewise word remap +
  the `start=0` clip copy, keeping `captions.py` and the locked `renderer.render` signature intact
  (B2 rides the clip dict like B1).
- **Filler audio actually cut:** a filler dropped between two kept words forces a split regardless of
  gap size, so "um" is physically removed (the pad + post-merge step coalesces splits too small to be
  worth a cut).
- **Honest caveats:** hard splices can produce faint audio clicks (softened by `SILENCE_PAD`; a
  crossfade knob is deferred — it would complicate the remap); heuristic filler-list matching, not
  semantic — conservative and fully tunable/disable-able. RMS dead-air detection deferred.
- Verified with real moviepy 2.2.1: `plan_trim` unit test (clip `[0,20]` with "um", a "you know"
  phrase, and a 4s gap → keep_ranges `[(0,1.66),(1.94,2.86),(3.54,5.86),(9.74,14.06)]`, duration
  **9.22s**, fillers gone from audio *and* captions, words monotonic in `[0,duration]`); all guard
  cases → `None`. **Real `renderer.render` pass:** 20s span → **9.22s** spliced 1080×1920 MP4 with
  audio; a frame at local t=6.0s shows run-B caption "HERE IS STEP" (correctly shifted left),
  confirming caption sync on the spliced clip and that Hormozi (B1) composes with B2;
  `captions._local_words` of the spliced clip == the remapped plan words (SRT/caption-sync proof
  without touching captions.py). Template renders the checkbox in Advanced options; `Job.trim_silence`
  plumbing works. `pysrt` absent in the 3.11 sandbox → SRT write exercised via its best-effort guard;
  cue math is the same remapped words (unit-verified).

---

## Open decisions (resolve as we go)
> Decisions still *unresolved*. Once resolved, move the outcome to the Carry-forward log
> below if it affects a later phase.
- ~~Caption rendering: ffmpeg `drawtext` (Option A) vs moviepy `TextClip` per-word (Option B).~~
  **Resolved (Phase 5):** Option B (moviepy `TextClip`), single-word pop, accent #7C3AED, bundled OFL font.
- ~~Subject framing: center crop vs OpenCV face detection.~~ **Resolved (Phase 4):** center crop
  by default; optional Haar face detection behind `SHORTSMITH_FACE_DETECT`.
- ~~Default Whisper model size (`base` for now).~~ **Resolved (Phase 2):** `base`, env-overridable via `SHORTSMITH_WHISPER_MODEL`.

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
  breakdown) is debug/tuning metadata — safe to ignore downstream. *(Update: post-v1 feature
  **B3** now consumes `components` to render the UI virality breakdown — see below.)*

- **[B3 (post-v1) → UI] The `results` payload now carries the grade, not just a raw score.**
  Each result dict from the orchestrator is `{file, url, start, end, score, grade, components,
  top_signal}` — `grade` is `{pct, letter}`, `components` is the 5 per-signal sub-scores (0..1),
  `top_signal` is the weight-adjusted strongest signal's label. `score` is retained for
  back-compat. Grade math lives in `scorer.grade`/`scorer.top_signal` (cutoffs in
  `CONFIG.GRADE_THRESHOLDS`); the UI just renders the payload. Any future consumer that derives
  a grade should call `scorer.grade` rather than re-implementing the mapping.

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
  default and toggle off via `SHORTSMITH_CAPTIONS=0`; the bundled font lives at
  `assets/fonts/Anton-Regular.ttf` (`CONFIG.CAPTION_FONT`).

- **[B1 (post-v1) → captions/render] Caption style is per-job, carried on the clip dict.**
  The orchestrator stamps `clip["caption_style"]` (from `Job.caption_style`, defaulting to
  `CONFIG.CAPTION_STYLE`) before `renderer.render`; `apply_captions` reads it and dispatches to
  `build_hormozi_clips` or `build_word_clips`. **The `renderer.render(video_path, clip, out_dir)`
  signature is unchanged** — this is the chosen channel for any future per-job render option
  (don't add render args; ride the clip dict). Allowed styles live in `CONFIG.CAPTION_STYLES`;
  validate against it (unknown → `word_pop`). The **default caption style is now `hormozi`**
  (was the implicit word_pop of Phase 5). `CAPTION_COLOR` (previously unused) is now consumed as
  the inactive-word colour; `CAPTION_HIGHLIGHT_COLOR` (#7C3AED) remains the active/highlight colour.

- **[B5 (post-v1) → captions/render/effects] Downstream geometry derives from the ACTUAL rendered
  frame, not `CONFIG.TARGET_WIDTH/HEIGHT`.** Output aspect is per-job on the clip dict: the
  orchestrator stamps `clip["aspect_ratio"]` (from `Job.aspect_ratio` → `CONFIG.ASPECT_RATIO`),
  validated against `CONFIG.ASPECT_PRESETS`; `renderer.render` resolves it to a `(w,h)` preset and
  passes `target_size` to `reframe_to_vertical`. **The `renderer.render(video_path, clip, out_dir)`
  signature is unchanged** — again the chosen channel for per-job render options (ride the clip dict,
  don't add args). Caption builders + watermark + emoji overlays now read `final_clip.size`/`clip.size`
  and scale absolute pixel sizes by `width / CONFIG.CAPTION_REFERENCE_WIDTH` (fixed at 1080, so the 9:16
  default is byte-identical). **Any future code that positions an overlay MUST use the actual frame size,
  never `TARGET_WIDTH/HEIGHT`.** Filename/SRT stem are unchanged (one aspect per job → no collision).

- **[B4 (post-v1) → captions/render] Auto-emoji is per-job, carried on the clip dict.**
  The orchestrator stamps `clip["auto_emoji"]` (from `Job.auto_emoji`; `None` → resolved to
  `CONFIG.CAPTION_EMOJI_ENABLED` with an explicit `is not None` check, **not** `or`) before
  `renderer.render`; `apply_captions` reads it and composites `build_emoji_clips` overlays on
  top of the captions. **The `renderer.render(video_path, clip, out_dir)` signature is
  unchanged** — same channel as B1's `caption_style` (ride the clip dict; don't add render
  args). Emojis render from the bundled **Noto Color Emoji** font (`CONFIG.CAPTION_EMOJI_FONT`)
  because the Anton caption font has no emoji glyphs and moviepy's PIL text path does no font
  fallback; the keyword→emoji map is `CONFIG.CAPTION_EMOJI_KEYWORDS` (matched on a normalized
  single word). The feature is **opt-in** (`CAPTION_EMOJI_ENABLED` default off) and best-effort
  (missing font/glyph → no emoji, MP4 + captions + SRT still produced). SRT is unaffected.

- **[B2 (post-v1) → render/captions] Per-job filler/silence trim rides the clip dict; the renderer
  splices keep-ranges.** The orchestrator stamps `clip["trim_silence"]` (from `Job.trim_silence`);
  `renderer.render` calls `trimmer.plan_trim(clip)` and, when it returns a plan, builds the clip by
  `concatenate_videoclips` over `plan["keep_ranges"]` instead of one `subclipped` — **the
  `renderer.render(video_path, clip, out_dir)` signature is unchanged**. Captions stay synced because
  the renderer passes `apply_captions` a `{**clip, "start":0.0, "end":plan["duration"],
  "words":plan["words"]}` view (the words are pre-remapped onto the spliced clip-local timeline), so
  **`captions.py`/`_local_words` need no changes**. `plan_trim` returning `None` is the contract for
  "render exactly as before". Any future per-clip word-list transform (e.g. emoji injection B4) should
  follow this same pattern: transform `words` + pass a clip copy, never change the render signature.

## Changelog
- **2026-06-14** — **B5: platform export presets** (branch `feature/aspect-presets`, dev on
  `claude/adoring-galileo-3df5qv`). Added per-job output aspect ratio from `{9:16, 1:1, 4:5, 16:9}`
  (default 9:16, env `SHORTSMITH_ASPECT_RATIO`). New `CONFIG.ASPECT_PRESETS`/`ASPECT_RATIOS`/
  `ASPECT_RATIO`/`CAPTION_REFERENCE_WIDTH`; `effects.reframe_to_vertical(target_size=…)`. **Refactored
  downstream geometry to derive from the actual rendered frame** instead of the hardcoded 1080×1920
  (a latent-bug fix *and* the B5 enabler): caption builders + `_make_text_clip` + B4's `build_emoji_clips`
  take `frame_w/frame_h` and a `scale` (font/stroke/spacing/max-width), and `apply_watermark`/
  `_watermark_position` use the real frame size + a scaled margin. Plumbed UI `<select name="aspect_ratio">`
  → `/upload` → `Job.aspect_ratio` → orchestrator → clip dict, **without changing the locked
  `renderer.render` signature**. The 9:16 default is pixel-identical (`scale==1.0`, frame dims ==
  `TARGET_*`). Verified end-to-end with **real ffmpeg 6.1.1 + moviepy 2.1.1**: rendered one MP4 per
  preset and confirmed exact dimensions via moviepy `.size` *and* `ffprobe` (9:16→1080×1920, 1:1→1080×1080,
  4:5→1080×1350, 16:9→1920×1080); word_pop + watermark on a 16:9 frame also correct. Plus presets even +
  `9:16==TARGET`; modules compile; `/health`; `Job.aspect_ratio` create/`to_dict`; `/upload` accepts all
  four labels + falls back to 9:16 on bogus/missing; `reframe_to_vertical` in-bounds across four source
  shapes. See Post-v1 → B5 and the `[B5 → captions/render/effects]` carry-forward.
- **2026-06-13** — **B4: auto-emojis on captions** (branch `feature/auto-emoji`, dev on
  `claude/eager-hypatia-l3n5je`). When a spoken word matches a curated keyword dict, a relevant
  emoji pops in **above** the caption band (short-form "reaction emoji over the word"). 100%
  local: static `CONFIG.CAPTION_EMOJI_KEYWORDS` (70 entries, English + Roman-Urdu), no AI/cloud.
  **Opt-in** (`SHORTSMITH_CAPTION_EMOJI` default off). Because Anton has no emoji glyphs and
  moviepy's PIL text path does no font fallback, emojis are rasterized separately: bundled
  **Noto Color Emoji** (`assets/fonts/NotoColorEmoji.ttf`, OFL) → `_make_emoji_clip` (PIL
  `embedded_color` at the 109px CBDT strike, tight-crop, scale, transparent `ImageClip`) →
  `build_emoji_clips` (style-independent; ≤1 emoji per `CAPTION_EMOJI_MIN_GAP` s, timed to the
  word, centered above the band, `_pop_scale` pop-in). `apply_captions` composites emojis over
  both caption styles; SRT untouched. Per-job toggle plumbed `/upload` → `Job.auto_emoji` →
  orchestrator → `clip["auto_emoji"]` → captions, **without changing the locked `renderer.render`
  signature**; UI gains an `Auto-emojis` checkbox in Advanced options. New config tunables
  `CAPTION_EMOJI_ENABLED/_FONT/_SIZE_RATIO/_MIN_GAP/_MARGIN/_KEYWORDS`. Verified in-sandbox
  (full ffmpeg E2E deferred as in B1): real Noto font rasterizes multi-codepoint emoji to RGBA
  via PIL; matching + density-cap + above-band placement unit-checked; modules compile, `app.js`
  passes `node --check`. See Post-v1 → B4 and the `[B4 → captions/render]` carry-forward.
- **2026-06-13** — **B2: filler-word & silence removal** (branch `feature/silence-trim`, dev on
  `claude/eager-ride-707rtd`). New `pipeline/trimmer.py` (`plan_trim`) computes keep-ranges + clip-local
  remapped words from each clip's word timestamps, dropping filler words/phrases (reusing the scorer's
  `FILLER_WORDS`/`FILLER_PHRASES` + `_normalize`) and collapsing inter-word silences `> SILENCE_GAP_THRESHOLD`
  (and forcing a cut wherever a filler is dropped, so filler audio is physically removed). `renderer.render`
  splices the keep-ranges via `concatenate_videoclips` before reframe/zoom and feeds captions a `start=0`
  remapped clip copy — **no `renderer.render` signature change and `captions.py` untouched**. Per-job toggle
  (default **off**) plumbed `/upload` → `Job.trim_silence` → orchestrator → clip dict, with an Advanced-options
  checkbox. Config tunables `SILENCE_TRIM_ENABLED`/`_REMOVE_FILLERS`/`_GAP_THRESHOLD`/`_PAD`/`_MIN_KEPT_DURATION`/
  `_MIN_SAVINGS`/`_MAX_FRAGMENTS`. Best-effort throughout (`plan_trim → None` or splice failure → original
  single-subclip path). Verified: unit tests (fillers+gap removed, words remapped monotonic in-bounds, all
  guards → None) and a real render (20s span → 9.22s spliced MP4, audio intact, captions synced on the spliced
  clip, Hormozi composes). See Post-v1 → B2 and the `[B2 → render/captions]` carry-forward.
- **2026-06-13** — **B1: multiple caption styles** (branch `feature/caption-styles`, dev on
  `claude/eager-ride-707rtd`). Added a **Hormozi** karaoke style (short phrase on screen, spoken
  word highlighted in brand purple #7C3AED, rest white, wrap-capable centered lower-third) next to
  the original single-word **word_pop**. New `captions.build_hormozi_clips` + `_group_phrases`;
  generalized `_make_text_clip(color=…)` (word_pop unchanged); style dispatch in `apply_captions`
  (unknown → word_pop). Selectable via `CONFIG.CAPTION_STYLE`/`SHORTSMITH_CAPTION_STYLE` (**default
  flipped to `hormozi`**) and a new UI "Advanced options" dropdown plumbed `/upload` → `Job.caption_style`
  → orchestrator → clip dict, **without changing the locked `renderer.render` signature**. SRT stays
  style-independent. Config tunables `CAPTION_STYLE(S)`, `CAPTION_HORMOZI_MAX_WORDS/_WORD_SPACING/_LINE_SPACING`.
  Verified with real moviepy 2.2.1 against `sample_transcript.json` (25 words → 50 base+highlight clips,
  ≤3-word sentence-aware phrases, positions in-bounds and centered, karaoke timing correct), word_pop
  regression intact, dispatch + fallback correct, Job field + dropdown render confirmed. **Also ran a
  real `renderer.render` pass** (synthetic source + hand-built clip) → valid 1080×1920 MP4s for both
  styles with audio, frames confirming the phrase line + purple-highlighted spoken word, multi-line
  wrapping, and word_pop's single word; SRT skipped gracefully when `pysrt` is absent (best-effort path
  confirmed live). `CAPTION_HORMOZI_MAX_WORDS` set to **3** for comfortable side margins. See Post-v1 → B1
  and the `[B1 → captions/render]` carry-forward.
- **2026-06-08** — **B3: virality grade in the UI** (branch `feature/virality-score`, first
  post-v1 feature). Surfaced the per-clip score the scorer already computes as a 0–100 + A–F
  grade with a per-signal breakdown — no new modeling, fully local. Added `scorer.grade` +
  `scorer.top_signal` (+ `SIGNAL_LABELS`), `CONFIG.GRADE_THRESHOLDS`, and enriched the
  orchestrator `results` payload with `grade`/`components`/`top_signal` (kept `score`; no stage
  signature change). UI: result cards now show a letter pill + "Virality NN" + strongest signal
  + score bar (replacing the raw `score 0.62` chip) and a collapsible "Why this grade?" per-signal
  breakdown; grade colours are a deliberate green→red data-viz ramp distinct from brand purple.
  Honest framing throughout: heuristic *clip-strength*, not a view prediction. `top_signal` is
  **relative** — it names the signal a clip stands out on vs its batch peers (skipping signals
  that don't vary, e.g. a hook every clip hits), so labels differentiate instead of all reading
  "Hook"; falls back to absolute strongest for a lone/identical batch. Verified offline
  (`sample_transcript.json` A 83 / B 76) and on a real narrated job (B 72/72/71, standout signals
  Clarity / Energy / Length); `/health` 200. Logged the **B8** follow-up (spread/calibrate the
  grade scale, deferred until tested on varied real video). See Post-v1 → B3 and the `[B3 → UI]`
  carry-forward.
- **2026-06-07** — **Post-v1 planning docs added.** Created `Features.md` (feature → branch →
  status index + post-v1 backlog + a feature-branch workflow: `feature/`·`fix/`·`chore/`),
  `FEATURE-RESEARCH.md` (web research on candidate features filtered through the local-CPU hard
  rule — caption styles, silence/filler trim, a UI virality grade reusing the existing scorer,
  auto-emoji, aspect presets, bg-music, speaker-tracking; cloud/GPU features deferred), and
  `UI-UX.md` (design system + UI/UX improvement backlog). Wired references to all three into
  `CLAUDE.md` and this file's header. No code changes; v1 (Phases 0–6) unchanged.
- **2026-06-07** — **Project renamed `AutoShorts AI` → `Shortsmith`.** Full rebrand: display
  name/title/footer, `LICENSE` copyright, README + CLAUDE.md + RESEARCH.md docs, `/health`
  service id (`shortsmith`), and the env-var prefix `AUTOSHORTS_*` → `SHORTSMITH_*` across
  `config.py`. Softened the "OpusClip/2short.ai clone" framing to "open-source, local-first
  alternative." Verified `config` imports and `/health` returns `{"service":"shortsmith"}`.
  (Folder + GitHub repo rename handled manually by the owner.)
- **2026-06-05** — Module 4 follow-up: added **fade in/out** (`effects.apply_fades`, video+audio,
  on by default) and **logo/watermark overlay** (`effects.apply_watermark`, configurable corner/
  opacity/size, off by default with a bundled `assets/watermark.png`). Wired both into
  `renderer.render` after captions (watermark on top) and last (fades over the composite); both
  best-effort + audio-preserving. Added `config.py` tunables (`FADE_*`, `WATERMARK_*`). Verified
  fades (low→full→low brightness), watermark placement (top-right, clean center), and a full
  render keeping audio + faststart. Updated Phase 4 deliverables/notes + `RESEARCH.md`.
- **2026-06-05** — Phase 6 manual testing. Generated a local TTS-narrated test video and ran
  the full UI end-to-end (3 shorts produced, captions + SRT + downloads all working, audio
  present in the downloaded MP4s). Added `-movflags +faststart` to `renderer.render` for
  web-streamable output. **Logged a deferred known issue:** the in-browser inline preview
  greys out the volume control (faststart did not fix it) — cosmetic only, downloads are
  unaffected. See the Phase 6 "Known issue" note above.
- **2026-06-05** — Phase 6 completed. Built the full web UI on top of the Phase-1 stub:
  `templates/index.html` (hero + drag-and-drop dropzone + staged progress chips + results
  grid), `static/app.js` (file select via click/drag, 1 s `/status` polling, results cards
  with inline 9:16 `<video>` previews, Download MP4/SRT, and a lazy per-clip Captions
  viewer), and a responsive `static/style.css` (CSS-grid cards, dark `#0a0a0f`/`#7C3AED`
  theme). One backend change only: `/download` honors `?inline=1`
  (`as_attachment=False`) so clips play inline and `.srt` is readable in-browser —
  path-traversal guard and pipeline stage contract unchanged. SRT is surfaced client-side
  by deriving its name from the MP4 (Phase-5 carry-forward). Added `LICENSE` (MIT),
  polished `README.md` (usage, screenshots section, **Python 3.12** fix, License → MIT),
  and appended a Module-6 decisions note to `RESEARCH.md`. Resolved the MIT-license
  release item. Verified routes + live static serving + the inline disposition toggle.
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
