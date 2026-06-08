# FEATURE-RESEARCH.md — Web Research on Features We Could Build

> **Purpose:** Forward-looking research on *what features could go into Shortsmith*, drawn
> from the web (competitors + open-source alternatives), each filtered through our hard rule:
> **100% local, free, CPU-only.**
>
> **Not to be confused with `RESEARCH.md`**, which is the internal *design-decisions /
> trade-offs log* for choices already made. This file is the idea/feasibility pipeline that
> feeds the backlog in **`Features.md`**; once a feature is chosen and built, the *why* of how
> we implemented it gets recorded in `RESEARCH.md` and the detail in `progress.md`.

Last researched: **2026-06-07**.

---

## The filter: what "local CPU-only" rules in and out

Most commercial tools (OpusClip, Submagic, Klap, Choppity) lean on cloud GPU + LLMs for
their headline features. Our constraint flips the priority order: features that are *pure
rendering or heuristics* are cheap and on-brand for us, while anything needing a generative
model or large LLM is out (or a far-future stretch). Encouragingly, **much of the "viral"
feel is rendering + timing, not generation** — and we already have the plumbing (word-level
timestamps, a heuristic scorer with filler lists, a moviepy caption engine, optional Haar
face detection).

---

## What the market ships in 2026 (and our take)

### Captions — word-by-word highlight is the dominant style
The best-performing 2026 caption style is **word-by-word / short-phrase**, high-contrast
(white-on-black-outline or yellow-on-black), in the lower-middle third, with the active word
highlighted in a contrasting color — a karaoke rhythm. Popular named styles: **Hormozi**
(bold, punchy), **karaoke** (line visible, active word highlighted), **minimal**. Tools
advertise 18+ styles, often rendered via the ASS subtitle format.
- **Our take (HIGH value / LOW effort):** we currently do *single-word pop* only. Adding a
  small set of styles — Hormozi, multi-word karaoke line, minimal — is pure rendering on top
  of the existing engine. → `Features.md` **B1**.

### Hook detection & "virality score"
Competitors run AI to find hooks and assign a **virality score (0–100, plus A–F category
grades)** predicting performance.
- **Our take (HIGH perceived value / near-zero effort):** we *already compute* per-clip
  heuristic scores with a per-signal `components` breakdown (hook/length/pause/energy/
  repetition). We can map that to a 0–100 + A–F grade and **surface it in the UI** without
  any new modeling. The LLM-driven version stays out. → **B3**.

### B-Roll
OpusClip/Submagic auto-insert contextually relevant B-roll — royalty-free stock *or*
**AI-generated** clips for abstract concepts.
- **Our take:** AI generation is **out** (cloud/GPU) → 🧊. A *local* stretch: let the user
  drop a keyword-tagged clip folder and we insert matches by transcript keyword. Parked.

### Auto-reframe & active-speaker tracking
CV tracks face positions across frames and applies **eased pan** when speakers move; handles
multi-speaker (split-screen), gaming (PiP facecam), panels (3-screen).
- **Our take (MED value / MED-HIGH effort):** we already have optional Haar-cascade detection
  that biases a *static* crop. Upgrading to *tracked, eased panning* is feasible on CPU
  (sample frames, smooth the path). Multi-layout split-screen is a later stretch. → **B7**.

### Silence & filler-word removal
"Magic cut" / one-click removal of silences and filler words ("um", "like", awkward pauses)
is a staple editing feature.
- **Our take (HIGH value / LOW-MED effort):** we already have word-level timestamps **and**
  filler-word/phrase lists in the scorer. Removing them is timeline splicing — fully local.
  → **B2**.

### Auto-emojis
Tools sprinkle context-relevant (sometimes animated) emojis onto captions.
- **Our take (LOW effort, fun):** a local keyword→emoji dictionary applied at caption build
  time. No AI, no cloud. → **B4**.

### Background music
AI "audio matching" picks copyright-free tracks matching each segment's mood.
- **Our take (MED value / LOW effort):** skip the AI matching; **bundle a few OFL/CC0 tracks**
  and mix one in, ducked under speech. → **B6**.

### Multi-format / aspect ratios
Tools auto-adapt to 9:16, 1:1, 4:5, 16:9 per platform.
- **Our take (LOW effort):** config-driven render dimensions + export presets. → **B5**.

### Filler features we're NOT chasing
Cloud publishing/scheduling, AI voice dubbing/translation, "ClipAnything" LLM semantic
understanding — all require cloud/GPU/LLM. 🧊 Deferred.

---

## Open-source alternatives worth studying (for technique, not dependency)

Useful to compare implementation choices; **we stay fully local** (several of these default
to cloud APIs for the LLM/highlight step — we deliberately don't):

- **SamurAIGPT / AI-Youtube-Shorts-Generator** — yt-dlp + faster-whisper + ffmpeg/opencv;
  has an offline "Local" mode. Good reference for the YouTube-URL ingest path.
- **OpenShorts (mutonby)** — faster-whisper *word-level* subtitles burned via ffmpeg, hook
  text overlays, FFmpeg final assembly. Closest to our caption approach.
- **ClippedAI (Shaarav4795)** — 9:16 auto-resize, animated subtitles, viral-title gen (uses
  `clipsai`).
- **Supoclip (FujiwaraChoki)** — general OpusClip-alternative reference.

> Takeaway: there's **no** fully-local OSS tool that nails clip-detection + captioning +
> styling together — that's exactly Shortsmith's niche. Most lean on a cloud LLM for the
> "smart" step; our heuristic scorer is the differentiator.

---

## Sources

- [Opus Clip 2026 overview — Quasa](https://quasa.io/video/opus-clip-2026-the-best-ai-video-clip-generator-for-viral-shorts)
- [OpusClip AI B-Roll Generator](https://www.opus.pro/tools/ai-b-roll-generator)
- [Opus Clip tested 2026 — BIGVU](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/)
- [Top AI Clipping Tools in 2026 — Reap](https://reap.video/blog/top-ai-clipping-tools-in-2026)
- [AI-Youtube-Shorts-Generator — GitHub](https://github.com/samuraigpt/ai-youtube-shorts-generator)
- [OpenShorts — GitHub](https://github.com/mutonby/openshorts)
- [ClippedAI — GitHub](https://github.com/Shaarav4795/ClippedAI)
- [Supoclip — GitHub](https://github.com/FujiwaraChoki/supoclip)
- [TikTok Caption Styles 2026 — Blitzcut](https://blitzcutai.com/blog/best-caption-style-tiktok)
- [Best Caption Styles for Marketing Videos 2026 — Poko](https://poko.video/blog/best-caption-styles-for-marketing-videos-2026-guide)
- [Viral Shorts video templates — Klap](https://klap.app/blog/social-media-video-templates)
- [Auto Reframe — CaptionX](https://caption-x.com/auto-reframe-premiere-pro)
- [Filler-word removal — quso.ai](https://quso.ai/products/filler-word-removal)
- [Auto Video Editor / silence removal — VEED](https://www.veed.io/tools/auto-video-editor)
- [AI B-Roll — Submagic](https://www.submagic.co/features/b-roll)
- [How to Edit Short-Form Video 2026 — Descript](https://www.descript.com/blog/article/edit-short-form-video)
