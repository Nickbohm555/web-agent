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
from backend.agent.types import AgentRunRetrievalPolicy
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
        "retrieval_policy": AgentRunRetrievalPolicy().model_dump(),
    }


def expected_runtime_config_with_policy(
    retrieval_policy: AgentRunRetrievalPolicy,
    mode: AgentRunMode = "agentic",
) -> dict[str, Any]:
    config = expected_runtime_config(mode)
    config["retrieval_policy"] = retrieval_policy.model_dump()
    return config


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
    captured_retrieval_policy: AgentRunRetrievalPolicy | None = None
    captured_system_prompt: str | None = None
    agent: StubAgent | None = None

    def __call__(
        self,
        profile: AgentRuntimeProfile,
        tools: tuple[Any, ...],
        retrieval_policy: AgentRunRetrievalPolicy,
        system_prompt: str,
    ) -> StubAgent:
        self.captured_profile = profile
        self.captured_tools = tools
        self.captured_retrieval_policy = retrieval_policy
        self.captured_system_prompt = system_prompt
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
    captured_freshness: str | None = None
    captured_include_domains: list[str] | None = None
    captured_exclude_domains: list[str] | None = None

    def __call__(
        self,
        *,
        query: str,
        max_results: int = 5,
        freshness: str = "any",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        self.captured_query = query
        self.captured_max_results = max_results
        self.captured_freshness = freshness
        self.captured_include_domains = include_domains
        self.captured_exclude_domains = exclude_domains
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
                    "citations": [
                        {
                            "source_id": "https-example-com-source",
                            "start_index": 0,
                            "end_index": 12,
                        }
                    ],
                    "sources": [
                        {
                            "title": "Example source",
                            "url": "https://example.com/source",
                            "snippet": "Evidence snippet.",
                        }
                    ],
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
    assert result.final_answer is not None
    assert result.final_answer.text == "Final answer with one source."
    assert result.final_answer.model_dump(mode="json")["citations"] == [
        {
            "source_id": "https-example-com-source",
            "title": "Example source",
            "url": "https://example.com/source",
            "start_index": 0,
            "end_index": 12,
        }
    ]
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-source",
            "title": "Example source",
            "url": "https://example.com/source",
            "snippet": "Evidence snippet.",
        }
    ]
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
    assert result.final_answer is None
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
    assert "Use web_search to shortlist likely-answering sources before crawling" in prompt
    assert "always include an objective" in prompt


def test_system_prompt_includes_effective_retrieval_policy_details() -> None:
    profile = get_runtime_profile("agentic")
    prompt = build_system_prompt(
        profile,
        AgentRunRetrievalPolicy.model_validate(
            {
                "search": {
                    "freshness": "week",
                    "include_domains": ["openai.com"],
                },
                "fetch": {
                    "max_age_ms": 21_600_000,
                    "fresh": True,
                },
            }
        ),
    )

    assert "Translate clear prompt intent like official-docs-only" in prompt
    assert "freshness=week" in prompt
    assert "include domains=['openai.com']" in prompt
    assert "fetch fresh=True" in prompt
    assert "fetch max_age_ms=21600000" in prompt


def test_system_prompt_accepts_prompt_specific_retrieval_brief() -> None:
    profile = get_runtime_profile("deep_research")
    prompt = build_system_prompt(
        profile,
        retrieval_brief=(
            "Retrieval strategy:\n"
            "- Answer objective: Compare two API launches\n"
            "- Crawl plan: every web_crawl call must include an objective"
        ),
    )

    assert "Retrieval strategy:" in prompt
    assert "Compare two API launches" in prompt
    assert "every web_crawl call must include an objective" in prompt


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
    assert result.final_answer is not None
    assert "Example One: First summary." in result.final_answer.text
    assert "Sources:" in result.final_answer.text
    assert "https://example.com/one" in result.final_answer.text
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-one",
            "title": "Example One",
            "url": "https://example.com/one",
            "snippet": "First summary",
        },
        {
            "source_id": "https-example-com-two",
            "title": "Example Two",
            "url": "https://example.com/two",
            "snippet": "Second summary",
        },
    ]
    assert search_runner.captured_query == "latest agent news"
    assert search_runner.captured_max_results == 5
    assert search_runner.captured_freshness == "week"
    assert search_runner.captured_include_domains == []
    assert search_runner.captured_exclude_domains == []
    assert agent.captured_inputs is None


