# UI-UX.md — Visual Design & Experience Plan

> **Purpose:** Where we make the website genuinely *visually appealing* and pleasant to use.
> Owns the design system (palette, type, spacing, components), the current-state audit, and a
> prioritised list of UI/UX improvements.
>
> **Relationship to the other docs:** feature *behaviour* and delivery status live in
> `progress.md` (source of truth) and are indexed in `Features.md`; the *why* behind shipped
> UI decisions is logged in `RESEARCH.md` (see its "Frontend & Integration (Module 6)"
> section). This file is the forward-looking *visual* plan — when a UI improvement ships, tick
> it here and record the rationale in `RESEARCH.md` / detail in `progress.md`.

Stack: **plain HTML/CSS/JS, no framework** (deliberate — keeps it local, dependency-free).
Files: `templates/index.html`, `static/style.css`, `static/app.js`.

---

## Design system (current, from `static/style.css`)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0a0a0f` | page background (with a radial accent glow at top) |
| `--card` / `--card-2` | `#14141c` / `#0f0f17` | surfaces |
| `--border` | `#26263a` | hairlines |
| `--accent` / `--accent-soft` | `#7c3aed` / `rgba(124,58,237,.15)` | brand purple, used in captions too |
| `--text` / `--muted` | `#e8e8ef` / `#9a9ab0` | foreground / secondary |
| `--danger` | `#f0506e` | errors |
| `--radius` | `14px` | corner rounding |
| Font | `system-ui` stack | UI text (captions use bundled Anton) |

Layout: single column, `width: min(92vw, 1040px)`, hero → upload card → status card →
results grid. Already responsive and mobile-friendly.

> **Brand consistency note:** the caption accent `#7C3AED` and the UI accent are intentionally
> the same purple — keep them in sync so previews feel native to the page.

---

## Current-state audit

**Working well**
- Cohesive dark theme with a tasteful top accent glow.
- Drag-and-drop dropzone, staged progress chips, live `/status` polling.
- Responsive CSS-grid results cards with inline 9:16 `<video>` previews + caption viewer.

**Pain points / opportunities**
1. **Inline preview audio control is greyed out** (tracked as bug A1 in `Features.md`) — UX
   wart on the results grid.
2. **Static, generic typography** — system font only; the hero could carry more brand
   character (a display face for the wordmark).
3. **No empty/first-run state** beyond the upload card — no example, no "what you'll get".
4. **Progress feels flat** — chips + a bar; no per-stage time/feel of momentum, no clip-count
   preview as results arrive.
5. **Results grid is functional, not delightful** — cards could show the virality grade (B3),
   hover affordances, and quick actions (copy SRT, regenerate).
6. **No light theme / no theme toggle** (low priority; dark is on-brand).
7. **No in-UI customisation** of caption style/color/aspect once those features (B1/B5) land —
   the UI needs to grow controls for them.

---

## Design principles

1. **Local-first, instant feel.** No web fonts/CDNs that hit the network — bundle any custom
   font under `assets/`/`static/` (as we already do for captions). Keep it snappy.
2. **The preview is the hero.** The product *is* the vertical clip — make 9:16 previews crisp,
   centered, and the visual focal point.
3. **One brand purple.** `#7C3AED` ties the page and the burned-in captions together.
4. **Show momentum.** Processing can take minutes; the UI should always communicate progress
   and reveal results incrementally.
5. **Progressive disclosure.** Defaults work out of the box; advanced controls (caption style,
   aspect, music) are tucked into an "Advanced" reveal so the first run stays one click.

---

## Improvement backlog (prioritised)

Legend: 📋 Planned · 🟡 In progress · ✅ Done

| # | Improvement | Status | Notes |
|---|---|---|---|
| U1 | Fix greyed inline-audio control | 📋 | Same work as `Features.md` A1; biggest visible UX wart. |
| U2 | Brand the wordmark (bundled display font for the hero/logo) | 📋 | Self-hosted; no network. Reuse the caption font or add one under `static/fonts/`. |
| U3 | Richer first-run / empty state | 📋 | Short "how it works" + sample output thumbnail before any upload. |
| U4 | Virality grade on result cards | ✅ | Shipped with `Features.md` B3 — letter pill + "Virality NN" + *relative* "Stands out" signal + score bar + collapsible per-signal breakdown. Grade colours are a deliberate green→red data-viz ramp (exception to "one brand purple"). Confirmed live. |
| U5 | Results card polish | 📋 | Hover lift, quick actions (Download MP4/SRT, copy captions), nicer loading skeletons. |
| U6 | More alive progress | 📋 | Per-stage state + incremental "clips ready" count as they finish. |
| U7 | "Advanced options" panel | 🟡 | **Seeded by B1, extended by B2/B4/B5:** the "Advanced options" `<details>` reveal hosts the caption-style `<select>` (B1, Hormozi default / word-pop), an aspect-ratio `<select>` (B5, 9:16 / 1:1 / 4:5 / 16:9, 9:16 default), a "Remove filler words & silences" checkbox (B2), and an auto-emoji checkbox (B4). Still to add: music toggle (B6). |
| U8 | Micro-interactions & transitions | 📋 | Subtle dropzone hover, chip fills, card entrance — restrained, not flashy. |

> As pipeline features (B1, B5, B6, …) land, their UI controls slot into **U7** and get ticked
> both here and in `Features.md`.
