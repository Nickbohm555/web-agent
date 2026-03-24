from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Protocol
from uuid import uuid4

from backend.agent.prompts import build_system_prompt
from backend.agent.quick_search import (
    QuickSearchRunner,
    run_quick_search,
)
from backend.agent.quick_runtime import QuickCrawlRunner, run_quick_runtime
from backend.agent.runtime_constants import (
    AGENTIC_RUNTIME_MODE,
    CANONICAL_TOOL_NAMES,
    DEEP_RESEARCH_RUNTIME_MODE,
    QUICK_RUNTIME_MODE,
    RUNTIME_PROFILES,
)
from backend.agent.runtime_errors import (
    elapsed_ms,
    failed_result,
    map_runtime_failure,
)
from backend.agent.runtime_policy import (
    build_retrieval_brief,
    build_runtime_config,
    resolve_effective_retrieval_policy,
)
from backend.agent.runtime_sources import (
    count_tool_calls,
    extract_crawl_error,
    extract_final_answer,
    extract_sources,
    has_zero_evidence_crawl_success,
)
from backend.agent.schemas import (
    AgentRunMode,
    AgentRunError,
    AgentRunResult,
    AgentRunRetrievalPolicy,
    AgentRuntimeProfile,
)
from backend.app.tools.web_crawl import build_web_crawl_tool, run_web_crawl, web_crawl
from backend.app.tools.web_search import build_web_search_tool, web_search


class AgentExecutor(Protocol):
    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
        ...


class AgentFactory(Protocol):
    def __call__(
        self,
        profile: AgentRuntimeProfile,
        tools: tuple[Any, ...],
        system_prompt: str,
    ) -> AgentExecutor:
        ...


class QuickRuntimeRunner(Protocol):
    def __call__(
        self,
        *,
        prompt: str,
        run_id: str,
        started_at: float,
        retrieval_policy: AgentRunRetrievalPolicy,
        runtime_dependencies: "RuntimeDependencies",
    ) -> AgentRunResult:
        ...


class DeepResearchRunner(Protocol):
    def __call__(
        self,
        *,
        prompt: str,
        run_id: str,
        started_at: float,
        retrieval_policy: AgentRunRetrievalPolicy,
        runtime_dependencies: "RuntimeDependencies",
    ) -> AgentRunResult:
        ...


@dataclass(frozen=True)
class RuntimeDependencies:
    agent: AgentExecutor | None = None
    agent_factory: AgentFactory | None = None
    quick_search_runner: QuickSearchRunner | None = None
    quick_crawl_runner: QuickCrawlRunner | None = None
    quick_runtime_runner: QuickRuntimeRunner | None = None
    deep_research_runner: DeepResearchRunner | None = None


def run_agent_once(
    prompt: str,
    mode: AgentRunMode = "agentic",
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    *,
    runtime_dependencies: RuntimeDependencies | None = None,
) -> AgentRunResult:
    run_id = str(uuid4())
    started_at = perf_counter()
    if not prompt.strip():
        return failed_result(
            run_id=run_id,
            started_at=started_at,
            category="invalid_prompt",
            message="prompt must not be empty",
            retryable=False,
        )

    try:
        profile = get_runtime_profile(mode)
        effective_policy = resolve_effective_retrieval_policy(
            prompt=prompt,
            retrieval_policy=retrieval_policy,
        )
        dependencies = runtime_dependencies or build_runtime_dependencies()
        if profile.name == QUICK_RUNTIME_MODE:
            return get_quick_runtime_runner(dependencies)(
                prompt=prompt,
                run_id=run_id,
                started_at=started_at,
                retrieval_policy=effective_policy,
                runtime_dependencies=dependencies,
            )
        if profile.name == DEEP_RESEARCH_RUNTIME_MODE:
            return get_deep_research_runtime_runner(dependencies)(
                prompt=prompt,
                run_id=run_id,
                started_at=started_at,
                retrieval_policy=effective_policy,
                runtime_dependencies=dependencies,
            )
        return run_agentic_mode(
            prompt=prompt,
            run_id=run_id,
            started_at=started_at,
            retrieval_policy=effective_policy,
            runtime_dependencies=dependencies,
        )
    except Exception as exc:
        return map_runtime_failure(exc=exc, run_id=run_id, started_at=started_at)