def test_run_agent_once_threads_retrieval_policy_into_runtime_and_quick_search() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "latest agent news",
            "results": [],
            "metadata": {"result_count": 0, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    retrieval_policy = AgentRunRetrievalPolicy.model_validate(
        {
            "search": {
                "freshness": "week",
                "include_domains": ["example.com"],
                "exclude_domains": ["blocked.com"],
            },
        }
    )

    result = run_agent_once(
        "latest agent news",
        "quick",
        retrieval_policy,
        runtime_dependencies=RuntimeDependencies(quick_search_runner=search_runner),
    )

    assert result.status == "completed"
    assert search_runner.captured_freshness == "week"
    assert search_runner.captured_include_domains == ["example.com"]
    assert search_runner.captured_exclude_domains == ["blocked.com"]


def test_run_agent_once_infers_retrieval_policy_from_prompt_intent() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "Responses API update",
            "results": [],
            "metadata": {"result_count": 0, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )

    result = run_agent_once(
        "Use official docs only to find the latest OpenAI Responses API update.",
        "quick",
        runtime_dependencies=RuntimeDependencies(quick_search_runner=search_runner),
    )

    assert result.status == "completed"
    assert search_runner.captured_freshness == "week"
    assert search_runner.captured_include_domains == ["openai.com"]
    assert search_runner.captured_exclude_domains == []


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
    assert factory.captured_retrieval_policy == AgentRunRetrievalPolicy()
    assert factory.captured_system_prompt is not None
    assert "Retrieval strategy:" in factory.captured_system_prompt
    assert "Answer objective: investigate a topic" in factory.captured_system_prompt
    assert "every web_crawl call must include an objective" in factory.captured_system_prompt
    assert factory.agent is not None
    assert factory.agent.captured_config == expected_runtime_config("deep_research")


def test_run_agent_once_passes_inferred_retrieval_policy_into_agent_factory_and_config() -> None:
    factory = CapturingAgentFactory(raw_result={"output": "Research answer."})
    expected_policy = AgentRunRetrievalPolicy.model_validate(
        {
            "search": {
                "freshness": "week",
                "include_domains": ["openai.com"],
            },
            "fetch": {
                "max_age_ms": 21_600_000,
                "fresh": True,
            },
        }
    )

    result = run_agent_once(
        "Use official docs only to find the latest OpenAI Responses API update.",
        "agentic",
        runtime_dependencies=RuntimeDependencies(agent_factory=factory),
    )

    assert result.status == "completed"
    assert factory.captured_retrieval_policy == expected_policy
    assert factory.captured_system_prompt is not None
    assert "stay within openai.com" in factory.captured_system_prompt
    assert "prefer week-fresh sources" in factory.captured_system_prompt
    assert (
        "Answer objective: Use official docs only to find the latest OpenAI Responses API update."
        in factory.captured_system_prompt
    )
    assert factory.agent is not None
    assert factory.agent.captured_config == expected_runtime_config_with_policy(
        expected_policy,
        "agentic",
    )


def test_run_agent_once_preserves_explicit_structured_final_answer_citations() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Structured answer with two cited spans.",
                "citations": [
                    {
                        "url": "https://example.com/b",
                        "title": "Source B",
                        "start_index": 22,
                        "end_index": 31,
                    },
                    {
                        "source_id": "https-example-com-a",
                        "start_index": 0,
                        "end_index": 10,
                    },
                ],
            },
            "sources": [
                {
                    "source_id": "https-example-com-a",
                    "title": "Source A",
                    "url": "https://example.com/a",
                    "snippet": "A snippet.",
                },
                {
                    "title": "Source B",
                    "url": "https://example.com/b",
                    "snippet": "B snippet.",
                },
            ],
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert result.final_answer is not None
    assert result.final_answer.model_dump(mode="json") == {
        "text": "Structured answer with two cited spans.",
        "citations": [
            {
                "source_id": "https-example-com-a",
                "title": "Source A",
                "url": "https://example.com/a",
                "start_index": 0,
                "end_index": 10,
            },
            {
                "source_id": "https-example-com-b",
                "title": "Source B",
                "url": "https://example.com/b",
                "start_index": 22,
                "end_index": 31,
            },
        ],
    }


