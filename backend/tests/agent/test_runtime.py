from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from backend.agent.runtime import (
    CANONICAL_TOOL_NAMES,
    DEFAULT_RECURSION_LIMIT,
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
    captured_config: dict[str, Any] | None = None

    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.captured_inputs = inputs
        self.captured_config = config
        return self.raw_result


@dataclass
class RaisingStubAgent:
    exc: Exception
    captured_inputs: dict[str, Any] | None = None
    captured_config: dict[str, Any] | None = None

    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.captured_inputs = inputs
        self.captured_config = config
        raise self.exc


class GraphRecursionError(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass


class ProviderAPIError(RuntimeError):
    pass


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
    assert agent.captured_config == {"recursion_limit": DEFAULT_RECURSION_LIMIT}
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


def test_run_agent_once_rejects_empty_prompt() -> None:
    result = run_agent_once("   ")

    assert result.status == "failed"
    assert result.final_answer == ""
    assert result.error is not None
    assert result.error.category == "invalid_prompt"
    assert result.error.retryable is False


def test_run_agent_once_maps_recursion_limit_failures() -> None:
    agent = RaisingStubAgent(GraphRecursionError("GRAPH_RECURSION_LIMIT reached"))

    result = run_agent_once(
        "keep searching forever",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "loop_limit"
    assert result.error.message == "agent exceeded bounded execution limit"
    assert result.error.retryable is False
    assert agent.captured_config == {"recursion_limit": DEFAULT_RECURSION_LIMIT}


def test_run_agent_once_maps_tool_failures() -> None:
    agent = RaisingStubAgent(ToolExecutionError("tool web_search failed"))

    result = run_agent_once(
        "find one source and summarize",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "tool_failure"
    assert result.error.message == "agent tool invocation failed"
    assert result.error.retryable is False


def test_run_agent_once_maps_timeout_failures() -> None:
    agent = RaisingStubAgent(httpx.ReadTimeout("timed out"))

    result = run_agent_once(
        "find one source and summarize",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "timeout"
    assert result.error.message == "agent execution timed out"
    assert result.error.retryable is True


def test_run_agent_once_maps_provider_failures() -> None:
    agent = RaisingStubAgent(ProviderAPIError("provider request failed"))

    result = run_agent_once(
        "find one source and summarize",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "provider_failure"
    assert result.error.message == "agent provider request failed"
    assert result.error.retryable is True
