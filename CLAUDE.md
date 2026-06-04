# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AutoShorts AI — a 100% local, free, CPU-only web app that turns long videos into
9:16 vertical shorts with burned-in animated captions (an open-source OpusClip /
2short.ai clone). The project is being built phase-by-phase.

## Workflow (follow on every task)

`progress.md` is the **source of truth** for project state. It is not optional reading.

1. **Before starting any task**, read `progress.md` to see current progress, which
   phase is live, its deliverable checklist, and the next steps. Confirm the task's
   dependencies (earlier phases) are actually done before building on them.
2. **After completing a task**, update `progress.md` immediately — tick the relevant
   deliverable checkboxes, flip the phase status (⬜ → 🟡 → ✅), and add a changelog line.
3. **Whenever a decision in one phase affects a later phase** (you build something a later
   phase will reuse/replace, lock in a contract others depend on, or resolve an open
   decision), record it in the **"Carry-forward decisions (cross-phase)"** section of
   `progress.md` *and* add a short note under the affected phase's section. This keeps
   future phases from rebuilding existing work or breaking a contract.
4. **After completing a whole phase**, push to GitHub:
   `git add -A && git commit -m "Phase N: <summary>" && git push`

## Hard rules (do not violate)

- **No paid APIs, cloud services, or subscriptions.** Everything runs locally on CPU.
- **No hardcoded paths.** All paths go through `config.py` (relative to project root,
  overridable via `AUTOSHORTS_*` env vars). Use `pathlib`, never string-concatenate paths.
- **Cross-platform:** code must run unmodified on Windows 10+ and Ubuntu 22.04.
- **Python 3.12 only.** Python 3.13 fails: `av` and `numpy` have no 3.13 wheels and
  fall back to source compilation (needs MSVC). Create the venv with `py -3.12`.

## Commands

```powershell
# Activate venv (Windows)
.\venv\Scripts\Activate.ps1
# Activate venv (Ubuntu):  source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app  ->  http://127.0.0.1:5000
python app.py

# Quick health smoke-test without a browser
python -c "from app import create_app; print(create_app().test_client().get('/health').get_json())"
```

- **ffmpeg is a system dependency** (not pip). Windows: `winget install Gyan.FFmpeg`;
  Ubuntu: `sudo apt install ffmpeg`. It must be on PATH (moviepy/whisper shell out to it).
- No test framework is set up yet. When adding one, document the runner here.

## Architecture

The app is a Flask server (`app.py`) driving a 5-stage processing **pipeline** in
`pipeline/`. Data flows one direction:

```
upload → transcriber → scorer → selector → renderer (+ effects/captions) → shorts_output/
```

- **`config.py`** — single source of all configuration via the `CONFIG` object
  (`from config import CONFIG`). Holds directories, upload limits, Whisper settings,
  scoring thresholds, and render dimensions. `CONFIG.ensure_dirs()` creates runtime
  dirs. Add any new tunable here rather than hardcoding it in a module.
- **`pipeline/transcriber.py`** (Module 2) — faster-whisper (CPU/int8) → `transcript.json`
  with **word-level timestamps**. The JSON schema is defined by `sample_transcript.json`
  in the repo root; that file also lets scoring (Module 3) be developed before
  transcription exists.
- **`pipeline/scorer.py` + `selector.py`** (Module 3) — heuristic scoring (hooks,
  keywords incl. Roman Urdu, length, pauses, audio energy, repetition penalty), then
  greedy non-overlapping top-N selection. No LLM — must stay local/fast.
- **`pipeline/renderer.py` + `effects.py`** (Module 4 & 5) — cut clip, reframe to 9:16,
  apply punch-in zoom, burn word-synced animated captions, export MP4 + SRT.
- **`app.py`** — `create_app()` factory. Routes drive the pipeline; long processing is
  intended to run in a background thread with an in-memory job registry exposing progress.

The module boundaries map 1:1 to the phases in `progress.md`. Most pipeline files are
currently stubs — check `progress.md` for which phase is live before assuming behavior.

## Conventions

- Import config as `from config import CONFIG`; reference paths as `CONFIG.UPLOAD_DIR`, etc.
- Pipeline stages should be plain functions with stable signatures so the job
  orchestrator can call them uniformly and later phases can fill in stubs.
- `uploads/` and `shorts_output/` are runtime/gitignored — never commit media. The
  internal task brief under `documents/` is gitignored and must stay out of the public repo.