def build_runtime_dependencies() -> RuntimeDependencies:
    assert_canonical_tool_names(get_canonical_tools())
    return RuntimeDependencies(
        agent_factory=build_default_agent,
        quick_search_runner=run_quick_search,
        quick_crawl_runner=run_web_crawl,
        quick_runtime_runner=run_quick_mode,
        deep_research_runner=run_deep_research_mode,
    )


def get_runtime_profile(mode: AgentRunMode) -> AgentRuntimeProfile:
    return RUNTIME_PROFILES[mode]


def get_canonical_tools() -> tuple[Any, Any]:
    return (web_search, web_crawl)


def get_tools_for_profile(
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
) -> tuple[Any, Any]:
    if profile.name == QUICK_RUNTIME_MODE:
        return get_canonical_tools()

    effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
    return (
        build_web_search_tool(
            max_results_cap=profile.max_search_results,
            retrieval_policy=effective_policy,
        ),
        build_web_crawl_tool(
            max_content_chars=profile.max_crawl_chars,
            retrieval_policy=effective_policy,
        ),
    )


def assert_canonical_tool_names(tools: tuple[Any, ...]) -> None:
    actual_names = tuple(getattr(tool, "name", None) for tool in tools)
    if actual_names != CANONICAL_TOOL_NAMES:
        raise ValueError(
            "Canonical tool binding mismatch: "
            f"expected {CANONICAL_TOOL_NAMES}, got {actual_names}"
        )


def resolve_agent(
    runtime_dependencies: RuntimeDependencies,
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy,
    prompt: str,
) -> AgentExecutor:
    if runtime_dependencies.agent is not None:
        return runtime_dependencies.agent

    if runtime_dependencies.agent_factory is None:
        raise RuntimeError("Runtime dependencies must include an agent or agent_factory")

    tools = get_tools_for_profile(profile, retrieval_policy)
    assert_canonical_tool_names(tools)
    system_prompt = build_system_prompt(
        profile,
        retrieval_policy,
        build_retrieval_brief(
            prompt=prompt,
            profile=profile,
            retrieval_policy=retrieval_policy,
        ),
    )
    return runtime_dependencies.agent_factory(
        profile,
        tools,
        system_prompt,
    )


def run_quick_mode(
    *,
    prompt: str,
    run_id: str,
    started_at: float,
    retrieval_policy: AgentRunRetrievalPolicy,
    runtime_dependencies: RuntimeDependencies,
) -> AgentRunResult:
    return run_quick_runtime(
        prompt=prompt,
        run_id=run_id,
        started_at=started_at,
        retrieval_policy=retrieval_policy,
        search_runner=get_quick_search_runner(runtime_dependencies),
        crawl_runner=get_quick_crawl_runner(runtime_dependencies),
    )


def run_agentic_mode(
    *,
    prompt: str,
    run_id: str,
    started_at: float,
    retrieval_policy: AgentRunRetrievalPolicy,
    runtime_dependencies: RuntimeDependencies,
) -> AgentRunResult:
    return run_agent_profile_mode(
        profile=get_runtime_profile(AGENTIC_RUNTIME_MODE),
        prompt=prompt,
        run_id=run_id,
        started_at=started_at,
        retrieval_policy=retrieval_policy,
        runtime_dependencies=runtime_dependencies,
    )


