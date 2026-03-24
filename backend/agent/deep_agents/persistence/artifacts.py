from __future__ import annotations

from typing import Protocol

DEFAULT_DEEP_RESEARCH_NAMESPACE = "deep_research"


class HasRunId(Protocol):
    run_id: str


class HasRuntimeContext(Protocol):
    context: HasRunId


class HasBackendContext(Protocol):
    runtime: HasRuntimeContext


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
