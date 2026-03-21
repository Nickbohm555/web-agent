from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Protocol
from uuid import uuid4

from pydantic import ValidationError

from backend.agent.prompts import build_system_prompt
from backend.agent.quick_search import (
    DEFAULT_QUICK_SEARCH_MAX_RESULTS,
    QuickSearchRunner,
    run_quick_search,
    synthesize_quick_answer,
)
from backend.agent.types import (
    AgentAnswerCitation,
    AgentRunError,
    AgentRunMode,
    AgentRunResult,
    AgentRunRetrievalPolicy,
    AgentSourceReference,
    AgentStructuredAnswer,
    AgentRuntimeProfile,
)
from backend.app.contracts.tool_errors import ToolErrorEnvelope
from backend.app.contracts.web_search import WebSearchResponse
from backend.app.tools.web_crawl import build_web_crawl_tool, web_crawl
from backend.app.tools.web_search import build_web_search_tool, web_search

CANONICAL_TOOL_NAMES = ("web_search", "web_crawl")
DEFAULT_RECURSION_LIMIT = 12
RUNTIME_PROFILES: dict[AgentRunMode, AgentRuntimeProfile] = {
    "quick": AgentRuntimeProfile(
        name="quick",
        model="gpt-4.1-mini",
        recursion_limit=4,
        timeout_seconds=20,
        execution_mode="single_pass",
        max_tool_steps=1,
        max_search_results=DEFAULT_QUICK_SEARCH_MAX_RESULTS,
        max_crawl_chars=0,
    ),
    "agentic": AgentRuntimeProfile(
        name="agentic",
        model="gpt-4.1-mini",
        recursion_limit=DEFAULT_RECURSION_LIMIT,
        timeout_seconds=45,
        execution_mode="bounded_agent_loop",
        max_tool_steps=6,
        max_search_results=4,
        max_crawl_chars=4000,
    ),
    "deep_research": AgentRuntimeProfile(
        name="deep_research",
        model="gpt-4.1",
        recursion_limit=24,
        timeout_seconds=180,
        execution_mode="background_research",
        max_tool_steps=16,
        max_search_results=8,
        max_crawl_chars=12000,
    ),
}
QUICK_SEARCH_ERROR_CATEGORY_BY_KIND = {
    "provider_unavailable": "provider_failure",
    "provider_timeout": "provider_failure",
    "rate_limited": "provider_failure",
    "timeout": "timeout",
    "invalid_request": "invalid_prompt",
}
QUICK_SEARCH_ERROR_MESSAGE_BY_KIND = {
    "provider_unavailable": "quick search provider request failed",
    "provider_timeout": "quick search provider request failed",
    "rate_limited": "quick search provider request failed",
    "timeout": "quick search timed out",
    "invalid_request": "prompt is invalid for quick search",
}


class AgentExecutor(Protocol):
    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
        ...


class AgentFactory(Protocol):
    def __call__(self, profile: AgentRuntimeProfile, tools: tuple[Any, ...]) -> AgentExecutor:
        ...


@dataclass(frozen=True)
class RuntimeDependencies:
    agent: AgentExecutor | None = None
    agent_factory: AgentFactory | None = None
    quick_search_runner: QuickSearchRunner | None = None


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
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            category="invalid_prompt",
            message="prompt must not be empty",
            retryable=False,
        )

    try:
        profile = get_runtime_profile(mode)
        effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
        dependencies = runtime_dependencies or build_runtime_dependencies()
        if profile.name == "quick":
            return _run_quick_mode(
                prompt=prompt,
                run_id=run_id,
                started_at=started_at,
                retrieval_policy=effective_policy,
                runtime_dependencies=dependencies,
            )
        agent = _resolve_agent(dependencies, profile, effective_policy)
        raw_result = agent.invoke(
            _build_inputs(prompt),
            _build_runtime_config(profile, effective_policy),
        )
        sources = _extract_sources(raw_result)
        return AgentRunResult(
            run_id=run_id,
            status="completed",
            final_answer=_extract_final_answer(raw_result, sources),
            sources=sources,
            tool_call_count=_count_tool_calls(raw_result),
            elapsed_ms=_elapsed_ms(started_at),
        )
    except Exception as exc:
        return _map_runtime_failure(exc=exc, run_id=run_id, started_at=started_at)


def build_runtime_dependencies() -> RuntimeDependencies:
    _assert_canonical_tool_names(_get_canonical_tools())
    return RuntimeDependencies(
        agent_factory=_build_default_agent,
        quick_search_runner=run_quick_search,
    )


