from __future__ import annotations

from contextlib import contextmanager
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
from backend.agent.runtime_sources import extract_sources
from backend.agent.schemas import AgentRunMode, AgentRunResult, AgentRuntimeProfile
from backend.app.tools.open_url import open_url
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


def expected_threaded_runtime_config(
    mode: AgentRunMode,
    thread_id: str,
) -> dict[str, Any]:
    config = expected_runtime_config(mode)
    config["configurable"] = {"thread_id": thread_id}
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
    captured_system_prompt: str | None = None
    captured_checkpointer: object | None = None
    agent: StubAgent | None = None

    def __call__(
        self,
        profile: AgentRuntimeProfile,
        tools: tuple[Any, ...],
        system_prompt: str,
        *,
        checkpointer: object | None = None,
    ) -> StubAgent:
        self.captured_profile = profile
        self.captured_tools = tools
        self.captured_system_prompt = system_prompt
        self.captured_checkpointer = checkpointer
        self.agent = StubAgent(raw_result=self.raw_result)
        return self.agent


@dataclass
class RecordingCheckpointerContextFactory:
    checkpointer: object
    enters: int = 0
    exits: int = 0

    def __call__(self):
        @contextmanager
        def manager():
            self.enters += 1
            try:
                yield self.checkpointer
            finally:
                self.exits += 1

        return manager()


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

    def __call__(
        self,
        *,
        query: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        self.captured_query = query
        self.captured_max_results = max_results
        return self.payload


@dataclass
class StubQuickCrawlRunner:
    payloads_by_url: dict[str, Any]
    requested_urls: list[str] | None = None

    def __call__(self, *, url: str) -> dict[str, Any]:
        if self.requested_urls is None:
            self.requested_urls = []
        self.requested_urls.append(url)
        return self.payloads_by_url[url]


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
                        {"name": "open_url", "args": {"url": "https://example.com"}},
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


def test_run_agent_once_routes_quick_mode_into_quick_runtime() -> None:
    quick_result = AgentRunResult(
        run_id="run-quick",
        status="completed",
        final_answer={"text": "Quick answer"},
        sources=[],
        tool_call_count=4,
        elapsed_ms=12,
    )
    deps = RuntimeDependencies(
        quick_runtime_runner=lambda **_: quick_result,
        agent=RaisingStubAgent(RuntimeError("agent path should not run")),
    )

    result = run_agent_once("Find pricing", "quick", runtime_dependencies=deps)

    assert result.run_id == "run-quick"


def test_run_agent_once_routes_background_deep_research_mode_into_background_runtime() -> None:
    deep_result = AgentRunResult(
        run_id="run-deep",
        status="completed",
        final_answer={"text": "Deep answer"},
        sources=[],
        tool_call_count=8,
        elapsed_ms=120,
    )
    deps = RuntimeDependencies(
        deep_research_runner=lambda **_: deep_result,
        agent=RaisingStubAgent(RuntimeError("agent path should not run")),
    )

    result = run_agent_once("Investigate deeply", "deep_research", runtime_dependencies=deps)

    assert result.run_id == "run-deep"


def test_agentic_mode_still_uses_agent_factory_and_profile_tool_limits() -> None:
    factory = CapturingAgentFactory(raw_result={"output": "Answer"})

    result = run_agent_once(
        "Compare two providers",
        "agentic",
        runtime_dependencies=RuntimeDependencies(agent_factory=factory),
    )

    assert result.status == "completed"
    assert factory.captured_profile == get_runtime_profile("agentic")
    assert factory.captured_tools is not None
    assert tuple(tool.name for tool in factory.captured_tools) == CANONICAL_TOOL_NAMES
    assert "bounded multi-step reasoning" in (factory.captured_system_prompt or "")


def test_deep_research_no_longer_reuses_agentic_prompt_appendix_only() -> None:
    prompt = build_system_prompt(
        profile=get_runtime_profile("deep_research"),
        retrieval_brief="...",
    )

    assert "Deep research guidance" in prompt
    assert "Work methodically" in prompt
    assert "bounded multi-step reasoning" not in prompt


def test_canonical_tool_binding_matches_phase_two_tool_names() -> None:
    assert (web_search.name, open_url.name) == CANONICAL_TOOL_NAMES
    _assert_canonical_tool_names((web_search, open_url))


def test_canonical_tool_binding_rejects_name_drift() -> None:
    class RenamedTool:
        def __init__(self, name: str) -> None:
            self.name = name

    with pytest.raises(ValueError, match="Canonical tool binding mismatch"):
        _assert_canonical_tool_names((RenamedTool("search_web"), RenamedTool("open_url")))


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
    assert crawl_tool is not open_url


def test_agentic_prompt_includes_bounded_search_and_crawl_guidance() -> None:
    profile = get_runtime_profile("agentic")
    prompt = build_system_prompt(profile)

    assert "bounded multi-step reasoning" in prompt
    assert f"at most {profile.max_tool_steps} tool calls total" in prompt
    assert f"no more than {profile.max_search_results} results per call" in prompt
    assert str(profile.max_crawl_chars) in prompt
    assert "Use web_search to shortlist likely-answering sources before crawling" in prompt
    assert "Treat search excerpts as a triage layer" in prompt


def test_system_prompt_instructs_agent_to_batch_selected_url_opens() -> None:
    prompt = build_system_prompt(profile=RUNTIME_PROFILES["agentic"])

    assert "call open_url with multiple selected URLs in one call" in prompt


def test_extract_sources_flattens_successful_batch_crawl_items() -> None:
    registry = extract_sources(
        {
            "messages": [
                {
                    "type": "tool",
                    "name": "open_url",
                    "payload": {
                        "requested_urls": [
                            "https://example.com/a",
                            "https://example.com/b",
                        ],
                        "items": [
                            {
                                "url": "https://example.com/a",
                                "status": "succeeded",
                                "result": {
                                    "url": "https://example.com/a",
                                    "final_url": "https://example.com/a",
                                    "text": "Alpha body text.",
                                    "markdown": "Alpha body text.",
                                    "excerpts": [],
                                    "status_code": 200,
                                    "content_type": "text/html",
                                    "fallback_reason": None,
                                    "meta": {
                                        "operation": "open_url",
                                        "attempts": 1,
                                        "retries": 0,
                                        "duration_ms": 10,
                                        "timings": {"total_ms": 10},
                                    },
                                },
                                "error": None,
                            },
                            {
                                "url": "https://example.com/b",
                                "status": "failed",
                                "result": None,
                                "error": {
                                    "kind": "invalid_request",
                                    "message": "blocked",
                                    "retryable": False,
                                    "status_code": None,
                                    "attempt_number": None,
                                    "operation": "open_url",
                                    "timings": {"total_ms": 1},
                                },
                            },
                        ],
                        "meta": {
                            "operation": "open_url",
                            "attempts": 2,
                            "retries": 0,
                            "duration_ms": 11,
                            "timings": {"total_ms": 11},
                        },
                        "summary": {"attempted": 2, "succeeded": 1, "failed": 1},
                    },
                }
            ]
        }
    )

    assert [str(source.url) for source in registry.sources()] == ["https://example.com/a"]


def test_system_prompt_includes_mode_guidance_and_tool_budget() -> None:
    profile = get_runtime_profile("agentic")
    prompt = build_system_prompt(profile)

    assert "Mode guidance:" in prompt
    assert "Tool budget:" in prompt


def test_system_prompt_accepts_prompt_specific_retrieval_brief() -> None:
    profile = get_runtime_profile("deep_research")
    prompt = build_system_prompt(
        profile,
        retrieval_brief=(
            "Retrieval strategy:\n"
            "- Answer objective: Compare two API launches\n"
            "- Crawl plan: crawl only high-value pages that look useful for the answer"
        ),
    )

    assert "Retrieval strategy:" in prompt
    assert "Compare two API launches" in prompt
    assert "crawl only high-value pages that look useful for the answer" in prompt


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
    crawl_runner = StubQuickCrawlRunner(
        payloads_by_url={
            "https://example.com/one": {
                "url": "https://example.com/one",
                "final_url": "https://example.com/one",
                "text": "Expanded summary one.",
                "markdown": "Expanded summary one.",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "open_url",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 20,
                    "timings": {"total_ms": 20},
                },
            },
            "https://example.com/two": {
                "url": "https://example.com/two",
                "final_url": "https://example.com/two",
                "text": "Expanded summary two.",
                "markdown": "Expanded summary two.",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "open_url",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 20,
                    "timings": {"total_ms": 20},
                },
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
            quick_crawl_runner=crawl_runner,
        ),
    )

    assert result.status == "completed"
    assert result.tool_call_count == 3
    assert result.final_answer is not None
    assert result.final_answer.text.startswith("Quick answer based on the top sources:\n")
    assert "- Example One: Expanded summary one" in result.final_answer.text
    assert "- Example Two: Expanded summary two" in result.final_answer.text
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-one",
            "title": "Example One",
            "url": "https://example.com/one",
            "snippet": "Expanded summary one.",
        },
        {
            "source_id": "https-example-com-two",
            "title": "Example Two",
            "url": "https://example.com/two",
            "snippet": "Expanded summary two.",
        },
    ]
    assert search_runner.captured_query == "latest agent news"
    assert search_runner.captured_max_results == 5
    assert crawl_runner.requested_urls == [
        "https://example.com/one",
        "https://example.com/two",
    ]
    assert agent.captured_inputs is None


