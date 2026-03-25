from __future__ import annotations

from typing import Any

import pytest

from backend.agent.deep_research_subagents import build_research_subagent
from backend.agent.deep_research_supervisor import build_deep_research_supervisor


def test_deepagents_compatibility_gate_requires_create_deep_agent() -> None:
    deepagents = pytest.importorskip("deepagents")

    assert hasattr(
        deepagents,
        "create_deep_agent",
    ), "deepagents create_deep_agent API is required for Phase 4"


def test_retrieval_subagent_exposes_canonical_tools() -> None:
    spec = build_research_subagent()

    assert spec["name"] == "research_subagent"
    assert sorted(tool.name for tool in spec["tools"]) == ["open_url", "web_search"]


def test_fanout_supervisor_builds_deep_agent_for_plan_subquestions() -> None:
    recorded_calls: list[dict[str, Any]] = []

    def fake_create_agent(**kwargs: Any) -> dict[str, Any]:
        recorded_calls.append(kwargs)
        return {"kind": "deep-agent", "subagents": kwargs["subagents"]}

    subquestions = [
        "What changed in the product roadmap?",
        "Which launch constraints are called out publicly?",
    ]

    supervisor = build_deep_research_supervisor(
        create_agent=fake_create_agent,
        plan_subquestions=subquestions,
    )

    assert supervisor["kind"] == "deep-agent"
    assert len(recorded_calls) == 1
    assert "metadata" not in recorded_calls[0]
    assert recorded_calls[0]["name"] == "deep_research_supervisor"
    assert len(recorded_calls[0]["subagents"]) == 1
    assert recorded_calls[0]["subagents"][0]["name"] == "research_subagent"
