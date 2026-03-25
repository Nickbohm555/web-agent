from __future__ import annotations

from threading import Thread

from backend.agent.deep_research_runtime import run_deep_research_job


def schedule_deep_research_job(job_id: str) -> None:
    """Start the deep-research worker in a background thread.

    Example input: "run-deep-123"
    Example output: None
    """

    worker = Thread(
        target=run_deep_research_job,
        args=(job_id,),
        daemon=True,
        name=f"deep-research-{job_id}",
    )
    worker.start()