def run_deep_research_mode(
    *,
    prompt: str,
    run_id: str,
    started_at: float,
    retrieval_policy: AgentRunRetrievalPolicy,
    runtime_dependencies: RuntimeDependencies,
) -> AgentRunResult:
    return run_agent_profile_mode(
        profile=get_runtime_profile(DEEP_RESEARCH_RUNTIME_MODE),
        prompt=prompt,
        run_id=run_id,
        started_at=started_at,
        retrieval_policy=retrieval_policy,
        runtime_dependencies=runtime_dependencies,
    )


def run_agent_profile_mode(
    *,
    profile: AgentRuntimeProfile,
    prompt: str,
    run_id: str,
    started_at: float,
    retrieval_policy: AgentRunRetrievalPolicy,
    runtime_dependencies: RuntimeDependencies,
) -> AgentRunResult:
    agent = resolve_agent(
        runtime_dependencies,
        profile,
        retrieval_policy,
        prompt,
    )
    raw_result = agent.invoke(
        build_inputs(prompt),
        build_runtime_config(profile, retrieval_policy),
    )
    source_registry = extract_sources(raw_result)
    sources = source_registry.sources()
    crawl_error = extract_crawl_error(raw_result)
    if crawl_error is not None and not sources:
        return AgentRunResult(
            run_id=run_id,
            status="failed",
            final_answer=None,
            sources=[],
            tool_call_count=count_tool_calls(raw_result),
            elapsed_ms=elapsed_ms(started_at),
            error=AgentRunError(
                category="tool_failure",
                message=crawl_error.error.message,
                retryable=crawl_error.error.retryable,
            ),
        )
    if has_zero_evidence_crawl_success(raw_result) and not sources:
        return AgentRunResult(
            run_id=run_id,
            status="failed",
            final_answer=None,
            sources=[],
            tool_call_count=count_tool_calls(raw_result),
            elapsed_ms=elapsed_ms(started_at),
            error=AgentRunError(
                category="tool_failure",
                message="agent crawl returned no evidence",
                retryable=False,
            ),
        )
    return AgentRunResult(
        run_id=run_id,
        status="completed",
        final_answer=extract_final_answer(raw_result, source_registry.source_lookup()),
        sources=sources,
        tool_call_count=count_tool_calls(raw_result),
        elapsed_ms=elapsed_ms(started_at),
    )


def build_default_agent(
    profile: AgentRuntimeProfile,
    tools: tuple[Any, ...],
    system_prompt: str,
) -> AgentExecutor:
    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        raise RuntimeError(
            "Agent runtime dependencies are unavailable; install compatible langchain packages"
        ) from exc

    agent_factory = load_agent_factory()

    model = ChatOpenAI(
        model=profile.model,
        temperature=0,
        timeout=profile.timeout_seconds,
    )
    return agent_factory(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )


def load_agent_factory() -> Callable[..., AgentExecutor]:
    try:
        from langchain.agents import create_agent
    except ImportError:
        from langgraph.prebuilt import create_react_agent

        return lambda *, model, tools, prompt: create_react_agent(
            model=model,
            tools=list(tools),
            prompt=prompt,
        )

    return lambda *, model, tools, prompt: create_agent(
        model=model,
        tools=list(tools),
        system_prompt=prompt,
    )


def build_inputs(prompt: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": prompt}]}


def get_quick_search_runner(runtime_dependencies: RuntimeDependencies) -> QuickSearchRunner:
    return runtime_dependencies.quick_search_runner or run_quick_search


def get_quick_runtime_runner(runtime_dependencies: RuntimeDependencies) -> QuickRuntimeRunner:
    return runtime_dependencies.quick_runtime_runner or run_quick_mode


def get_quick_crawl_runner(runtime_dependencies: RuntimeDependencies) -> QuickCrawlRunner:
    return runtime_dependencies.quick_crawl_runner or run_web_crawl


def get_deep_research_runtime_runner(
    runtime_dependencies: RuntimeDependencies,
) -> DeepResearchRunner:
    return runtime_dependencies.deep_research_runner or run_deep_research_mode
