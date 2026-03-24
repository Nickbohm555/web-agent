from __future__ import annotations

from backend.agent.deep_agents.resume import restore_deep_research_job
from backend.agent.deep_agents.schemas.persisted_status import PersistedStatusArtifact
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


class RecordingResumeRepository:
    def __init__(self) -> None:
        self.status_artifact = PersistedStatusArtifact(
            run_id="run-deep-resume",
            thread_id="thread-run-deep-resume",
            stage=DeepResearchStage.SEARCHING,
            artifact_path="/runs/run-deep-resume/status.json",
            sub_questions=["Existing question"],
        )

    def read_status(self, run_id: str) -> PersistedStatusArtifact | None:
        if run_id == "run-deep-resume":
            return self.status_artifact
        return None

    def read_subquestions(self, run_id: str) -> list[str]:
        if run_id == "run-deep-resume":
            return ["Existing question"]
        return []


class RecordingCheckpointRepository:
    def __init__(self) -> None:
        self.thread_ids: list[str] = []

    def has_thread(self, thread_id: str) -> bool:
        self.thread_ids.append(thread_id)
        return thread_id == "thread-run-deep-resume"


def test_restore_deep_research_job_reuses_checkpoint_backed_thread_state() -> None:
    job = DeepResearchJob(
        job_id="run-deep-resume",
        thread_id="thread-run-deep-resume",
        prompt="Investigate resume support",
        stage=DeepResearchStage.QUEUED,
    )
    artifact_repository = RecordingResumeRepository()
    checkpoint_repository = RecordingCheckpointRepository()

    restored = restore_deep_research_job(
        job,
        artifact_repository=artifact_repository,
        checkpoint_repository=checkpoint_repository,
    )

    assert checkpoint_repository.thread_ids == ["thread-run-deep-resume"]
    assert restored.stage == DeepResearchStage.SEARCHING
    assert restored.sub_questions == ["Existing question"]
    assert restored.thread_id == "thread-run-deep-resume"