def test_run_agent_once_rejects_citations_that_bypass_safe_source_registry() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Unsafe citation answer",
                "citations": [
                    {
                        "title": "Unsafe Source",
                        "url": "javascript:alert(1)",
                        "start_index": 0,
                        "end_index": 6,
                    }
                ],
            },
            "sources": [
                {
                    "title": "Unsafe Source",
                    "url": "javascript:alert(1)",
                    "snippet": "Should never become clickable.",
                }
            ],
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "invalid_prompt"
    assert result.error.message == "citation must reference a policy-cleared source"


def test_run_agent_once_assembles_consulted_sources_from_search_and_crawl_messages() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "web_search",
                    "content": {
                        "query": "example topic",
                        "results": [
                            {
                                "title": "Example source",
                                "url": "https://example.com/start",
                                "snippet": "Search snippet.",
                                "rank": {"position": 1, "provider_position": 1},
                            },
                            {
                                "title": "Other source",
                                "url": "https://example.com/other",
                                "snippet": "Other snippet.",
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
                    },
                },
                {
                    "role": "tool",
                    "name": "web_crawl",
                    "content": {
                        "url": "https://example.com/start",
                        "final_url": "https://example.com/final",
                        "text": "Expanded crawl content from the final page.",
                        "markdown": "Expanded crawl content from the final page.",
                        "status_code": 200,
                        "content_type": "text/html",
                        "fallback_reason": None,
                        "meta": {
                            "operation": "web_crawl",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 20,
                            "timings": {"total_ms": 20},
                        },
                    },
                },
                {
                    "role": "assistant",
                    "final_answer": {
                        "text": "Example final answer",
                        "citations": [
                            {
                                "url": "https://example.com/start",
                                "start_index": 0,
                                "end_index": 7,
                            }
                        ],
                    },
                },
            ]
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert result.final_answer is not None
    assert result.final_answer.model_dump(mode="json")["citations"] == [
        {
            "source_id": "https-example-com-final",
            "title": "Example source",
            "url": "https://example.com/final",
            "start_index": 0,
            "end_index": 7,
        }
    ]
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-final",
            "title": "Example source",
            "url": "https://example.com/final",
            "snippet": "Expanded crawl content from the final page.",
        },
        {
            "source_id": "https-example-com-other",
            "title": "Other source",
            "url": "https://example.com/other",
            "snippet": "Other snippet.",
        },
    ]


def test_run_agent_once_normalizes_safe_source_urls_before_emitting_citations() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Normalized citation",
                "citations": [
                    {
                        "url": "https://Example.com/report#section-1",
                        "start_index": 0,
                        "end_index": 10,
                    }
                ],
            },
            "sources": [
                {
                    "title": "Example Report",
                    "url": "https://Example.com/report#section-1",
                    "snippet": "Normalized snippet.",
                }
            ],
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert result.final_answer is not None
    assert result.final_answer.model_dump(mode="json")["citations"] == [
        {
            "source_id": "https-example-com-report",
            "title": "Example Report",
            "url": "https://example.com/report",
            "start_index": 0,
            "end_index": 10,
        }
    ]
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-report",
            "title": "Example Report",
            "url": "https://example.com/report",
            "snippet": "Normalized snippet.",
        }
    ]


