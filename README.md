# AutoShorts AI

Turn long videos into short, vertical (9:16) clips with burned-in animated
captions — **100% local, free, and CPU-only**. An open-source alternative to
OpusClip / 2short.ai / Vidyo.ai. No cloud, no API keys, no subscriptions.

## Features
- Upload a long video and get the best short clips automatically
- Local AI transcription (faster-whisper, word-level timestamps)
- Smart clip selection (hooks, keywords, pauses, audio energy)
- 9:16 vertical reframing with a punch-in zoom effect
- Animated, word-synced captions burned into the video
- SRT subtitle export

## Requirements
- Python 3.10+
- ffmpeg on your system PATH
  - Windows: `winget install Gyan.FFmpeg`
  - Ubuntu: `sudo apt install ffmpeg`

## Quick start
```bash
# 1. Create and activate a virtual environment
python -m venv venv
# Windows:  .\venv\Scripts\Activate.ps1
# Ubuntu:   source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
# open http://127.0.0.1:5000
```

## Project structure
```
autoshorts/
├── app.py                 # Flask app + routes (Module 1)
├── config.py              # Central config, no hardcoded paths
├── pipeline/
│   ├── transcriber.py     # faster-whisper -> transcript.json (Module 2)
│   ├── scorer.py          # clip scoring (Module 3)
│   ├── selector.py        # top-N non-overlapping selection (Module 3)
│   ├── renderer.py        # 9:16 render pipeline (Module 4)
│   └── effects.py         # zoom / crop / captions (Module 4 & 5)
├── static/{style.css, app.js}
├── templates/index.html
├── uploads/               # user uploads (gitignored)
└── shorts_output/         # generated clips (gitignored)
```

## License
MIT (planned — to be added before public release).
