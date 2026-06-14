// Module 6 — upload, drag-and-drop, live progress, results grid + caption viewer.
"use strict";

const form = document.getElementById("upload-form");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("video-input");
const dzHint = document.getElementById("dz-hint");
const submitBtn = document.getElementById("submit-btn");

const statusCard = document.getElementById("status");
const statusText = document.getElementById("status-text");
const barFill = document.getElementById("bar-fill");
const stagesEl = document.getElementById("stages");

const resultsSection = document.getElementById("results-section");
const resultsGrid = document.getElementById("results");
const resultsCount = document.getElementById("results-count");
const resultsPlural = document.getElementById("results-plural");
const resetBtn = document.getElementById("reset-btn");

const DEFAULT_HINT = dzHint.innerHTML;
// progress % at which each stage becomes active (matches the orchestrator).
const STAGE_THRESHOLDS = { transcribe: 10, score: 40, select: 60, render: 65 };

let pollTimer = null;
let currentJobId = null;

// --- File selection (click + drag-and-drop) --------------------------------

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) selectFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-active");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-active");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer?.files?.[0];
  if (!file) return;
  fileInput.files = e.dataTransfer.files;
  selectFile(file);
});

function selectFile(file) {
  dzHint.textContent = `${file.name} · ${formatSize(file.size)}`;
  submitBtn.disabled = false;
}

// --- Upload + polling ------------------------------------------------------

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;

  const data = new FormData();
  data.append("video", fileInput.files[0]);
  const styleSel = document.getElementById("caption-style");
  if (styleSel) data.append("caption_style", styleSel.value);
  const aspectSel = document.getElementById("aspect-ratio");
  if (aspectSel) data.append("aspect_ratio", aspectSel.value);

  setBusy(true);
  resultsSection.classList.add("hidden");
  resultsGrid.innerHTML = "";
  statusCard.classList.remove("hidden", "error");
  render({ status: "uploading", progress: 0, message: "Uploading…" });

  try {
    const res = await fetch("/upload", { method: "POST", body: data });
    const body = await res.json();
    if (!res.ok) {
      renderError(body.error || "Upload failed.");
      setBusy(false);
      return;
    }
    currentJobId = body.job_id;
    poll(body.job_id);
  } catch (err) {
    renderError("Network error: " + err);
    setBusy(false);
  }
});

