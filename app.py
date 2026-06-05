"""Module 1 — Flask app entry point.

Routes:
    GET  /                       upload page
    POST /upload                 validate + store a video, start a job
    GET  /status/<job_id>        live job progress as JSON
    GET  /results/<job_id>       finished clips for a job
    GET  /download/<job_id>/...  download a generated short
    GET  /health                 liveness check
"""

from __future__ import annotations

import threading
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from config import CONFIG
from pipeline.jobs import JOBS, STATUS_QUEUED
from pipeline.orchestrator import run_pipeline


def _allowed_file(filename: str) -> bool:
    """True if the filename has a whitelisted video extension."""
    return Path(filename).suffix.lower() in CONFIG.ALLOWED_EXTENSIONS


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = CONFIG.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = CONFIG.MAX_UPLOAD_MB * 1024 * 1024
    CONFIG.ensure_dirs()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/upload", methods=["POST"])
    def upload():
        if "video" not in request.files:
            return jsonify(error="No file part named 'video'."), 400

        file = request.files["video"]
        if not file.filename:
            return jsonify(error="No file selected."), 400

        if not _allowed_file(file.filename):
            allowed = ", ".join(sorted(CONFIG.ALLOWED_EXTENSIONS))
            return jsonify(error=f"Unsupported file type. Allowed: {allowed}"), 400

        safe_name = secure_filename(file.filename) or "video"
        job = JOBS.create(filename=safe_name)

        job_dir = CONFIG.UPLOAD_DIR / job.id
        job_dir.mkdir(parents=True, exist_ok=True)
        video_path = job_dir / safe_name
        file.save(video_path)

        JOBS.update(job.id, video_path=video_path, status=STATUS_QUEUED)
        threading.Thread(
            target=run_pipeline, args=(job.id,), daemon=True
        ).start()

        return jsonify(job_id=job.id, status=job.status), 202

    @app.route("/status/<job_id>")
    def status(job_id: str):
        job = JOBS.get(job_id)
        if job is None:
            return jsonify(error="Unknown job."), 404
        return jsonify(job.to_dict())

    @app.route("/results/<job_id>")
    def results(job_id: str):
        job = JOBS.get(job_id)
        if job is None:
            return jsonify(error="Unknown job."), 404
        return jsonify(job_id=job.id, status=job.status, results=job.results)

    @app.route("/download/<job_id>/<path:filename>")
    def download(job_id: str, filename: str):
        # Guard against path traversal: only ever serve a sanitized basename
        # from inside this job's output directory.
        safe_name = secure_filename(filename)
        if not safe_name or safe_name != filename:
            abort(404)
        job_dir = (CONFIG.OUTPUT_DIR / job_id).resolve()
        target = (job_dir / safe_name).resolve()
        if job_dir not in target.parents or not target.is_file():
            abort(404)
        # `?inline=1` serves the file without forcing a download so the UI can
        # play clips in a <video> element and read an .srt in-browser. Werkzeug
        # still honors HTTP range requests, so video seeking works. Default
        # (no param) keeps the download-as-attachment behavior.
        inline = request.args.get("inline", "").lower() in {"1", "true", "yes"}
        return send_from_directory(job_dir, safe_name, as_attachment=not inline)

    @app.errorhandler(413)
    def too_large(_err):
        return jsonify(
            error=f"File too large. Max {CONFIG.MAX_UPLOAD_MB} MB."
        ), 413

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "autoshorts"}

    return app


if __name__ == "__main__":
    create_app().run(host=CONFIG.HOST, port=CONFIG.PORT, debug=True)
