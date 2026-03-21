from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from backend.agent.prompts import build_system_prompt
from backend.agent.runtime import (
    CANONICAL_TOOL_NAMES,
    DEFAULT_RECURSION_LIMIT,
    RUNTIME_PROFILES,
    RuntimeDependencies,
    _assert_canonical_tool_names,
    _get_tools_for_profile,
    get_runtime_profile,
    run_agent_once,
)
from backend.agent.types import AgentRunMode, AgentRunResult, AgentRuntimeProfile
from backend.app.tools.web_crawl import web_crawl
from backend.app.tools.web_search import web_search


def expected_runtime_config(mode: AgentRunMode = "agentic") -> dict[str, Any]:
    profile = get_runtime_profile(mode)
    return {
        "recursion_limit": profile.recursion_limit,
        "run_mode": profile.name,
        "execution_mode": profile.execution_mode,
        "timeout_seconds": profile.timeout_seconds,
        "model": profile.model,
        "tool_limits": {
            "max_tool_steps": profile.max_tool_steps,
            "max_search_results": profile.max_search_results,
            "max_crawl_chars": profile.max_crawl_chars,
        },
    }


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


@dataclass
class CapturingAgentFactory:
    raw_result: dict[str, Any]
    captured_profile: AgentRuntimeProfile | None = None
    captured_tools: tuple[Any, ...] | None = None
    agent: StubAgent | None = None

    def __call__(self, profile: AgentRuntimeProfile, tools: tuple[Any, ...]) -> StubAgent:
        self.captured_profile = profile
        self.captured_tools = tools
        self.agent = StubAgent(raw_result=self.raw_result)
        return self.agent


