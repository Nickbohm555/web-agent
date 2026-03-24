from __future__ import annotations

from backend.agent.deep_agents.logging import log_deep_research_stage
from backend.agent.deep_agents.schemas.persisted_status import PersistedStatusArtifact
from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


class RecordingStatusRepository:
    def __init__(self) -> None:
        self.status_artifacts: list[PersistedStatusArtifact] = []

    def write_status(self, artifact: PersistedStatusArtifact) -> PersistedStatusArtifact:
        self.status_artifacts.append(artifact)
        return artifact


def test_log_deep_research_stage_persists_status_and_structured_log_payload() -> None:
    job = DeepResearchJob(
        job_id="run-deep-logging",
        thread_id="thread-run-deep-logging",
        prompt="Investigate logging support",
        retrieval_policy=AgentRunRetrievalPolicy(),
        stage=DeepResearchStage.QUEUED,
        sub_questions=["Initial question"],
    )
    artifact_repository = RecordingStatusRepository()
    records: list[dict[str, object]] = []

    updated_job = log_deep_research_stage(
        job,
        stage=DeepResearchStage.SEARCHING,
        artifact_repository=artifact_repository,
        artifact_path="/runs/run-deep-logging/status.json",
        emit_log=records.append,
    )

    assert updated_job.stage == DeepResearchStage.SEARCHING
    assert artifact_repository.status_artifacts[0].model_dump(mode="json") == {
        "run_id": "run-deep-logging",
        "thread_id": "thread-run-deep-logging",
        "stage": "searching",
        "artifact_path": "/runs/run-deep-logging/status.json",
        "sub_questions": ["Initial question"],
        "error": None,
    }
    assert records == [
        {
            "run_id": "run-deep-logging",
            "thread_id": "thread-run-deep-logging",
            "stage": "searching",
            "artifact_path": "/runs/run-deep-logging/status.json",
        }
    ]
