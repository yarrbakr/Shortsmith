"""Module 1 — Stage orchestrator.

Runs an uploaded video through the pipeline in a background thread, updating
the job's progress as it goes:

    transcribe -> score -> select -> render

In Phase 1 the stages are stubs that raise ``NotImplementedError``; the
orchestrator catches that and stops the job cleanly with a message naming the
stage. Phases 2-5 fill in the stage bodies and this file needs no changes.
"""

from __future__ import annotations

from config import CONFIG
from pipeline import renderer, scorer, selector, transcriber
from pipeline.jobs import JOBS, STATUS_DONE, STATUS_ERROR, STATUS_PROCESSING


def run_pipeline(job_id: str) -> None:
    """Process a job end-to-end. Intended to run in a daemon thread."""
    job = JOBS.get(job_id)
    if job is None or job.video_path is None:
        return

    video_path = job.video_path
    work_dir = CONFIG.UPLOAD_DIR / job_id
    out_dir = CONFIG.OUTPUT_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        JOBS.update(job_id, status=STATUS_PROCESSING, progress=10,
                    message="Transcribing audio...")
        transcript = transcriber.transcribe(video_path, work_dir)

        JOBS.update(job_id, progress=40, message="Scoring segments...")
        scored = scorer.score(transcript, video_path)

        JOBS.update(job_id, progress=60, message="Selecting best clips...")
        selected = selector.select(scored, CONFIG.TOP_N_CLIPS)

        JOBS.update(job_id, progress=65, message="Rendering clips...")
        results: list[dict] = []
        total = len(selected) or 1
        # The whole batch's per-signal scores, so each clip's "stands out"
        # signal is judged relative to its peers (B3).
        peer_components = [c.get("components") or {} for c in selected]
        # Per-job caption style (B1) + auto-emoji toggle (B4) ride on the clip
        # dict so the locked renderer.render signature stays unchanged;
        # apply_captions reads them.
        caption_style = job.caption_style or CONFIG.CAPTION_STYLE
        auto_emoji = job.auto_emoji if job.auto_emoji is not None else CONFIG.CAPTION_EMOJI_ENABLED
        for index, clip in enumerate(selected):
            clip["caption_style"] = caption_style
            clip["auto_emoji"] = auto_emoji
            clip["trim_silence"] = job.trim_silence  # B2: per-job filler/silence removal
            out_path = renderer.render(video_path, clip, out_dir)
            components = clip.get("components")
            results.append({
                "file": out_path.name,
                "url": f"/download/{job_id}/{out_path.name}",
                "start": clip.get("start"),
                "end": clip.get("end"),
                "score": clip.get("score"),
                # Virality grade (B3): surface the score the scorer already
                # computed as a 0-100 + A-F grade, with its per-signal breakdown.
                "grade": scorer.grade(clip.get("score") or 0.0),
                "components": components,
                "top_signal": scorer.top_signal(components, peers=peer_components),
            })
            progress = 65 + int((index + 1) / total * 35)
            JOBS.update(job_id, progress=progress, results=list(results))

        JOBS.update(job_id, status=STATUS_DONE, progress=100,
                    message=f"Done. {len(results)} clip(s) ready.",
                    results=results)

    except NotImplementedError as exc:
        # Expected in Phase 1: a downstream stage is still a stub. Stop cleanly.
        JOBS.update(job_id, status=STATUS_ERROR, message=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client
        JOBS.update(job_id, status=STATUS_ERROR,
                    message="Processing failed.", error=repr(exc))
