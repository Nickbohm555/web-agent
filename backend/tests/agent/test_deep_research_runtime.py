from __future__ import annotations

from backend.agent.deep_research_runtime import (
    run_deep_research_job,
    start_deep_research,
)
from backend.agent.deep_research_store import InMemoryDeepResearchStore
from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.api.schemas import AgentRunQueuedResponse


def test_start_deep_research_returns_queued_response_and_persists_job() -> None:
    store = InMemoryDeepResearchStore()
    scheduled_job_ids: list[str] = []

    response = start_deep_research(
        prompt="Investigate market share",
        retrieval_policy=AgentRunRetrievalPolicy(),
        store=store,
        schedule_job=scheduled_job_ids.append,
        run_id_factory=lambda: "run-deep-queued",
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
    assert saved.stage == "queued"
    assert saved.wave_count == 0
    assert saved.sub_questions == []
    assert saved.sources == []


def test_deep_research_runtime_plans_then_executes_waves_then_marks_complete() -> None:
    store = InMemoryDeepResearchStore()
    start_deep_research(
        prompt="Investigate deep research",
        retrieval_policy=AgentRunRetrievalPolicy(),
        store=store,
        schedule_job=lambda _job_id: None,
        run_id_factory=lambda: "run-deep-complete",
    )

    run_deep_research_job(
        "run-deep-complete",
        store=store,
        plan_builder=lambda job: ["What is deep research?", "How long can it run?"],
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
    assert saved.sub_questions == ["What is deep research?", "How long can it run?"]
    assert saved.wave_count == 2
    assert saved.final_answer is not None
    assert saved.final_answer.text == "Deep research answer."
    assert [str(source.url) for source in saved.sources] == ["https://example.com/source"]