def get_runtime_profile(mode: AgentRunMode) -> AgentRuntimeProfile:
    return RUNTIME_PROFILES[mode]


def _get_canonical_tools() -> tuple[Any, Any]:
    return (web_search, web_crawl)


def _get_tools_for_profile(
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
) -> tuple[Any, Any]:
    if profile.name == "quick":
        return _get_canonical_tools()

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


def _assert_canonical_tool_names(tools: tuple[Any, ...]) -> None:
    actual_names = tuple(getattr(tool, "name", None) for tool in tools)
    if actual_names != CANONICAL_TOOL_NAMES:
        raise ValueError(
            "Canonical tool binding mismatch: "
            f"expected {CANONICAL_TOOL_NAMES}, got {actual_names}"
        )


def _resolve_agent(
    runtime_dependencies: RuntimeDependencies,
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy,
) -> AgentExecutor:
    if runtime_dependencies.agent is not None:
        return runtime_dependencies.agent

    if runtime_dependencies.agent_factory is None:
        raise RuntimeError("Runtime dependencies must include an agent or agent_factory")

    tools = _get_tools_for_profile(profile, retrieval_policy)
    _assert_canonical_tool_names(tools)
    return runtime_dependencies.agent_factory(profile, tools)


def _run_quick_mode(
    *,
    prompt: str,
    run_id: str,
    started_at: float,
    retrieval_policy: AgentRunRetrievalPolicy,
    runtime_dependencies: RuntimeDependencies,
) -> AgentRunResult:
    payload = _get_quick_search_runner(runtime_dependencies)(
        query=prompt,
        max_results=DEFAULT_QUICK_SEARCH_MAX_RESULTS,
        freshness=retrieval_policy.search.freshness,
        include_domains=retrieval_policy.search.include_domains,
        exclude_domains=retrieval_policy.search.exclude_domains,
    )

    error = _coerce_tool_error(payload)
    if error is not None:
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            category=_map_quick_search_error_category(error.error.kind),
            message=_map_quick_search_error_message(error.error.kind),
            retryable=error.error.retryable,
        )

    try:
        response = WebSearchResponse.model_validate(payload)
    except Exception:
        return _failed_result(
            run_id=run_id,
            started_at=started_at,
            category="tool_failure",
            message="quick search returned invalid payload",
            retryable=False,
        )

    return AgentRunResult(
        run_id=run_id,
        status="completed",
        final_answer=synthesize_quick_answer(response),
        sources=_extract_search_sources(response),
        tool_call_count=1,
        elapsed_ms=_elapsed_ms(started_at),
    )


def _build_default_agent(profile: AgentRuntimeProfile, tools: tuple[Any, ...]) -> AgentExecutor:
    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # pragma: no cover - exercised only in integrated environments
        raise RuntimeError(
            "Agent runtime dependencies are unavailable; install compatible langchain packages"
        ) from exc

    agent_factory = _load_agent_factory()

    model = ChatOpenAI(
        model=profile.model,
        temperature=0,
        timeout=profile.timeout_seconds,
    )
    return agent_factory(
        model=model,
        tools=tools,
        prompt=build_system_prompt(profile),
    )


def _load_agent_factory() -> Callable[..., AgentExecutor]:
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


def _build_inputs(prompt: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": prompt}]}


def _build_runtime_config(
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy,
) -> dict[str, Any]:
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
        "retrieval_policy": retrieval_policy.model_dump(),
    }


def _extract_final_answer(
    raw_result: Any,
    sources: list[AgentSourceReference] | None = None,
) -> AgentStructuredAnswer:
    source_lookup = _build_source_lookup(sources or [])

    if isinstance(raw_result, str):
        return AgentStructuredAnswer(text=raw_result.strip())

    if isinstance(raw_result, dict):
        direct_final_answer = raw_result.get("final_answer")
        if isinstance(direct_final_answer, dict):
            return _validate_structured_answer(direct_final_answer, source_lookup)

        messages = raw_result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                direct_final_answer = _coerce_message_final_answer(message)
                if isinstance(direct_final_answer, dict):
                    return _validate_structured_answer(direct_final_answer, source_lookup)

                content = _coerce_message_content(message)
                if content:
                    citations = _coerce_message_citations(message, source_lookup)
                    return AgentStructuredAnswer(text=content, citations=citations)

        output = raw_result.get("output")
        if isinstance(output, str) and output.strip():
            direct_citations = raw_result.get("citations")
            if isinstance(direct_citations, list):
                return AgentStructuredAnswer(
                    text=output.strip(),
                    citations=_validate_citations(direct_citations, source_lookup),
                )
            return AgentStructuredAnswer(text=output.strip())

    raise ValueError("Agent runtime did not return a final answer")


