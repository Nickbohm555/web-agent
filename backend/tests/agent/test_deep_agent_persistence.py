from __future__ import annotations

from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

from backend.agent.deep_agents.persistence.artifacts import (
    final_answer_artifact_path,
    plan_artifact_path,
    status_artifact_path,
    subquestions_artifact_path,
)
from backend.agent.deep_agents.persistence.backend_factory import build_deep_research_backend


def test_persistence_artifact_paths_use_run_scoped_layout() -> None:
    run_id = "run-persist-123"

    assert plan_artifact_path(run_id) == "/runs/run-persist-123/plan.md"
    assert subquestions_artifact_path(run_id) == "/runs/run-persist-123/subquestions.json"
    assert status_artifact_path(run_id) == "/runs/run-persist-123/status.json"
    assert final_answer_artifact_path(run_id) == "/runs/run-persist-123/final_answer.md"


def test_build_deep_research_backend_routes_runs_and_plans_into_store(fake_tool_runtime) -> None:
    backend = build_deep_research_backend(fake_tool_runtime)

    assert isinstance(backend, CompositeBackend)
    assert isinstance(backend.default, StateBackend)
    assert isinstance(backend.routes["/runs/"], StoreBackend)
    assert isinstance(backend.routes["/plans/"], StoreBackend)


def test_build_deep_research_backend_namespaces_by_run_id(fake_tool_runtime) -> None:
    backend = build_deep_research_backend(fake_tool_runtime)
    run_backend = backend.routes["/runs/"]
    plan_backend = backend.routes["/plans/"]
    backend_context = type(
        "BackendContext",
        (),
        {"runtime": fake_tool_runtime, "state": fake_tool_runtime.state},
    )()

    assert run_backend._namespace(backend_context) == ("deep_research", "run-test-123")
    assert plan_backend._namespace(backend_context) == ("deep_research", "run-test-123")
