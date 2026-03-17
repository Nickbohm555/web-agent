from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from backend.agent.runtime import (
    CANONICAL_TOOL_NAMES,
    RuntimeDependencies,
    _assert_canonical_tool_names,
    run_agent_once,
)
from backend.agent.types import AgentRunResult
from backend.app.tools.web_crawl import web_crawl
from backend.app.tools.web_search import web_search


@dataclass
class StubAgent:
    raw_result: dict[str, Any]
    captured_inputs: dict[str, Any] | None = None

    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.captured_inputs = inputs
        return self.raw_result


def test_run_agent_once_returns_normalized_result_without_provider_payload_leakage() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {"role": "user", "content": "find one source and summarize"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"name": "web_search", "args": {"query": "agents"}},
                        {"name": "web_crawl", "args": {"url": "https://example.com"}},
                    ],
                },
                {
                    "role": "assistant",
                    "content": "Final answer with one source.",
                    "provider_payload": {"token_usage": {"total_tokens": 42}},
                },
            ],
            "provider_payload": {"model": "gpt-test"},
        }
    )

    result = run_agent_once(
        "find one source and summarize",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert isinstance(result, AgentRunResult)
    assert result.status == "completed"
    assert result.final_answer == "Final answer with one source."
    assert result.tool_call_count == 2
    assert result.elapsed_ms >= 0
    assert result.run_id
    assert agent.captured_inputs == {
        "messages": [{"role": "user", "content": "find one source and summarize"}]
    }
    assert "provider_payload" not in result.model_dump()


def test_canonical_tool_binding_matches_phase_two_tool_names() -> None:
    assert (web_search.name, web_crawl.name) == CANONICAL_TOOL_NAMES
    _assert_canonical_tool_names((web_search, web_crawl))


def test_canonical_tool_binding_rejects_name_drift() -> None:
    class RenamedTool:
        def __init__(self, name: str) -> None:
            self.name = name

    with pytest.raises(ValueError, match="Canonical tool binding mismatch"):
        _assert_canonical_tool_names((RenamedTool("search_web"), RenamedTool("web_crawl")))
