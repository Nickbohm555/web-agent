from __future__ import annotations

from backend.agent.schemas.deep_research import DeepResearchJob


class InMemoryDeepResearchStore:
    def __init__(self) -> None:
        self._jobs: dict[str, DeepResearchJob] = {}

    def save(self, job: DeepResearchJob) -> DeepResearchJob:
        normalized_job = DeepResearchJob.model_validate(
            {field_name: getattr(job, field_name) for field_name in DeepResearchJob.model_fields}
        )
        self._jobs[normalized_job.job_id] = normalized_job
        return normalized_job

    def get(self, job_id: str) -> DeepResearchJob | None:
        return self._jobs.get(job_id)

    def get_required(self, job_id: str) -> DeepResearchJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown deep research job: {job_id}")
        return job


_DEFAULT_DEEP_RESEARCH_STORE = InMemoryDeepResearchStore()


def get_default_deep_research_store() -> InMemoryDeepResearchStore:
    return _DEFAULT_DEEP_RESEARCH_STORE
