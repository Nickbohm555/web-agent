from __future__ import annotations

import asyncio
from typing import Protocol

from backend.agent.deep_agents.persistence.store import create_deep_research_store
from backend.agent.deep_agents.schemas.persisted_plan import PersistedPlanArtifact
from backend.agent.deep_agents.schemas.persisted_status import PersistedStatusArtifact
from backend.app.config import Settings

DEFAULT_DEEP_RESEARCH_NAMESPACE = "deep_research"
PLAN_ARTIFACT_KEY = "plan.md"
SUBQUESTIONS_ARTIFACT_KEY = "subquestions.json"
STATUS_ARTIFACT_KEY = "status.json"
FINAL_ANSWER_ARTIFACT_KEY = "final_answer.md"


class HasRunId(Protocol):
    run_id: str


class HasRuntimeContext(Protocol):
    context: HasRunId


class HasBackendContext(Protocol):
    runtime: HasRuntimeContext


class DeepResearchArtifactRepository(Protocol):
    def write_plan(self, artifact: PersistedPlanArtifact) -> PersistedPlanArtifact: ...

    def read_plan(self, run_id: str) -> PersistedPlanArtifact | None: ...

    def write_subquestions(self, *, run_id: str, sub_questions: list[str]) -> dict[str, object]: ...

    def read_subquestions(self, run_id: str) -> list[str]: ...

    def write_status(self, artifact: PersistedStatusArtifact) -> PersistedStatusArtifact: ...

    def read_status(self, run_id: str) -> PersistedStatusArtifact | None: ...

    def write_final_answer(self, *, run_id: str, markdown: str) -> dict[str, str]: ...


def plan_artifact_path(run_id: str) -> str:
    return f"/runs/{run_id}/plan.md"


def subquestions_artifact_path(run_id: str) -> str:
    return f"/runs/{run_id}/subquestions.json"


def status_artifact_path(run_id: str) -> str:
    return f"/runs/{run_id}/status.json"


def final_answer_artifact_path(run_id: str) -> str:
    return f"/runs/{run_id}/final_answer.md"


def artifact_namespace(run_id: str, *, namespace_root: str = DEFAULT_DEEP_RESEARCH_NAMESPACE) -> tuple[str, str]:
    return (namespace_root, run_id)


def namespace_from_backend_context(
    context: HasBackendContext,
    *,
    namespace_root: str = DEFAULT_DEEP_RESEARCH_NAMESPACE,
) -> tuple[str, str]:
    return artifact_namespace(context.runtime.context.run_id, namespace_root=namespace_root)


class PostgresArtifactRepository:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        namespace_root: str = DEFAULT_DEEP_RESEARCH_NAMESPACE,
    ) -> None:
        self._settings = settings
        self._namespace_root = namespace_root

    def write_plan(self, artifact: PersistedPlanArtifact) -> PersistedPlanArtifact:
        return asyncio.run(self._write_plan(artifact))

    async def _write_plan(self, artifact: PersistedPlanArtifact) -> PersistedPlanArtifact:
        async with create_deep_research_store(settings=self._settings) as store:
            await store.aput(
                artifact_namespace(artifact.run_id, namespace_root=self._namespace_root),
                PLAN_ARTIFACT_KEY,
                artifact.model_dump(mode="json"),
            )
        return artifact

    def read_plan(self, run_id: str) -> PersistedPlanArtifact | None:
        return asyncio.run(self._read_plan(run_id))

    async def _read_plan(self, run_id: str) -> PersistedPlanArtifact | None:
        async with create_deep_research_store(settings=self._settings) as store:
            item = await store.aget(
                artifact_namespace(run_id, namespace_root=self._namespace_root),
                PLAN_ARTIFACT_KEY,
            )
        if item is None:
            return None
        return PersistedPlanArtifact.model_validate(getattr(item, "value", item))

    def write_subquestions(self, *, run_id: str, sub_questions: list[str]) -> dict[str, object]:
        return asyncio.run(self._write_subquestions(run_id=run_id, sub_questions=sub_questions))

    async def _write_subquestions(
        self,
        *,
        run_id: str,
        sub_questions: list[str],
    ) -> dict[str, object]:
        payload = {
            "run_id": run_id,
            "sub_questions": list(sub_questions),
            "artifact_path": subquestions_artifact_path(run_id),
        }
        async with create_deep_research_store(settings=self._settings) as store:
            await store.aput(
                artifact_namespace(run_id, namespace_root=self._namespace_root),
                SUBQUESTIONS_ARTIFACT_KEY,
                payload,
            )
        return payload

    def read_subquestions(self, run_id: str) -> list[str]:
        return asyncio.run(self._read_subquestions(run_id))

    async def _read_subquestions(self, run_id: str) -> list[str]:
        async with create_deep_research_store(settings=self._settings) as store:
            item = await store.aget(
                artifact_namespace(run_id, namespace_root=self._namespace_root),
                SUBQUESTIONS_ARTIFACT_KEY,
            )
        if item is None:
            return []
        payload = getattr(item, "value", item)
        return list(payload.get("sub_questions", []))

    def write_status(self, artifact: PersistedStatusArtifact) -> PersistedStatusArtifact:
        return asyncio.run(self._write_status(artifact))

    async def _write_status(self, artifact: PersistedStatusArtifact) -> PersistedStatusArtifact:
        async with create_deep_research_store(settings=self._settings) as store:
            await store.aput(
                artifact_namespace(artifact.run_id, namespace_root=self._namespace_root),
                STATUS_ARTIFACT_KEY,
                artifact.model_dump(mode="json"),
            )
        return artifact

    def read_status(self, run_id: str) -> PersistedStatusArtifact | None:
        return asyncio.run(self._read_status(run_id))

    async def _read_status(self, run_id: str) -> PersistedStatusArtifact | None:
        async with create_deep_research_store(settings=self._settings) as store:
            item = await store.aget(
                artifact_namespace(run_id, namespace_root=self._namespace_root),
                STATUS_ARTIFACT_KEY,
            )
        if item is None:
            return None
        return PersistedStatusArtifact.model_validate(getattr(item, "value", item))

    def write_final_answer(self, *, run_id: str, markdown: str) -> dict[str, str]:
        return asyncio.run(self._write_final_answer(run_id=run_id, markdown=markdown))

    async def _write_final_answer(self, *, run_id: str, markdown: str) -> dict[str, str]:
        payload = {
            "run_id": run_id,
            "markdown": markdown,
            "artifact_path": final_answer_artifact_path(run_id),
        }
        async with create_deep_research_store(settings=self._settings) as store:
            await store.aput(
                artifact_namespace(run_id, namespace_root=self._namespace_root),
                FINAL_ANSWER_ARTIFACT_KEY,
                payload,
            )
        return payload