def _count_tool_calls(raw_result: Any) -> int:
    if not isinstance(raw_result, dict):
        return 0

    messages = raw_result.get("messages")
    if not isinstance(messages, list):
        return 0

    total = 0
    for message in messages:
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                total += len(tool_calls)
            elif message.get("type") == "tool":
                total += 1
            continue

        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            total += len(tool_calls)
        elif getattr(message, "type", None) == "tool":
            total += 1

    return total


def _extract_sources(raw_result: Any) -> list[AgentSourceReference]:
    if not isinstance(raw_result, dict):
        return []

    direct_sources = raw_result.get("sources")
    if isinstance(direct_sources, list):
        return _validate_sources(direct_sources)

    messages = raw_result.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            source_payload = _coerce_message_sources(message)
            if source_payload:
                return source_payload

    return []


def _coerce_message_sources(message: Any) -> list[AgentSourceReference]:
    if isinstance(message, dict):
        direct_sources = message.get("sources")
        if isinstance(direct_sources, list):
            return _validate_sources(direct_sources)

        additional_kwargs = message.get("additional_kwargs")
        if isinstance(additional_kwargs, dict) and isinstance(additional_kwargs.get("sources"), list):
            return _validate_sources(additional_kwargs["sources"])
        return []

    direct_sources = getattr(message, "sources", None)
    if isinstance(direct_sources, list):
        return _validate_sources(direct_sources)

    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict) and isinstance(additional_kwargs.get("sources"), list):
        return _validate_sources(additional_kwargs["sources"])

    return []


def _coerce_message_final_answer(message: Any) -> dict[str, Any] | None:
    if isinstance(message, dict):
        direct_final_answer = message.get("final_answer")
        if isinstance(direct_final_answer, dict):
            return direct_final_answer

        additional_kwargs = message.get("additional_kwargs")
        if isinstance(additional_kwargs, dict) and isinstance(
            additional_kwargs.get("final_answer"), dict
        ):
            return additional_kwargs["final_answer"]
        return None

    direct_final_answer = getattr(message, "final_answer", None)
    if isinstance(direct_final_answer, dict):
        return direct_final_answer

    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict) and isinstance(additional_kwargs.get("final_answer"), dict):
        return additional_kwargs["final_answer"]

    return None


def _validate_sources(source_payload: list[Any]) -> list[AgentSourceReference]:
    sources: list[AgentSourceReference] = []
    for entry in source_payload:
        try:
            sources.append(AgentSourceReference.model_validate(entry))
        except Exception:
            continue
    return sources


def _extract_search_sources(response: WebSearchResponse) -> list[AgentSourceReference]:
    return [
        AgentSourceReference(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
        )
        for result in response.results[:3]
    ]


def _build_source_lookup(
    sources: list[AgentSourceReference],
) -> dict[str, AgentSourceReference]:
    lookup: dict[str, AgentSourceReference] = {}
    for source in sources:
        lookup[source.source_id] = source
        lookup[str(source.url)] = source
    return lookup


def _coerce_message_citations(
    message: Any,
    source_lookup: dict[str, AgentSourceReference],
) -> list[AgentAnswerCitation]:
    if isinstance(message, dict):
        direct_citations = message.get("citations")
        if isinstance(direct_citations, list):
            return _validate_citations(direct_citations, source_lookup)

        additional_kwargs = message.get("additional_kwargs")
        if isinstance(additional_kwargs, dict) and isinstance(
            additional_kwargs.get("citations"), list
        ):
            return _validate_citations(additional_kwargs["citations"], source_lookup)
        return []

    direct_citations = getattr(message, "citations", None)
    if isinstance(direct_citations, list):
        return _validate_citations(direct_citations, source_lookup)

    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict) and isinstance(additional_kwargs.get("citations"), list):
        return _validate_citations(additional_kwargs["citations"], source_lookup)

    return []


def _validate_structured_answer(
    payload: dict[str, Any],
    source_lookup: dict[str, AgentSourceReference],
) -> AgentStructuredAnswer:
    answer_payload = dict(payload)
    citations = answer_payload.get("citations")
    if isinstance(citations, list):
        answer_payload["citations"] = _validate_citations(citations, source_lookup)
    return AgentStructuredAnswer.model_validate(answer_payload)


def _validate_citations(
    citation_payload: list[Any],
    source_lookup: dict[str, AgentSourceReference],
) -> list[AgentAnswerCitation]:
    citations = [
        AgentAnswerCitation.model_validate(_hydrate_citation(entry, source_lookup))
        for entry in citation_payload
    ]
    citations.sort(key=lambda citation: (citation.start_index, citation.end_index, citation.source_id))
    return citations


