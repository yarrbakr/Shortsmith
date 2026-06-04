"""Module 1 — In-memory job registry.

A job tracks the lifecycle of one uploaded video as it moves through the
pipeline (transcribe -> score -> select -> render). The registry is held in
memory and guarded by a lock so the request threads and the background
processing thread can read/write it safely.

There is no persistence by design (Phase 1 backbone); jobs vanish on restart.

Import the shared singleton as `from pipeline.jobs import JOBS`.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Status values a job can hold. Kept as plain strings for easy JSON exposure.
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_ERROR = "error"


@dataclass
class Job:
    """State for a single processing job."""

    id: str
    filename: str
    status: str = STATUS_QUEUED
    progress: int = 0  # 0-100
    message: str = "Queued."
    error: str | None = None
    video_path: Path | None = None
    results: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """JSON-safe view of the job for the status/results routes."""
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "results": self.results,
            "created_at": self.created_at,
        }


class JobManager:
    """Thread-safe in-memory registry of jobs keyed by id."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, filename: str) -> Job:
        """Register a new job with a unique id and return it."""
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, filename=filename)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> Job | None:
        """Atomically update fields on a job. Unknown ids are ignored."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            return job


# Shared singleton used by the routes and the orchestrator.
JOBS = JobManager()
