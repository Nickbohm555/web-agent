from __future__ import annotations

from backend.agent.deep_research_execution import execute_research_waves
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


class StubSupervisor:
    def __init__(self) -> None:
        self.inputs: list[dict[str, object]] = []

    def invoke(self, inputs: dict[str, object]) -> dict[str, object]:
        self.inputs.append(inputs)
        return {
            "final_answer": {
                "text": "Founded in 2015 and known for ChatGPT.",
                "citations": [],
            },
            "sources": [
                {
                    "title": "OpenAI",
                    "url": "https://openai.com/about",
                    "snippet": "OpenAI is an AI research and deployment company.",
                }
            ],
        }


def test_execute_research_waves_invokes_supervisor_when_no_delegate_is_injected() -> None:
    supervisor = StubSupervisor()
    job = DeepResearchJob(
        job_id="run-deep-execution",
        thread_id="thread-run-deep-execution",
        prompt="Research OpenAI founding and products",
        stage=DeepResearchStage.PLANNING,
        sub_questions=["Research OpenAI founding and products"],
    )

    updated = execute_research_waves(
        job,
        supervisor_builder=lambda **_: supervisor,
    )

    assert supervisor.inputs == [
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Research OpenAI founding and products",
                }
            ]
        }
    ]
    assert updated.stage == DeepResearchStage.SEARCHING
    assert updated.wave_count == 1
    assert updated.research_artifacts[0].subanswer == "Founded in 2015 and known for ChatGPT."
