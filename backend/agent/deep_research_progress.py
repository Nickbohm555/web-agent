from __future__ import annotations

from backend.agent.schemas.deep_research import DeepResearchProgressRecord


def build_subquestion_progress_record(
    subquestion: str,
    status: str,
    artifact_path: str | None = None,
) -> DeepResearchProgressRecord:
    return DeepResearchProgressRecord(
        subquestion=subquestion,
        status=status,
        artifact_path=artifact_path,
    )


def append_progress_event(
    events: list[DeepResearchProgressRecord],
    *,
    subquestion: str,
    status: str,
    artifact_path: str | None = None,
) -> list[DeepResearchProgressRecord]:
    return [
        *events,
        build_subquestion_progress_record(
            subquestion=subquestion,
            status=status,
            artifact_path=artifact_path,
        ),
    ]
