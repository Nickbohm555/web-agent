from __future__ import annotations

from typing import Any, Callable

from backend.agent.deep_research_artifacts import (
    build_research_artifact_path,
    build_research_artifact_record,
    slugify_subquestion,
)
from backend.agent.deep_research_progress import append_progress_event
from backend.agent.deep_research_supervisor import build_deep_research_supervisor
from backend.agent.runtime_sources import (
    RuntimeSourceRegistry,
    extract_final_answer,
    extract_sources,
)
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage
from backend.agent.schemas.deep_research_subagent import DeepResearchSubagentResult


def execute_research_waves(
    job: DeepResearchJob,
    *,
    supervisor_builder: Callable[..., Any] | None = None,
    delegate_subquestion: Callable[[Any, str], Any] | None = None,
) -> DeepResearchJob:
    effective_supervisor_builder = supervisor_builder or build_deep_research_supervisor
    supervisor = effective_supervisor_builder(
        plan_subquestions=job.sub_questions,
    )
    source_registry = RuntimeSourceRegistry.empty()
    research_artifacts = list(job.research_artifacts)
    progress_events = list(job.progress_events)

    for subquestion_index, subquestion in enumerate(job.sub_questions):
        raw_result = _delegate_subquestion(
            supervisor=supervisor,
            subquestion=subquestion,
            delegate_subquestion=delegate_subquestion,
        )
        validated_result = DeepResearchSubagentResult.model_validate(raw_result)
        artifact_path = build_research_artifact_path(
            job.job_id,
            subquestion_index,
            slugify_subquestion(validated_result.subquestion),
        )

        for source in validated_result.sources:
            source_registry.register(
                url=str(source.url),
                title=source.title,
                snippet=source.snippet,
            )

        normalized_subanswer = extract_final_answer(
            {
                "final_answer": {
                    "text": validated_result.subanswer,
                    "citations": [
                        citation.model_dump(mode="json")
                        for citation in validated_result.citations
                    ],
                }
            },
            source_lookup=source_registry.source_lookup(),
        )

        research_artifacts.append(
            build_research_artifact_record(
                subquestion=validated_result.subquestion,
                subanswer=normalized_subanswer.text,
                artifact_path=artifact_path,
                sources=validated_result.sources,
                citations=normalized_subanswer.citations,
            )
        )
        progress_events = append_progress_event(
            progress_events,
            subquestion=validated_result.subquestion,
            status="completed",
            artifact_path=artifact_path,
        )

    return job.model_copy(
        update={
            "stage": DeepResearchStage.SEARCHING,
            "wave_count": len(job.sub_questions),
            "sources": source_registry.sources(),
            "research_artifacts": research_artifacts,
            "progress_events": progress_events,
        }
    )


def _delegate_subquestion(
    *,
    supervisor: Any,
    subquestion: str,
    delegate_subquestion: Callable[[Any, str], Any] | None,
) -> Any:
    if delegate_subquestion is not None:
        return delegate_subquestion(supervisor, subquestion)

    if not hasattr(supervisor, "invoke"):
        raise RuntimeError("delegate_subquestion is required for Phase 4 fan-out execution")

    raw_result = supervisor.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": subquestion,
                }
            ]
        }
    )
    source_registry = extract_sources(raw_result)
    final_answer = extract_final_answer(raw_result, source_registry.source_lookup())
    return {
        "subquestion": subquestion,
        "subanswer": final_answer.text,
        "sources": [source.model_dump(mode="json") for source in source_registry.sources()],
        "citations": [citation.model_dump(mode="json") for citation in final_answer.citations],
    }
