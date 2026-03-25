from __future__ import annotations

from backend.agent.deep_agents.schemas.persisted_plan import PersistedPlanArtifact
from backend.agent.deep_agents.schemas.persisted_status import PersistedStatusArtifact
from backend.agent.deep_research_execution import execute_research_waves
from backend.agent.deep_research_planning import build_deep_research_plan
from backend.agent.deep_research_runtime import (
    run_deep_research_job,
    start_deep_research,
)
from backend.agent.deep_research_store import InMemoryDeepResearchStore
from backend.agent.deep_research_verification import finalize_deep_research_answer
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchPlan, DeepResearchStage
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


def test_start_deep_research_uses_explicit_thread_id_when_supplied() -> None:
    store = InMemoryDeepResearchStore()

    response = start_deep_research(
        prompt="Investigate market share",
        store=store,
        schedule_job=lambda _job_id: None,
        run_id_factory=lambda: "run-deep-explicit-thread",
        thread_id="thread-custom-123",
    )

    assert response.run_id == "run-deep-explicit-thread"
    assert store.get_required("run-deep-explicit-thread").thread_id == "thread-custom-123"


def test_build_deep_research_plan_decomposes_multi_part_prompts() -> None:
    plan = build_deep_research_plan(
        DeepResearchJob(
            job_id="run-plan",
            thread_id="thread-run-plan",
            prompt="Compare OpenAI and Anthropic enterprise product strategies",
            stage=DeepResearchStage.QUEUED,
        )
    )

    assert len(plan.sub_questions) >= 2
    assert any("OpenAI" in question for question in plan.sub_questions)
    assert any("Anthropic" in question for question in plan.sub_questions)


