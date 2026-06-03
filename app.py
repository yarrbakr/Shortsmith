"""Module 1 — Flask app entry point.

Routes: upload, process, progress, results, download.

TODO: implement in Phase 1. For now this just boots so the scaffold runs.
"""

from __future__ import annotations

from flask import Flask

from config import CONFIG


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = CONFIG.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = CONFIG.MAX_UPLOAD_MB * 1024 * 1024
    CONFIG.ensure_dirs()

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "autoshorts"}

    return app


if __name__ == "__main__":
    create_app().run(host=CONFIG.HOST, port=CONFIG.PORT, debug=True)