def test_run_agent_once_parses_json_encoded_tool_payloads_into_source_registry() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "web_search",
                    "content": '{"query":"example topic","results":[{"title":"Example source","url":"https://example.com/a","snippet":"Snippet A","rank":{"position":1,"provider_position":1}}],"metadata":{"result_count":1,"provider":"serper"},"meta":{"operation":"web_search","attempts":1,"retries":0,"duration_ms":12,"timings":{"total_ms":12}}}',
                },
                {"role": "assistant", "content": "Answer."},
            ]
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-a",
            "title": "Example source",
            "url": "https://example.com/a",
            "snippet": "Snippet A",
        }
    ]


def test_run_agent_once_rejects_overlapping_citation_spans() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Overlapping citation spans",
                "citations": [
                    {
                        "title": "Source A",
                        "url": "https://example.com/a",
                        "start_index": 0,
                        "end_index": 11,
                    },
                    {
                        "title": "Source B",
                        "url": "https://example.com/b",
                        "start_index": 5,
                        "end_index": 14,
                    },
                ],
            }
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "invalid_prompt"
    assert result.error.message == "citation spans must not overlap"


def test_run_agent_once_rejects_out_of_bounds_citation_spans() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Short answer",
                "citations": [
                    {
                        "title": "Source A",
                        "url": "https://example.com/a",
                        "start_index": 0,
                        "end_index": 50,
                    }
                ],
            }
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "invalid_prompt"
    assert result.error.message == "citation end_index must not exceed answer text length"


@pytest.mark.parametrize("mode", ["quick", "agentic", "deep_research"])
def test_run_agent_once_has_a_happy_path_for_each_mode(mode: AgentRunMode) -> None:
    if mode == "quick":
        result = run_agent_once(
            "latest agent news",
            mode,
            runtime_dependencies=RuntimeDependencies(
                quick_search_runner=StubQuickSearchRunner(
                    payload={
                        "query": "latest agent news",
                        "results": [
                            {
                                "title": "Example One",
                                "url": "https://example.com/one",
                                "snippet": "First summary",
                                "rank": {"position": 1, "provider_position": 1},
                            }
                        ],
                        "metadata": {"result_count": 1, "provider": "serper"},
                        "meta": {
                            "operation": "web_search",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 12,
                            "timings": {"total_ms": 12, "provider_ms": 8},
                        },
                    }
                )
            ),
        )
        assert result.status == "completed"
        assert result.tool_call_count == 1
        assert str(result.sources[0].url) == "https://example.com/one"
        return

    agent = StubAgent(
        raw_result={
            "messages": [
                {"role": "assistant", "content": f"{mode} answer."},
            ]
        }
    )
    result = run_agent_once(
        f"investigate {mode}",
        mode,
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert result.final_answer is not None
    assert result.final_answer.text == f"{mode} answer."
    assert agent.captured_config == expected_runtime_config(mode)


@pytest.mark.parametrize("mode", ["quick", "agentic", "deep_research"])
def test_run_agent_once_has_a_failure_path_for_each_mode(mode: AgentRunMode) -> None:
    if mode == "quick":
        result = run_agent_once(
            "latest agent news",
            mode,
            runtime_dependencies=RuntimeDependencies(
                quick_search_runner=StubQuickSearchRunner(
                    payload={
                        "error": {
                            "kind": "provider_unavailable",
                            "message": "Temporary upstream failure",
                            "retryable": True,
                            "status_code": 503,
                            "attempt_number": 1,
                            "operation": "web_search",
                            "timings": {"total_ms": 120, "provider_ms": 100},
                        },
                        "meta": {
                            "operation": "web_search",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 120,
                            "timings": {"total_ms": 120, "provider_ms": 100},
                        },
                    }
                )
            ),
        )
        assert result.status == "failed"
        assert result.error is not None
        assert result.error.category == "provider_failure"
        return

    agent = RaisingStubAgent(GraphRecursionError("GRAPH_RECURSION_LIMIT reached"))
    result = run_agent_once(
        f"break {mode}",
        mode,
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "loop_limit"
    assert agent.captured_config == expected_runtime_config(mode)


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
