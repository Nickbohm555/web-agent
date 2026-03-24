from __future__ import annotations

from backend.agent.deep_agents.schemas.persisted_plan import PersistedPlanArtifact
from backend.agent.deep_agents.schemas.persisted_status import PersistedStatusArtifact
from backend.agent.deep_research_runtime import (
    run_deep_research_job,
    start_deep_research,
)
from backend.agent.deep_research_store import InMemoryDeepResearchStore
from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.agent.schemas.deep_research import DeepResearchPlan, DeepResearchStage
from backend.api.schemas import AgentRunQueuedResponse


class RecordingArtifactRepository:
    def __init__(self) -> None:
        self.plan_artifacts: list[PersistedPlanArtifact] = []
        self.subquestion_artifacts: list[dict[str, object]] = []
        self.status_artifacts: list[PersistedStatusArtifact] = []
        self.final_answer_artifacts: list[dict[str, str]] = []

    def write_plan(self, artifact: PersistedPlanArtifact) -> PersistedPlanArtifact:
        self.plan_artifacts.append(artifact)
        return artifact

    def read_plan(self, run_id: str) -> PersistedPlanArtifact | None:
        for artifact in reversed(self.plan_artifacts):
            if artifact.run_id == run_id:
                return artifact
        return None

    def write_subquestions(self, *, run_id: str, sub_questions: list[str]) -> dict[str, object]:
        artifact = {
            "run_id": run_id,
            "sub_questions": list(sub_questions),
            "artifact_path": f"/runs/{run_id}/subquestions.json",
        }
        self.subquestion_artifacts.append(artifact)
        return artifact

    def read_subquestions(self, run_id: str) -> list[str]:
        for artifact in reversed(self.subquestion_artifacts):
            if artifact["run_id"] == run_id:
                return list(artifact["sub_questions"])
        return []

    def write_status(self, artifact: PersistedStatusArtifact) -> PersistedStatusArtifact:
        self.status_artifacts.append(artifact)
        return artifact

    def read_status(self, run_id: str) -> PersistedStatusArtifact | None:
        for artifact in reversed(self.status_artifacts):
            if artifact.run_id == run_id:
                return artifact
        return None

    def write_final_answer(self, *, run_id: str, markdown: str) -> dict[str, str]:
        artifact = {
            "run_id": run_id,
            "markdown": markdown,
            "artifact_path": f"/runs/{run_id}/final_answer.md",
        }
        self.final_answer_artifacts.append(artifact)
        return artifact


def test_start_deep_research_returns_queued_response_and_persists_job() -> None:
    store = InMemoryDeepResearchStore()
    scheduled_job_ids: list[str] = []

    response = start_deep_research(
        prompt="Investigate market share",
        retrieval_policy=AgentRunRetrievalPolicy(),
        store=store,
        schedule_job=scheduled_job_ids.append,
        run_id_factory=lambda: "run-deep-queued",
        thread_id_factory=lambda run_id: f"thread-{run_id}",
    )

    assert isinstance(response, AgentRunQueuedResponse)
    assert response.model_dump() == {
        "run_id": "run-deep-queued",
        "status": "queued",
        "metadata": {"execution_surface": "background"},
    }
    assert scheduled_job_ids == ["run-deep-queued"]

    saved = store.get_required("run-deep-queued")
    assert saved.prompt == "Investigate market share"
    assert saved.thread_id == "thread-run-deep-queued"
    assert saved.stage == "queued"
    assert saved.wave_count == 0
    assert saved.sub_questions == []
    assert saved.sources == []


def test_deep_research_runtime_persists_plan_before_wave_execution() -> None:
    store = InMemoryDeepResearchStore()
    artifact_repository = RecordingArtifactRepository()
    wave_execution_inputs: list[list[str]] = []

    start_deep_research(
        prompt="Investigate deep research",
        retrieval_policy=AgentRunRetrievalPolicy(),
        store=store,
        schedule_job=lambda _job_id: None,
        run_id_factory=lambda: "run-deep-complete",
        thread_id_factory=lambda run_id: f"thread-{run_id}",
    )

    run_deep_research_job(
        "run-deep-complete",
        store=store,
        artifact_repository=artifact_repository,
        plan_builder=lambda job: DeepResearchPlan(
            sub_questions=["What is deep research?", "How long can it run?"]
        ),
        supervisor_builder=lambda: object(),
        wave_executor=lambda job: job.model_copy(
            update={
                "stage": "searching",
                "wave_count": 2,
                "sources": [
                    {
                        "title": "Primary source",
                        "url": "https://example.com/source",
                        "snippet": "Evidence snippet.",
                    }
                ],
            }
        )
        if not wave_execution_inputs.append(list(job.sub_questions))
        else job,
        verifier=lambda job: job.model_copy(update={"stage": "verifying"}),
        finalizer=lambda job: job.model_copy(
            update={
                "stage": "completed",
                "final_answer": {"text": "Deep research answer."},
            }
        ),
    )

    saved = store.get_required("run-deep-complete")
    assert saved.stage == "completed"
    assert saved.thread_id == "thread-run-deep-complete"
    assert saved.sub_questions == ["What is deep research?", "How long can it run?"]
    assert saved.wave_count == 2
    assert saved.final_answer is not None
    assert saved.final_answer.text == "Deep research answer."
    assert [str(source.url) for source in saved.sources] == ["https://example.com/source"]
    assert wave_execution_inputs == [["What is deep research?", "How long can it run?"]]
    assert artifact_repository.plan_artifacts[0].model_dump() == {
        "run_id": "run-deep-complete",
        "prompt": "Investigate deep research",
        "plan_markdown": "- What is deep research?\n- How long can it run?",
        "sub_questions": ["What is deep research?", "How long can it run?"],
    }
    assert artifact_repository.subquestion_artifacts == [
        {
            "run_id": "run-deep-complete",
            "sub_questions": ["What is deep research?", "How long can it run?"],
            "artifact_path": "/runs/run-deep-complete/subquestions.json",
        }
    ]
    assert [artifact.stage for artifact in artifact_repository.status_artifacts] == [
        DeepResearchStage.PLANNING,
        DeepResearchStage.PLANNING,
        DeepResearchStage.SEARCHING,
        DeepResearchStage.VERIFYING,
        DeepResearchStage.SYNTHESIZING,
        DeepResearchStage.COMPLETED,
    ]
