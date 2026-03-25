from __future__ import annotations

import re

from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchPlan


def build_deep_research_plan(job: DeepResearchJob) -> DeepResearchPlan:
    normalized_prompt = " ".join(job.prompt.split())
    if not normalized_prompt:
        return DeepResearchPlan(sub_questions=[])

    clauses = _extract_clauses(normalized_prompt)
    if len(clauses) >= 2:
        return DeepResearchPlan(
            sub_questions=[
                f"What does the available evidence say about {clause}?"
                for clause in clauses[:4]
            ]
        )

    return DeepResearchPlan(
        sub_questions=[
            f"What are the core facts needed to answer: {normalized_prompt}?",
            f"Which sources best support the answer to: {normalized_prompt}?",
        ]
    )


def _extract_clauses(prompt: str) -> list[str]:
    prompt_without_command = re.sub(
        r"^(compare|research|investigate|summarize)\s+",
        "",
        prompt,
        count=1,
        flags=re.IGNORECASE,
    )
    pieces = re.split(r"\s+\band\b\s+|,|;", prompt_without_command)
    return [piece.strip(" .") for piece in pieces if piece.strip(" .")]
