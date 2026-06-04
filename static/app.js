// Module 1 — minimal upload + live progress polling. Full UI in Phase 6.
"use strict";

const form = document.getElementById("upload-form");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status");
const statusText = document.getElementById("status-text");
const barFill = document.getElementById("bar-fill");
const resultsList = document.getElementById("results");

let pollTimer = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("video-input");
  if (!input.files.length) return;

  const data = new FormData();
  data.append("video", input.files[0]);

  setBusy(true);
  resultsList.innerHTML = "";
  statusBox.classList.remove("hidden");
  render({ status: "uploading", progress: 0, message: "Uploading..." });

  try {
    const res = await fetch("/upload", { method: "POST", body: data });
    const body = await res.json();
    if (!res.ok) {
      render({ status: "error", progress: 0, message: body.error || "Upload failed." });
      setBusy(false);
      return;
    }
    poll(body.job_id);
  } catch (err) {
    render({ status: "error", progress: 0, message: "Network error: " + err });
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
        if (job.status === "done") showResults(job.results);
      }
    } catch (err) {
      clearInterval(pollTimer);
      render({ status: "error", progress: 0, message: "Lost connection: " + err });
      setBusy(false);
    }
  }, 1000);
}

function render(job) {
  const pct = Math.max(0, Math.min(100, job.progress || 0));
  barFill.style.width = pct + "%";
  statusText.textContent = `[${job.status}] ${job.message || ""}`;
}

function showResults(results) {
  resultsList.innerHTML = "";
  (results || []).forEach((clip) => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = clip.url;
    link.textContent = `Download ${clip.file}`;
    li.appendChild(link);
    resultsList.appendChild(li);
  });
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  submitBtn.textContent = busy ? "Processing..." : "Upload & Process";
}