def test_run_agent_once_preserves_prompt_text_for_quick_search() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "Responses API update",
            "results": [
                {
                    "title": "OpenAI Responses API",
                    "url": "https://openai.com/docs/responses",
                    "snippet": "Updated docs",
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
    crawl_runner = StubQuickCrawlRunner(
        payloads_by_url={
            "https://openai.com/docs/responses": {
                "url": "https://openai.com/docs/responses",
                "final_url": "https://openai.com/docs/responses",
                "text": "OpenAI responses docs",
                "markdown": "OpenAI responses docs",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "open_url",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 20,
                    "timings": {"total_ms": 20},
                },
            }
        }
    )

    result = run_agent_once(
        "Use official docs only to find the latest OpenAI Responses API update.",
        "quick",
        runtime_dependencies=RuntimeDependencies(
            quick_search_runner=search_runner,
            quick_crawl_runner=crawl_runner,
        ),
    )

    assert result.status == "completed"
    assert search_runner.captured_query == (
        "Use official docs only to find the latest OpenAI Responses API update."
    )
    assert crawl_runner.requested_urls == ["https://openai.com/docs/responses"]


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
        (
            "deep_research",
            "gpt-4.1",
            DEFAULT_RECURSION_LIMIT,
            180,
            "background_research",
            16,
            4,
            4000,
        ),
    ],
)
def test_get_runtime_profile_exposes_distinct_runtime_profile_per_mode(
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
    assert factory.captured_tools != (web_search, open_url)
    assert factory.captured_system_prompt is not None
    assert "Retrieval strategy:" in factory.captured_system_prompt
    assert "Answer objective: investigate a topic" in factory.captured_system_prompt
    assert "crawl only high-value pages that look useful for the answer" in factory.captured_system_prompt
    assert factory.agent is not None
    assert factory.agent.captured_config == expected_runtime_config("deep_research")


def test_run_agent_once_passes_runtime_config_into_agent_factory_and_config() -> None:
    factory = CapturingAgentFactory(raw_result={"output": "Research answer."})

    result = run_agent_once(
        "Use official docs only to find the latest OpenAI Responses API update.",
        "agentic",
        runtime_dependencies=RuntimeDependencies(agent_factory=factory),
    )

    assert result.status == "completed"
    assert factory.captured_system_prompt is not None
    assert (
        "Answer objective: Use official docs only to find the latest OpenAI Responses API update."
        in factory.captured_system_prompt
    )
    assert factory.agent is not None
    assert factory.agent.captured_config == expected_runtime_config("agentic")


def test_run_agent_once_uses_checkpointer_backed_agentic_thread_config() -> None:
    factory = CapturingAgentFactory(raw_result={"output": "Research answer."})
    checkpointer_factory = RecordingCheckpointerContextFactory(checkpointer=object())

    result = run_agent_once(
        "Continue the existing thread",
        "agentic",
        thread_id="thread-agentic-123",
        runtime_dependencies=RuntimeDependencies(
            agent_factory=factory,
            checkpointer_context_factory=checkpointer_factory,
        ),
    )

    assert result.status == "completed"
    assert factory.captured_checkpointer is checkpointer_factory.checkpointer
    assert factory.agent is not None
    assert factory.agent.captured_config == expected_threaded_runtime_config(
        "agentic",
        "thread-agentic-123",
    )
    assert checkpointer_factory.enters == 1
    assert checkpointer_factory.exits == 1


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
        "basis": [],
    }


