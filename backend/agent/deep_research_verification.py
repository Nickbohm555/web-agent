from __future__ import annotations

from backend.agent.schemas import AgentStructuredAnswer
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


def verify_deep_research_job(job: DeepResearchJob) -> DeepResearchJob:
    return job.model_copy(update={"stage": DeepResearchStage.VERIFYING})


def finalize_deep_research_answer(job: DeepResearchJob) -> DeepResearchJob:
    basis: list[dict[str, object]] = []
    summary_lines: list[str] = []

    for artifact in job.research_artifacts:
        basis_text = f"{artifact.subquestion}: {artifact.subanswer}"
        basis.append(
            {
                "kind": "list_item",
                "text": basis_text,
                "citations": [citation.model_dump(mode="json") for citation in artifact.citations],
            }
        )
        summary_lines.append(f"- {basis_text}")

    if not summary_lines and job.sub_questions:
        summary_lines = [f"- {subquestion}" for subquestion in job.sub_questions]

    if not summary_lines:
        summary_lines = ["- No research findings were captured."]

    source_lines = [f"- {source.title}: {source.url}" for source in job.sources[:5]]
    answer_sections = ["Research summary:", *summary_lines]
    if source_lines:
        answer_sections.extend(["", "Key sources:", *source_lines])
    answer_text = "\n".join(answer_sections)

    return job.model_copy(
        update={
            "stage": DeepResearchStage.COMPLETED,
            "final_answer": AgentStructuredAnswer(
                text=answer_text,
                basis=basis,
            ),
        }
    )