function poll(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/status/${jobId}`);
      const job = await res.json();
      render(job);
      if (job.status === "done" || job.status === "error") {
        clearInterval(pollTimer);
        setBusy(false);
        if (job.status === "done") showResults(jobId, job.results);
        else renderError(job.message || "Processing failed.");
      }
    } catch (err) {
      clearInterval(pollTimer);
      renderError("Lost connection: " + err);
      setBusy(false);
    }
  }, 1000);
}

// --- Rendering -------------------------------------------------------------

function render(job) {
  const pct = Math.max(0, Math.min(100, job.progress || 0));
  barFill.style.width = pct + "%";
  statusText.textContent = job.message || `[${job.status}]`;

  // Light up the stage chips based on progress.
  for (const chip of stagesEl.querySelectorAll(".stage")) {
    const threshold = STAGE_THRESHOLDS[chip.dataset.stage];
    chip.classList.toggle("active", pct >= threshold);
  }
}

function renderError(message) {
  statusCard.classList.remove("hidden");
  statusCard.classList.add("error");
  statusText.textContent = message;
  barFill.style.width = "100%";
}

function showResults(jobId, results) {
  resultsGrid.innerHTML = "";
  const clips = results || [];

  resultsCount.textContent = clips.length;
  resultsPlural.style.display = clips.length === 1 ? "none" : "inline";
  resultsSection.classList.remove("hidden");

  if (!clips.length) {
    const empty = document.createElement("p");
    empty.className = "empty-note";
    empty.textContent = "No clips were generated for this video.";
    resultsGrid.appendChild(empty);
    return;
  }

  clips.forEach((clip, i) => resultsGrid.appendChild(buildCard(jobId, clip, i)));
}

function buildCard(jobId, clip, index) {
  const srtFile = clip.file.replace(/\.mp4$/i, ".srt");
  const srtUrl = `/download/${jobId}/${encodeURIComponent(srtFile)}`;
  const duration = clip.end != null && clip.start != null ? clip.end - clip.start : null;

  const card = document.createElement("article");
  card.className = "clip-card";

  const video = document.createElement("video");
  video.className = "clip-video";
  video.controls = true;
  video.preload = "metadata";
  video.src = `${clip.url}?inline=1`;
  card.appendChild(video);

  const body = document.createElement("div");
  body.className = "clip-body";

  const title = document.createElement("h3");
  title.className = "clip-title";
  title.textContent = `Clip ${index + 1}`;
  body.appendChild(title);

  if (clip.grade) body.appendChild(buildGrade(clip));

  const badges = document.createElement("div");
  badges.className = "badges";
  if (clip.start != null && clip.end != null) {
    badges.appendChild(badge(`${formatTime(clip.start)}–${formatTime(clip.end)}`));
  }
  if (duration != null) badges.appendChild(badge(`${duration.toFixed(1)}s`));
  body.appendChild(badges);

  const actions = document.createElement("div");
  actions.className = "actions";
  actions.appendChild(linkBtn(clip.url, "Download MP4", "primary"));
  actions.appendChild(linkBtn(srtUrl, "Download SRT", "secondary"));

  const capBtn = document.createElement("button");
  capBtn.type = "button";
  capBtn.className = "btn secondary";
  capBtn.textContent = "Captions";
  actions.appendChild(capBtn);
  body.appendChild(actions);

  const captions = document.createElement("pre");
  captions.className = "captions hidden";
  body.appendChild(captions);

  let loaded = false;
  capBtn.addEventListener("click", async () => {
    captions.classList.toggle("hidden");
    capBtn.classList.toggle("active");
    if (loaded || captions.classList.contains("hidden")) return;
    loaded = true;
    captions.textContent = "Loading captions…";
    try {
      const res = await fetch(`${srtUrl}?inline=1`);
      captions.textContent = res.ok ? (parseSrt(await res.text()) || "No captions for this clip.")
                                    : "No captions for this clip.";
    } catch {
      captions.textContent = "Could not load captions.";
    }
  });

  card.appendChild(body);
  return card;
}

// --- Virality grade (B3) ---------------------------------------------------

// Labels for the scorer's per-signal components (mirrors scorer.SIGNAL_LABELS).
const SIGNAL_LABELS = {
  hook: "Hook",
  length: "Length",
  pause: "Clean cut",
  energy: "Energy",
  repetition: "Clarity",
};

// Build the grade block: letter pill + "Virality NN" + strongest signal, a
// score bar, and a collapsible per-signal breakdown.
function buildGrade(clip) {
  const g = clip.grade;
  const wrap = document.createElement("div");
  wrap.className = "grade";

  const head = document.createElement("div");
  head.className = "grade-head";

  const pill = document.createElement("span");
  pill.className = `grade-pill grade-${g.letter}`;
  pill.textContent = g.letter;
  head.appendChild(pill);

  const meta = document.createElement("div");
  meta.className = "grade-meta";
  const scoreEl = document.createElement("span");
  scoreEl.className = "grade-score";
  scoreEl.textContent = `Virality ${g.pct}`;
  meta.appendChild(scoreEl);
  if (clip.top_signal) {
    const why = document.createElement("span");
    why.className = "grade-why";
    why.textContent = `Stands out: ${clip.top_signal}`;
    meta.appendChild(why);
  }
  head.appendChild(meta);
  wrap.appendChild(head);

  const bar = document.createElement("div");
  bar.className = "grade-bar";
  const fill = document.createElement("div");
  fill.className = `grade-bar-fill grade-${g.letter}`;
  fill.style.width = g.pct + "%";
  bar.appendChild(fill);
  wrap.appendChild(bar);

  if (clip.components) wrap.appendChild(buildBreakdown(clip.components));
  return wrap;
}

// Collapsible "Why this grade?" — a mini bar per scoring signal (0..1 → %).
function buildBreakdown(components) {
  const details = document.createElement("details");
  details.className = "breakdown";

  const summary = document.createElement("summary");
  summary.textContent = "Why this grade?";
  details.appendChild(summary);

  const list = document.createElement("div");
  list.className = "breakdown-list";
  for (const [key, label] of Object.entries(SIGNAL_LABELS)) {
    const value = components[key];
    if (value == null) continue;
    const row = document.createElement("div");
    row.className = "breakdown-row";

    const name = document.createElement("span");
    name.className = "breakdown-label";
    name.textContent = label;

    const track = document.createElement("div");
    track.className = "breakdown-track";
    const fill = document.createElement("div");
    fill.className = "breakdown-fill";
    fill.style.width = Math.round(value * 100) + "%";
    track.appendChild(fill);

    row.appendChild(name);
    row.appendChild(track);
    list.appendChild(row);
  }
  details.appendChild(list);
  return details;
}

// --- Small helpers ---------------------------------------------------------

function badge(text, variant) {
  const span = document.createElement("span");
  span.className = "badge-chip" + (variant ? ` ${variant}` : "");
  span.textContent = text;
  return span;
}

function linkBtn(href, text, variant) {
  const a = document.createElement("a");
  a.className = `btn ${variant}`;
  a.href = href;
  a.textContent = text;
  a.setAttribute("download", "");
  return a;
}

// Strip SRT index + "00:00 --> 00:00" timing lines, keep the spoken text.
function parseSrt(srt) {
  return srt
    .split(/\r?\n/)
    .filter((line) => line.trim() && !/^\d+$/.test(line.trim()) && !line.includes("-->"))
    .join(" ")
    .trim();
}

function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function formatSize(bytes) {
  if (bytes >= 1024 * 1024 * 1024) return (bytes / 1024 ** 3).toFixed(1) + " GB";
  if (bytes >= 1024 * 1024) return (bytes / 1024 ** 2).toFixed(1) + " MB";
  return (bytes / 1024).toFixed(0) + " KB";
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  submitBtn.textContent = busy ? "Processing…" : "Upload & Process";
}

resetBtn.addEventListener("click", () => {
  clearInterval(pollTimer);
  currentJobId = null;
  form.reset();
  dzHint.innerHTML = DEFAULT_HINT;
  submitBtn.disabled = true;
  statusCard.classList.add("hidden");
  statusCard.classList.remove("error");
  resultsSection.classList.add("hidden");
  resultsGrid.innerHTML = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
});