def test_run_agent_once_preserves_granular_claim_basis_references() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Claim one. Claim two.",
                "citations": [
                    {
                        "source_id": "https-example-com-a",
                        "start_index": 0,
                        "end_index": 9,
                    },
                ],
                "basis": [
                    {
                        "kind": "claim",
                        "text": "Claim one.",
                        "citations": [
                            {
                                "source_id": "https-example-com-a",
                                "start_index": 0,
                                "end_index": 9,
                            }
                        ],
                    },
                    {
                        "kind": "list_item",
                        "text": "Claim two.",
                        "citations": [
                            {
                                "url": "https://example.com/b",
                                "title": "Source B",
                                "start_index": 0,
                                "end_index": 9,
                            }
                        ],
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
        "investigate claim basis",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "completed"
    assert result.final_answer is not None
    assert result.final_answer.model_dump(mode="json")["basis"] == [
        {
            "kind": "claim",
            "text": "Claim one.",
            "citations": [
                {
                    "source_id": "https-example-com-a",
                    "title": "Source A",
                    "url": "https://example.com/a",
                    "start_index": 0,
                    "end_index": 9,
                }
            ],
        },
        {
            "kind": "list_item",
            "text": "Claim two.",
            "citations": [
                {
                    "source_id": "https-example-com-b",
                    "title": "Source B",
                    "url": "https://example.com/b",
                    "start_index": 0,
                    "end_index": 9,
                }
            ],
        },
    ]


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


def test_run_agent_once_rejects_unsafe_granular_claim_basis_references() -> None:
    agent = StubAgent(
        raw_result={
            "final_answer": {
                "text": "Claim one.",
                "basis": [
                    {
                        "kind": "claim",
                        "text": "Claim one.",
                        "citations": [
                            {
                                "title": "Unsafe Source",
                                "url": "javascript:alert(1)",
                                "start_index": 0,
                                "end_index": 6,
                            }
                        ],
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
        "investigate claim basis",
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
                    "name": "open_url",
                    "content": {
                        "url": "https://example.com/start",
                        "final_url": "https://example.com/final",
                        "text": "Expanded crawl content from the final page.",
                        "markdown": "Expanded crawl content from the final page.",
                        "status_code": 200,
                        "content_type": "text/html",
                        "fallback_reason": None,
                        "meta": {
                            "operation": "open_url",
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


def test_run_agent_once_no_evidence_crawl_success_does_not_register_source() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "url": "https://example.com/thin",
                        "final_url": "https://example.com/thin",
                        "text": "",
                        "markdown": "",
                        "excerpts": [],
                        "status_code": 200,
                        "content_type": "text/html",
                        "fallback_reason": "low-content-quality",
                        "meta": {
                            "operation": "open_url",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 20,
                            "timings": {"total_ms": 20},
                        },
                    },
                },
                {
                    "role": "assistant",
                    "content": "No evidence answer.",
                },
            ]
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.final_answer is None
    assert result.sources == []
    assert result.error is not None
    assert result.error.category == "tool_failure"
    assert result.error.message == "agent crawl returned no evidence"


def test_run_agent_once_preserves_retryable_crawl_error_without_sources() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "error": {
                            "kind": "provider_unavailable",
                            "message": "upstream unavailable",
                            "retryable": True,
                            "status_code": 503,
                            "attempt_number": 2,
                            "operation": "open_url",
                            "timings": {"total_ms": 120, "provider_ms": 90},
                        },
                        "meta": {
                            "operation": "open_url",
                            "attempts": 2,
                            "retries": 1,
                            "duration_ms": 120,
                            "timings": {"total_ms": 120, "provider_ms": 90},
                        },
                    },
                },
                {
                    "role": "assistant",
                    "content": "Fallback answer.",
                },
            ]
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.final_answer is None
    assert result.sources == []
    assert result.error is not None
    assert result.error.category == "tool_failure"
    assert result.error.message == "upstream unavailable"
    assert result.error.retryable is True


def test_run_agent_once_preserves_terminal_crawl_error_without_sources() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "error": {
                            "kind": "provider_unavailable",
                            "message": "temporary upstream issue",
                            "retryable": True,
                            "status_code": 503,
                            "attempt_number": 1,
                            "operation": "open_url",
                            "timings": {"total_ms": 80, "provider_ms": 60},
                        },
                        "meta": {
                            "operation": "open_url",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 80,
                            "timings": {"total_ms": 80, "provider_ms": 60},
                        },
                    },
                },
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "error": {
                            "kind": "invalid_request",
                            "message": "url is outside the configured retrieval policy domain scope",
                            "retryable": False,
                            "status_code": 400,
                            "attempt_number": 2,
                            "operation": "open_url",
                            "timings": {"total_ms": 10},
                        },
                        "meta": {
                            "operation": "open_url",
                            "attempts": 2,
                            "retries": 1,
                            "duration_ms": 10,
                            "timings": {"total_ms": 10},
                        },
                    },
                },
                {
                    "role": "assistant",
                    "content": "Fallback answer.",
                },
            ]
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.final_answer is None
    assert result.sources == []
    assert result.error is not None
    assert result.error.category == "tool_failure"
    assert result.error.message == "url is outside the configured retrieval policy domain scope"
    assert result.error.retryable is False