class GraphRecursionError(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass


class ProviderAPIError(RuntimeError):
    pass


@dataclass
class StubQuickSearchRunner:
    payload: dict[str, Any]
    captured_query: str | None = None
    captured_max_results: int | None = None

    def __call__(self, *, query: str, max_results: int = 5) -> dict[str, Any]:
        self.captured_query = query
        self.captured_max_results = max_results
        return self.payload


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
    assert agent.captured_config == expected_runtime_config()
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
    assert agent.captured_config == expected_runtime_config()


def test_run_agent_once_passes_selected_mode_into_runtime_config_for_agentic_modes() -> None:
    agent = StubAgent(raw_result={"output": "Fast answer."})

    result = run_agent_once(
        "find one source and summarize",
        "agentic",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert agent.captured_config == expected_runtime_config("agentic")


def test_agentic_profile_uses_bounded_profile_tools() -> None:
    profile = get_runtime_profile("agentic")

    search_tool, crawl_tool = _get_tools_for_profile(profile)

    assert (search_tool.name, crawl_tool.name) == CANONICAL_TOOL_NAMES
    assert search_tool is not web_search
    assert crawl_tool is not web_crawl


def test_agentic_prompt_includes_bounded_search_and_crawl_guidance() -> None:
    profile = get_runtime_profile("agentic")
    prompt = build_system_prompt(profile)

    assert "bounded multi-step reasoning" in prompt
    assert f"at most {profile.max_tool_steps} tool calls total" in prompt
    assert f"no more than {profile.max_search_results} results per call" in prompt
    assert str(profile.max_crawl_chars) in prompt


def test_run_agent_once_uses_single_search_path_for_quick_mode() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "latest agent news",
            "results": [
                {
                    "title": "Example One",
                    "url": "https://example.com/one",
                    "snippet": "First summary",
                    "rank": {"position": 1, "provider_position": 1},
                },
                {
                    "title": "Example Two",
                    "url": "https://example.com/two",
                    "snippet": "Second summary",
                    "rank": {"position": 2, "provider_position": 2},
                },
            ],
            "metadata": {"result_count": 2, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    agent = RaisingStubAgent(RuntimeError("quick mode should not invoke the agent"))

    result = run_agent_once(
        "latest agent news",
        "quick",
        runtime_dependencies=RuntimeDependencies(
            agent=agent,
            quick_search_runner=search_runner,
        ),
    )

    assert result.status == "completed"
    assert result.tool_call_count == 1
    assert "Example One: First summary." in result.final_answer
    assert "Sources:" in result.final_answer
    assert "https://example.com/one" in result.final_answer
    assert search_runner.captured_query == "latest agent news"
    assert search_runner.captured_max_results == 5
    assert agent.captured_inputs is None


def test_run_agent_once_maps_quick_search_provider_failures() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "error": {
                "kind": "provider_unavailable",
                "message": "Temporary upstream failure",
                "retryable": True,
                "status_code": 503,
                "attempt_number": 3,
                "operation": "web_search",
                "timings": {"total_ms": 120, "provider_ms": 100},
            },
            "meta": {
                "operation": "web_search",
                "attempts": 3,
                "retries": 2,
                "duration_ms": 120,
                "timings": {"total_ms": 120, "provider_ms": 100},
            },
        }
    )

    result = run_agent_once(
        "latest agent news",
        "quick",
        runtime_dependencies=RuntimeDependencies(quick_search_runner=search_runner),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "provider_failure"
    assert result.error.message == "quick search provider request failed"
    assert result.error.retryable is True


def test_run_agent_once_rejects_invalid_quick_search_payloads() -> None:
    search_runner = StubQuickSearchRunner(payload={"query": "agents", "results": "bad-payload"})

    result = run_agent_once(
        "latest agent news",
        "quick",
        runtime_dependencies=RuntimeDependencies(quick_search_runner=search_runner),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "tool_failure"
    assert result.error.message == "quick search returned invalid payload"
    assert result.error.retryable is False


@pytest.mark.parametrize(
    (
        "mode",
        "expected_model",
        "expected_recursion_limit",
        "expected_timeout",
        "expected_execution_mode",
        "expected_tool_steps",
        "expected_search_results",
        "expected_crawl_chars",
    ),
    [
        ("quick", "gpt-4.1-mini", 4, 20, "single_pass", 1, 5, 0),
        ("agentic", "gpt-4.1-mini", DEFAULT_RECURSION_LIMIT, 45, "bounded_agent_loop", 6, 4, 4000),
        ("deep_research", "gpt-4.1", 24, 180, "background_research", 16, 8, 12000),
    ],
)
def test_get_runtime_profile_exposes_distinct_policy_per_mode(
    mode: AgentRunMode,
    expected_model: str,
    expected_recursion_limit: int,
    expected_timeout: int,
    expected_execution_mode: str,
    expected_tool_steps: int,
    expected_search_results: int,
    expected_crawl_chars: int,
) -> None:
    profile = get_runtime_profile(mode)

    assert profile == RUNTIME_PROFILES[mode]
    assert profile.model == expected_model
    assert profile.recursion_limit == expected_recursion_limit
    assert profile.timeout_seconds == expected_timeout
    assert profile.execution_mode == expected_execution_mode
    assert profile.max_tool_steps == expected_tool_steps
    assert profile.max_search_results == expected_search_results
    assert profile.max_crawl_chars == expected_crawl_chars


def test_run_agent_once_uses_profile_driven_agent_factory() -> None:
    factory = CapturingAgentFactory(raw_result={"output": "Research answer."})

    result = run_agent_once(
        "investigate a topic",
        "deep_research",
        runtime_dependencies=RuntimeDependencies(agent_factory=factory),
    )

    assert result.status == "completed"
    assert factory.captured_profile == get_runtime_profile("deep_research")
    assert factory.captured_tools is not None
    assert tuple(tool.name for tool in factory.captured_tools) == CANONICAL_TOOL_NAMES
    assert factory.captured_tools != (web_search, web_crawl)
    assert factory.agent is not None
    assert factory.agent.captured_config == expected_runtime_config("deep_research")


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
