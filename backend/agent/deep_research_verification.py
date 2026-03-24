from __future__ import annotations

from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


def verify_deep_research_job(job: DeepResearchJob) -> DeepResearchJob:
    return job.model_copy(update={"stage": DeepResearchStage.VERIFYING})


def finalize_deep_research_answer(job: DeepResearchJob) -> DeepResearchJob:
    answer_text = "Deep research is complete."
    if job.sub_questions:
        answer_text = "Deep research covered: " + "; ".join(job.sub_questions)

    return job.model_copy(
        update={
            "stage": DeepResearchStage.COMPLETED,
            "final_answer": {"text": answer_text},
        }
    )