def test_run_agent_once_prefers_terminal_zero_evidence_crawl_success_without_sources() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "error": {
                            "kind": "provider_unavailable",
                            "message": "temporary upstream issue",
                            "retryable": True,
                            "status_code": 503,
                            "attempt_number": 1,
                            "operation": "open_url",
                            "timings": {"total_ms": 80, "provider_ms": 60},
                        },
                        "meta": {
                            "operation": "open_url",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 80,
                            "timings": {"total_ms": 80, "provider_ms": 60},
                        },
                    },
                },
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "url": "https://example.com/thin",
                        "final_url": "https://example.com/thin",
                        "text": "",
                        "markdown": "",
                        "excerpts": [],
                        "status_code": 200,
                        "content_type": "text/html",
                        "fallback_reason": "low-content-quality",
                        "meta": {
                            "operation": "open_url",
                            "attempts": 2,
                            "retries": 1,
                            "duration_ms": 20,
                            "timings": {"total_ms": 20},
                        },
                    },
                },
                {
                    "role": "assistant",
                    "content": "Fallback answer.",
                },
            ]
        }
    )

    result = run_agent_once(
        "investigate citations",
        runtime_dependencies=RuntimeDependencies(agent=agent),
    )

    assert result.status == "failed"
    assert result.final_answer is None
    assert result.sources == []
    assert result.error is not None
    assert result.error.category == "tool_failure"
    assert result.error.message == "agent crawl returned no evidence"
    assert result.error.retryable is False


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