def _hydrate_citation(
    payload: Any,
    source_lookup: dict[str, AgentSourceReference],
) -> Any:
    if not isinstance(payload, dict):
        return payload

    citation = dict(payload)
    source_id = citation.get("source_id")
    source_url = citation.get("url")

    lookup_key: str | None = None
    if isinstance(source_id, str) and source_id.strip():
        lookup_key = source_id.strip()
    elif source_url is not None:
        lookup_key = str(source_url).strip()

    source = source_lookup.get(lookup_key) if lookup_key else None
    if source is not None:
        citation.setdefault("source_id", source.source_id)
        citation.setdefault("title", source.title)
        citation.setdefault("url", str(source.url))

    return citation


def _coerce_message_content(message: Any) -> str:
    if isinstance(message, dict):
        return _normalize_content_value(message.get("content"))

    return _normalize_content_value(getattr(message, "content", None))


def _normalize_content_value(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
                continue
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    parts.append(text_value.strip())
        return "\n".join(parts).strip()

    return ""


def _coerce_tool_error(payload: Any) -> ToolErrorEnvelope | None:
    if not isinstance(payload, dict) or "error" not in payload:
        return None
    return ToolErrorEnvelope.model_validate(payload)


def _get_quick_search_runner(runtime_dependencies: RuntimeDependencies) -> QuickSearchRunner:
    return runtime_dependencies.quick_search_runner or run_quick_search


def _map_quick_search_error_category(kind: str) -> str:
    return QUICK_SEARCH_ERROR_CATEGORY_BY_KIND.get(kind, "tool_failure")


def _map_quick_search_error_message(kind: str) -> str:
    return QUICK_SEARCH_ERROR_MESSAGE_BY_KIND.get(kind, "quick search failed")


def _map_runtime_failure(*, exc: Exception, run_id: str, started_at: float) -> AgentRunResult:
    category = "internal_error"
    retryable = False
    message = "agent runtime failed"

    if _is_recursion_limit_error(exc):
        category = "loop_limit"
        message = "agent exceeded bounded execution limit"
    elif _is_timeout_error(exc):
        category = "timeout"
        retryable = True
        message = "agent execution timed out"
    elif _is_tool_runtime_error(exc):
        category = "tool_failure"
        message = "agent tool invocation failed"
    elif _is_provider_runtime_error(exc):
        category = "provider_failure"
        retryable = True
        message = "agent provider request failed"
    elif isinstance(exc, ValidationError):
        category = "invalid_prompt"
        message = _first_validation_error(exc) or "prompt is invalid"
    elif isinstance(exc, ValueError):
        category = "invalid_prompt"
        message = str(exc) or "prompt is invalid"

    return _failed_result(
        run_id=run_id,
        started_at=started_at,
        category=category,
        message=message,
        retryable=retryable,
    )


def _failed_result(
    *,
    run_id: str,
    started_at: float,
    category: str,
    message: str,
    retryable: bool,
) -> AgentRunResult:
    return AgentRunResult(
        run_id=run_id,
        status="failed",
        final_answer="",
        tool_call_count=0,
        elapsed_ms=_elapsed_ms(started_at),
        error=AgentRunError(
            category=category,
            message=message,
            retryable=retryable,
        ),
    )


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _first_validation_error(exc: ValidationError) -> str | None:
    errors = exc.errors()
    if not errors:
        return None

    message = errors[0].get("msg")
    if not isinstance(message, str):
        return None

    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def _is_recursion_limit_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "graphrecursion" in name or "recursion" in message


def _is_timeout_error(exc: Exception) -> bool:
    try:
        import httpx
    except Exception:  # pragma: no cover - import guard for minimal environments
        httpx = None  # type: ignore[assignment]

    timeout_types: tuple[type[BaseException], ...] = (TimeoutError,)
    if httpx is not None:
        timeout_types = timeout_types + (httpx.TimeoutException,)
    return isinstance(exc, timeout_types)


def _is_tool_runtime_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "tool" in name or "tool" in message


def _is_provider_runtime_error(exc: Exception) -> bool:
    try:
        import httpx
    except Exception:  # pragma: no cover - import guard for minimal environments
        httpx = None  # type: ignore[assignment]

    if httpx is not None and isinstance(exc, httpx.HTTPError):
        return True

    name = type(exc).__name__.lower()
    return any(token in name for token in ("openai", "provider", "api", "rate", "auth"))
