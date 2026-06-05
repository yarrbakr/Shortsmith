# AutoShorts AI

Turn long videos into short, vertical (9:16) clips with burned-in animated
captions — **100% local, free, and CPU-only**. An open-source alternative to
OpusClip / 2short.ai / Vidyo.ai. No cloud, no API keys, no subscriptions.

## Features
- Upload a long video and get the best short clips automatically
- Local AI transcription (faster-whisper, word-level timestamps)
- Smart clip selection (hooks, keywords incl. Roman Urdu, pauses, audio energy)
- 9:16 vertical reframing with a punch-in zoom effect
- Animated, word-synced captions burned into the video
- SRT subtitle export per clip
- Clean web UI: drag-and-drop upload, live progress, inline clip previews,
  one-click MP4 / SRT downloads, and a per-clip caption viewer

## Screenshots
> Captured from the running app at `http://127.0.0.1:5000`.

![Upload + results UI](docs/screenshot-results.png)

_(If the image is missing, run the app and drop in a video — the results grid
renders inline 9:16 previews with download and caption controls.)_

## Requirements
- **Python 3.12** (3.13 is not supported — `av`/`numpy` have no 3.13 wheels and
  fall back to source compilation).
- ffmpeg on your system PATH
  - Windows: `winget install Gyan.FFmpeg`
  - Ubuntu: `sudo apt install ffmpeg`

## Quick start
```bash
# 1. Create and activate a virtual environment (Python 3.12)
py -3.12 -m venv venv          # Windows
# python3.12 -m venv venv      # Ubuntu
# Windows:  .\venv\Scripts\Activate.ps1
# Ubuntu:   source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
# open http://127.0.0.1:5000
```

## Usage
1. Open `http://127.0.0.1:5000`.
2. Drag a video onto the dropzone (or click to browse) and press
   **Upload & Process**. Supported: MP4, MOV, MKV, WEBM, AVI, M4V (up to 1 GB).
3. Watch the staged progress — Transcribe → Score → Select → Render.
4. When it finishes, each generated short appears as a card with an inline
   9:16 preview. Use **Download MP4**, **Download SRT**, or **Captions** (to
   read the clip's transcript) on each card. **Process another video** resets
   the page.

Everything runs on your CPU; the first run downloads the faster-whisper `base`
model once, then works fully offline.

### Performance
Target throughput: a ~15-minute video yields ~3 shorts in roughly 15 minutes on
a typical desktop i5 (CPU-only). Render time scales with clip count, length, and
the chosen Whisper model size (`AUTOSHORTS_WHISPER_MODEL`).

## Configuration
All tunables live in `config.py` and are overridable via `AUTOSHORTS_*`
environment variables (model size, clip count/duration, caption style, render
codec, output/upload dirs, etc.). No paths are hardcoded; defaults are relative
to the project root.

## Project structure
```
autoshorts/
├── app.py                 # Flask app + routes (Module 1)
├── config.py              # Central config, no hardcoded paths
├── pipeline/
│   ├── jobs.py            # In-memory job registry (Module 1)
│   ├── orchestrator.py    # Background stage runner (Module 1)
│   ├── transcriber.py     # faster-whisper -> transcript.json (Module 2)
│   ├── scorer.py          # clip scoring (Module 3)
│   ├── selector.py        # top-N non-overlapping selection (Module 3)
│   ├── renderer.py        # 9:16 render pipeline (Module 4)
│   ├── effects.py         # zoom / crop frame transforms (Module 4)
│   └── captions.py        # word-synced captions + SRT (Module 5)
├── static/{style.css, app.js}
├── templates/index.html
├── assets/fonts/          # bundled OFL caption font (committed)
├── uploads/               # user uploads (gitignored)
└── shorts_output/         # generated clips (gitignored)
```

## License
MIT — see [LICENSE](LICENSE).
