from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.agent.answer_synthesis import build_quick_answer_prompt, synthesize_quick_answer
from backend.agent.schemas import AgentRunResult
from backend.agent.schemas.quick_answer import QuickEvidenceBundle, QuickEvidenceSource


@dataclass
class StubQuickAnswerResponses:
    output_text: str
    captured_model: str | None = None
    captured_input: str | None = None

    def create(self, *, model: str, input: str) -> Any:
        self.captured_model = model
        self.captured_input = input
        return type("StubResponse", (), {"output_text": self.output_text})()


@dataclass
class StubQuickAnswerClient:
    responses: StubQuickAnswerResponses


def test_build_quick_answer_prompt_includes_question_evidence_and_source_ids() -> None:
    prompt = build_quick_answer_prompt(
        question="What is the refund policy?",
        evidence=QuickEvidenceBundle(
            question="What is the refund policy?",
            sources=[
                QuickEvidenceSource(
                    source_id="src-1",
                    title="Refunds",
                    url="https://example.com/refunds",
                    excerpt="30-day refund policy",
                )
            ],
        ),
    )

    assert "What is the refund policy?" in prompt
    assert "src-1" in prompt
    assert "30-day refund policy" in prompt


def test_synthesize_quick_answer_returns_structured_answer_and_sources() -> None:
    responses = StubQuickAnswerResponses(output_text="Customers can request a refund within 30 days.")
    client = StubQuickAnswerClient(responses=responses)

    result = synthesize_quick_answer(
        run_id="run-1",
        started_at=0.0,
        question="What is the refund policy?",
        evidence=QuickEvidenceBundle(
            question="What is the refund policy?",
            sources=[
                QuickEvidenceSource(
                    source_id="src-1",
                    title="Refunds",
                    url="https://example.com/refunds",
                    excerpt="30-day refund policy",
                )
            ],
        ),
        client=client,
    )

    assert isinstance(result, AgentRunResult)
    assert result.final_answer is not None
    assert result.final_answer.text == "Customers can request a refund within 30 days."
    assert result.sources[0].source_id == "src-1"
    assert responses.captured_model is not None
    assert responses.captured_input is not None
