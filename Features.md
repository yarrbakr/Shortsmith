# Features.md — Feature & Branch Tracker

> **Purpose:** A lightweight index of *what features exist / are planned*, *which branch
> each lives in*, and *which branch we're working on right now*.
>
> **Relationship to the other docs (read this):**
> - **`progress.md` is the source of truth.** The *detailed* spec, deliverable checklist,
>   carry-forward decisions, and changelog for every feature live there. This file is just
>   the at-a-glance feature → branch → status index that points back into `progress.md`.
> - **`FEATURE-RESEARCH.md`** holds the web research and the *why* / feasibility behind each
>   candidate feature below.
> - **`UI-UX.md`** owns the visual-design plan for anything UI-facing.
>
> When a feature graduates from "Planned" to "In progress", give it a section in
> `progress.md` (mirroring the Phase 0–6 format) and link it from the table here.

**Repo:** https://github.com/yarrbakr/Shortsmith

---

## 🌿 Currently working on

| | |
|---|---|
| **Active branch** | `feature/caption-styles` (dev on `claude/eager-ride-707rtd`) — **B1** built |
| **Phase** | v1 complete (Phases 0–6 ✅). Post-v1: **B3** + **B1** shipped. |
| **Next up** | _Pick the next backlog item — e.g. B2 silence-trim, A1 audio fix, or B8 grade calibration._ |

---

## Branching workflow (adopted 2026-06-07)

One feature → one branch. `main` always stays releasable.

- **Branch naming:** `feature/<short-kebab-name>` for new capability,
  `fix/<short-kebab-name>` for bug/polish, `chore/<short-kebab-name>` for tooling/docs.
- **Lifecycle:** cut from latest `main` → build → update `progress.md` → merge back to `main`
  (then push, per the CLAUDE.md workflow rule) → delete the branch.
- **One in flight at a time** for now (single developer); the table's *Active branch* row above
  names whichever is current.
- Keep the **Status** column here in sync with `progress.md` when a feature moves.

Legend: 📋 Planned · 🟡 In progress · ✅ Done · 🧊 Deferred (out of scope / needs cloud-GPU)

---

## Shipped (v1 — all on `main`)

These are the Phase 0–6 features. Full detail in `progress.md`.

| Feature | Branch | Status | Detail |
|---|---|---|---|
| Upload + job pipeline backbone | `main` | ✅ | progress.md → Phase 1 |
| Local transcription (faster-whisper, word-level) | `main` | ✅ | progress.md → Phase 2 |
| Heuristic clip scoring + selection | `main` | ✅ | progress.md → Phase 3 |
| 9:16 render + zoom/fades/watermark effects | `main` | ✅ | progress.md → Phase 4 |
| Word-synced animated captions + SRT export | `main` | ✅ | progress.md → Phase 5 |
| Web UI (upload, progress, results grid, caption viewer) | `main` | ✅ | progress.md → Phase 6 |

---

## Backlog (post-v1)

Prioritised against the two chosen directions: **(A) Fix & polish v1** and
**(B) New pipeline features**. Feasibility/why → `FEATURE-RESEARCH.md`.

### A — Fix & polish v1

| # | Feature | Proposed branch | Status | Notes |
|---|---|---|---|---|
| A1 | Fix greyed-out in-browser audio control on inline previews | `fix/inline-audio-preview` | 📋 | Deferred bug from Phase 6 (downloads are fine; cosmetic). See progress.md → Phase 6 "Known issue". |
| A2 | Reliability / error-surfacing pass on the pipeline | `chore/pipeline-hardening` | 📋 | Better job-failure messages in UI; guard edge cases. |

### B — New pipeline features (local-CPU feasible)

| # | Feature | Proposed branch | Status | Notes |
|---|---|---|---|---|
| B1 | Multiple caption styles (Hormozi multi-word + highlight / word-pop) | `feature/caption-styles` | ✅ | Added the dominant 2026 **Hormozi** karaoke style (phrase + highlighted spoken word) next to word-pop; selectable via env + a UI "Advanced options" dropdown; default now Hormozi. Per-job style rides the clip dict (no render-contract change). progress.md → Post-v1 → B1. |
| B2 | Filler-word & silence removal | `feature/silence-trim` | 📋 | Reuse scorer's filler lists + word timestamps; splice them out. |
| B3 | Virality score / A–F grade in the UI | `feature/virality-score` | ✅ | Surfaces the score we **already compute** as A–F + 0–100 + a *relative* standout signal + collapsible per-signal breakdown. Confirmed live. progress.md → Post-v1 → B3. Follow-up: **B8**. |
| B4 | Auto-emojis on captions | `feature/auto-emoji` | 📋 | Local keyword→emoji dict; no AI/cloud. |
| B5 | Platform export presets (9:16 / 1:1 / 4:5 / 16:9) | `feature/aspect-presets` | 📋 | Config-driven render dimensions per target platform. |
| B6 | Background music (bundled royalty-free, ducked under speech) | `feature/bg-music` | 📋 | Ship OFL/CC0 tracks; mix at low volume. |
| B7 | Active-speaker tracking auto-reframe (eased pan) | `feature/speaker-tracking` | 📋 | Upgrade of existing optional Haar face detection → tracked panning. Heaviest of the set on CPU. |
| B8 | Spread / calibrate the virality grade scale | `feature/grade-calibration` | 📋 | **Refines B3.** On uniform talking-head content the heuristic signals saturate/zero/flatten so grades cluster (most clips → B). Relabel as a relative ranking + curve the %, or recalibrate `GRADE_THRESHOLDS`. Deferred until tested on varied real video (don't over-tune on one sample). progress.md → B3 "Known limitation". |

### Deferred — needs cloud/GPU (violates the local-CPU hard rule)

| Feature | Status | Why deferred |
|---|---|---|
| AI-generated B-roll (text-to-video) | 🧊 | Requires cloud/GPU generation. Possible local stretch: insert from a *user-provided* keyword-tagged clip library. |
| LLM semantic highlight detection ("ClipAnything") | 🧊 | Needs an LLM. We stay heuristic-only for v1+. |
| AI voice dubbing / translation | 🧊 | Cloud/GPU. |