def test_deep_research_runtime_persists_plan_before_wave_execution() -> None:
    store = InMemoryDeepResearchStore()
    artifact_repository = RecordingArtifactRepository()
    delegated_subquestions: list[str] = []

    start_deep_research(
        prompt="Investigate deep research",
        store=store,
        schedule_job=lambda _job_id: None,
        run_id_factory=lambda: "run-deep-complete",
        thread_id_factory=lambda run_id: f"thread-{run_id}",
    )

    def delegate_subquestion(supervisor: object, subquestion: str) -> dict[str, object]:
        delegated_subquestions.append(subquestion)
        return {
            "subquestion": subquestion,
            "subanswer": f"Answer for {subquestion}",
            "sources": [
                {
                    "title": "Primary source",
                    "url": "https://example.com/source",
                    "snippet": "Evidence snippet.",
                }
            ],
            "citations": [],
        }

    run_deep_research_job(
        "run-deep-complete",
        store=store,
        artifact_repository=artifact_repository,
        plan_builder=lambda job: DeepResearchPlan(
            sub_questions=["What is deep research?", "How long can it run?"]
        ),
        supervisor_builder=lambda **_: object(),
        wave_executor=lambda job: execute_research_waves(
            job,
            supervisor_builder=lambda **_: object(),
            delegate_subquestion=delegate_subquestion,
        ),
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
    assert delegated_subquestions == ["What is deep research?", "How long can it run?"]
    assert saved.final_answer is not None
    assert saved.final_answer.text == "Deep research answer."
    assert [str(source.url) for source in saved.sources] == ["https://example.com/source"]
    assert [artifact.artifact_path for artifact in saved.research_artifacts] == [
        "/workspace/research/run-deep-complete/00-what-is-deep-research.md",
        "/workspace/research/run-deep-complete/01-how-long-can-it-run.md",
    ]
    assert [event.model_dump() for event in saved.progress_events] == [
        {
            "subquestion": "What is deep research?",
            "status": "completed",
            "artifact_path": "/workspace/research/run-deep-complete/00-what-is-deep-research.md",
        },
        {
            "subquestion": "How long can it run?",
            "status": "completed",
            "artifact_path": "/workspace/research/run-deep-complete/01-how-long-can-it-run.md",
        },
    ]
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


def test_deep_research_runtime_progress_artifacts_use_workspace_paths() -> None:
    store = InMemoryDeepResearchStore()
    artifact_repository = RecordingArtifactRepository()

    start_deep_research(
        prompt="Investigate deep research progress",
        store=store,
        schedule_job=lambda _job_id: None,
        run_id_factory=lambda: "run-deep-progress",
        thread_id_factory=lambda run_id: f"thread-{run_id}",
    )

    run_deep_research_job(
        "run-deep-progress",
        store=store,
        artifact_repository=artifact_repository,
        plan_builder=lambda job: DeepResearchPlan(
            sub_questions=["What is deep research?", "How long can it run?"]
        ),
        supervisor_builder=lambda **_: object(),
        wave_executor=lambda job: execute_research_waves(
            job,
            supervisor_builder=lambda **_: object(),
            delegate_subquestion=lambda _supervisor, subquestion: {
                "subquestion": subquestion,
                "subanswer": f"Answer for {subquestion}",
                "sources": [],
                "citations": [],
            },
        ),
        verifier=lambda job: job.model_copy(update={"stage": "verifying"}),
        finalizer=lambda job: job.model_copy(
            update={
                "stage": "completed",
                "final_answer": {"text": "Deep research answer."},
            }
        ),
    )

    saved = store.get_required("run-deep-progress")
    assert saved.wave_count == 2
    assert all(
        artifact.artifact_path.startswith("/workspace/research/")
        for artifact in saved.research_artifacts
    )


def test_deep_research_runtime_evidence_normalizes_sources_from_subagents() -> None:
    store = InMemoryDeepResearchStore()
    artifact_repository = RecordingArtifactRepository()

    start_deep_research(
        prompt="Investigate deep research evidence",
        store=store,
        schedule_job=lambda _job_id: None,
        run_id_factory=lambda: "run-deep-evidence",
        thread_id_factory=lambda run_id: f"thread-{run_id}",
    )

    run_deep_research_job(
        "run-deep-evidence",
        store=store,
        artifact_repository=artifact_repository,
        plan_builder=lambda job: DeepResearchPlan(
            sub_questions=["What is deep research?", "How long can it run?"]
        ),
        supervisor_builder=lambda **_: object(),
        wave_executor=lambda job: execute_research_waves(
            job,
            supervisor_builder=lambda **_: object(),
            delegate_subquestion=lambda _supervisor, subquestion: {
                "subquestion": subquestion,
                "subanswer": f"Answer for {subquestion}",
                "sources": [
                    {
                        "title": "Primary source",
                        "url": "https://example.com/source",
                        "snippet": "Evidence snippet.",
                    }
                ],
                "citations": [],
            },
        ),
        verifier=lambda job: job.model_copy(update={"stage": "verifying"}),
        finalizer=lambda job: job.model_copy(
            update={
                "stage": "completed",
                "final_answer": {"text": "Deep research answer."},
            }
        ),
    )
    saved = store.get_required("run-deep-evidence")
    assert [str(source.url) for source in saved.sources] == ["https://example.com/source"]


def test_finalize_deep_research_answer_synthesizes_artifacts_into_structured_answer() -> None:
    finalized = finalize_deep_research_answer(
        DeepResearchJob(
            job_id="run-deep-finalize",
            thread_id="thread-run-deep-finalize",
            prompt="Compare two launch strategies",
            stage=DeepResearchStage.SYNTHESIZING,
            sources=[
                {
                    "title": "Primary source",
                    "url": "https://example.com/source",
                    "snippet": "Evidence snippet.",
                }
            ],
            research_artifacts=[
                {
                    "subquestion": "What is strategy A?",
                    "subanswer": "Strategy A prioritizes fast launch velocity.",
                    "sources": [
                        {
                            "title": "Primary source",
                            "url": "https://example.com/source",
                            "snippet": "Evidence snippet.",
                        }
                    ],
                    "citations": [],
                    "artifact_path": "/workspace/research/run-deep-finalize/00-strategy-a.md",
                },
                {
                    "subquestion": "What is strategy B?",
                    "subanswer": "Strategy B prioritizes governance and review.",
                    "sources": [
                        {
                            "title": "Primary source",
                            "url": "https://example.com/source",
                            "snippet": "Evidence snippet.",
                        }
                    ],
                    "citations": [],
                    "artifact_path": "/workspace/research/run-deep-finalize/01-strategy-b.md",
                },
            ],
        )
    )

    assert finalized.stage == DeepResearchStage.COMPLETED
    assert finalized.final_answer is not None
    assert "Research summary:" in finalized.final_answer.text
    assert "What is strategy A?" in finalized.final_answer.text
    assert "What is strategy B?" in finalized.final_answer.text
    assert finalized.final_answer.model_dump(mode="json")["basis"] == [
        {
            "kind": "list_item",
            "text": "What is strategy A?: Strategy A prioritizes fast launch velocity.",
            "citations": [],
        },
        {
            "kind": "list_item",
            "text": "What is strategy B?: Strategy B prioritizes governance and review.",
            "citations": [],
        },
    ]