def test_run_agent_once_parses_repr_encoded_tool_payloads_into_source_registry() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "web_search",
                    "content": (
                        "query='example topic' "
                        "results=[WebSearchResult(title='Example source', "
                        "url=HttpUrl('https://example.com/a'), "
                        "snippet='Snippet A', "
                        "rank=SearchRank(position=1, provider_position=1))] "
                        "metadata=SearchMetadata(result_count=1, provider='serper') "
                        "meta=ToolMeta(operation='web_search', attempts=1, retries=0, "
                        "duration_ms=12, timings=ToolTimings(total_ms=12, provider_ms=10))"
                    ),
                },
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": (
                        "url=HttpUrl('https://example.com/a') "
                        "final_url=HttpUrl('https://example.com/a') "
                        "text='Expanded article body.' "
                        "markdown='# Example source' "
                        "excerpts=[OpenUrlExcerpt(text='Expanded article body.', markdown='# Example source')] "
                        "status_code=200 content_type='text/html' fallback_reason=None "
                        "meta=OpenUrlMeta(operation='open_url', attempts=1, retries=0, "
                        "duration_ms=20, timings=ToolTimings(total_ms=20, provider_ms=None), "
                        "strategy_used='http', escalation_count=0, session_profile_id=None, "
                        "block_reason=None, rendered=False, challenge_detected=False)"
                    ),
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
            "snippet": "Expanded article body.",
        }
    ]


