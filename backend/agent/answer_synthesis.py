from __future__ import annotations

from typing import Any, Protocol, Sequence

from backend.agent.runtime_errors import elapsed_ms
from backend.agent.schemas import AgentRunResult, AgentSourceReference, AgentStructuredAnswer
from backend.agent.schemas.quick_answer import (
    QuickAnswerSynthesisRequest,
    QuickEvidenceBundle,
    QuickEvidenceSource,
)

DEFAULT_QUICK_ANSWER_MODEL = "gpt-4.1-mini"


class QuickAnswerResponsesClient(Protocol):
    def create(self, *, model: str, input: str) -> Any:
        ...


class QuickAnswerClient(Protocol):
    responses: QuickAnswerResponsesClient


def build_quick_answer_evidence_bundle(
    *,
    question: str,
    sources: Sequence[AgentSourceReference],
) -> QuickEvidenceBundle:
    return QuickEvidenceBundle(
        question=question,
        sources=[
            QuickEvidenceSource(
                source_id=source.source_id,
                title=source.title,
                url=source.url,
                excerpt=source.snippet,
            )
            for source in sources
        ],
    )


def build_quick_answer_prompt(*, question: str, evidence: QuickEvidenceBundle) -> str:
    request = QuickAnswerSynthesisRequest(question=question, evidence=evidence)
    lines = [
        "You are answering a user question from retrieved web evidence.",
        "Use only the evidence below.",
        "Return a concise answer with no markdown preamble.",
        "",
        f"Question: {request.question}",
        "",
        "Evidence:",
    ]

    if not request.evidence.sources:
        lines.append("- No sources were provided.")
    else:
        for source in request.evidence.sources:
            lines.extend(
                [
                    f"- Source ID: {source.source_id}",
                    f"  Title: {source.title}",
                    f"  URL: {source.url}",
                    f"  Excerpt: {source.excerpt}",
                ]
            )

    return "\n".join(lines)


def synthesize_quick_answer(
    *,
    run_id: str,
    started_at: float,
    question: str,
    evidence: QuickEvidenceBundle,
    client: QuickAnswerClient | None = None,
    model: str = DEFAULT_QUICK_ANSWER_MODEL,
    tool_call_count: int = 0,
) -> AgentRunResult:
    prompt = build_quick_answer_prompt(question=question, evidence=evidence)
    answer_client = client or build_default_quick_answer_client()
    completion = answer_client.responses.create(model=model, input=prompt)
    output_text = extract_output_text(completion)

    return AgentRunResult(
        run_id=run_id,
        status="completed",
        final_answer=AgentStructuredAnswer(text=output_text),
        sources=[source_reference_from_quick_source(source) for source in evidence.sources],
        tool_call_count=tool_call_count,
        elapsed_ms=elapsed_ms(started_at),
    )


def build_default_quick_answer_client() -> QuickAnswerClient:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(
            "OpenAI client dependencies are unavailable; provide a quick answer client"
        ) from exc

    return OpenAI()


def extract_output_text(completion: Any) -> str:
    output_text = getattr(completion, "output_text", None)
    if isinstance(output_text, str):
        normalized = output_text.strip()
        if normalized:
            return normalized

    if isinstance(completion, dict):
        maybe_output_text = completion.get("output_text")
        if isinstance(maybe_output_text, str):
            normalized = maybe_output_text.strip()
            if normalized:
                return normalized

    raise ValueError("quick answer synthesis returned no text")


def source_reference_from_quick_source(source: QuickEvidenceSource) -> AgentSourceReference:
    return AgentSourceReference(
        source_id=source.source_id,
        title=source.title,
        url=source.url,
        snippet=source.excerpt,
    )
