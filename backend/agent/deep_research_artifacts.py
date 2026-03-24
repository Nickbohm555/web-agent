from __future__ import annotations

import re

from backend.agent.schemas import AgentAnswerCitation, AgentSourceReference
from backend.agent.schemas.deep_research_subagent import DeepResearchArtifactRecord

_NON_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def build_research_artifact_path(job_id: str, subquestion_index: int, slug: str) -> str:
    return f"/workspace/research/{job_id}/{subquestion_index:02d}-{slug}.md"


def build_research_artifact_record(
    *,
    subquestion: str,
    subanswer: str,
    artifact_path: str,
    sources: list[AgentSourceReference],
    citations: list[AgentAnswerCitation],
) -> DeepResearchArtifactRecord:
    return DeepResearchArtifactRecord(
        subquestion=subquestion,
        subanswer=subanswer,
        sources=sources,
        citations=citations,
        artifact_path=artifact_path,
    )


def slugify_subquestion(subquestion: str) -> str:
    slug = _NON_SLUG_PATTERN.sub("-", subquestion.strip().lower()).strip("-")
    return slug or "research-thread"