def test_run_agent_once_replaces_placeholder_agent_answer_when_sources_exist() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "web_search",
                    "content": (
                        "query='example topic' "
                        "results=[WebSearchResult(title='Example source', "
                        "url=HttpUrl('https://example.com/a'), "
                        "snippet='Snippet A', "
                        "rank=SearchRank(position=1, provider_position=1))] "
                        "metadata=SearchMetadata(result_count=1, provider='serper') "
                        "meta=ToolMeta(operation='web_search', attempts=1, retries=0, "
                        "duration_ms=12, timings=ToolTimings(total_ms=12, provider_ms=10))"
                    ),
                },
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": (
                        "url=HttpUrl('https://example.com/a') "
                        "final_url=HttpUrl('https://example.com/a') "
                        "text='Expanded article body.' "
                        "markdown='# Example source' "
                        "excerpts=[OpenUrlExcerpt(text='Expanded article body.', markdown='# Example source')] "
                        "status_code=200 content_type='text/html' fallback_reason=None "
                        "meta=OpenUrlMeta(operation='open_url', attempts=1, retries=0, "
                        "duration_ms=20, timings=ToolTimings(total_ms=20, provider_ms=None), "
                        "strategy_used='http', escalation_count=0, session_profile_id=None, "
                        "block_reason=None, rendered=False, challenge_detected=False)"
                    ),
                },
                {
                    "role": "assistant",
                    "content": "Sorry, need more steps to process this request.",
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
    assert result.final_answer.text != "Sorry, need more steps to process this request."
    assert "Example source" in result.final_answer.text
    assert result.model_dump(mode="json")["sources"] == [
        {
            "source_id": "https-example-com-a",
            "title": "Example source",
            "url": "https://example.com/a",
            "snippet": "Expanded article body.",
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
        crawl_runner = StubQuickCrawlRunner(
            payloads_by_url={
                "https://example.com/one": {
                    "url": "https://example.com/one",
                    "final_url": "https://example.com/one",
                    "text": "Expanded summary one.",
                    "markdown": "Expanded summary one.",
                    "status_code": 200,
                    "content_type": "text/html",
                    "fallback_reason": None,
                    "meta": {
                        "operation": "open_url",
                        "attempts": 1,
                        "retries": 0,
                        "duration_ms": 20,
                        "timings": {"total_ms": 20},
                    },
                }
            }
        )
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
                ),
                quick_crawl_runner=crawl_runner,
            ),
        )
        assert result.status == "completed"
        assert result.tool_call_count == 2
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
