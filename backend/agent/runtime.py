from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Protocol
from uuid import uuid4

from backend.agent.prompts import build_system_prompt
from backend.agent.types import (
    AgentRunError,
    AgentRunMode,
    AgentRunResult,
    AgentRuntimeProfile,
)
from backend.app.tools.web_crawl import web_crawl
from backend.app.tools.web_search import web_search

CANONICAL_TOOL_NAMES = ("web_search", "web_crawl")
DEFAULT_RECURSION_LIMIT = 12
RUNTIME_PROFILES: dict[AgentRunMode, AgentRuntimeProfile] = {
    "quick": AgentRuntimeProfile(
        name="quick",
        model="gpt-4.1-mini",
        recursion_limit=4,
        timeout_seconds=20,
        execution_mode="single_pass",
    ),
    "agentic": AgentRuntimeProfile(
        name="agentic",
        model="gpt-4.1-mini",
        recursion_limit=DEFAULT_RECURSION_LIMIT,
        timeout_seconds=45,
        execution_mode="bounded_agent_loop",
    ),
    "deep_research": AgentRuntimeProfile(
        name="deep_research",
        model="gpt-4.1",
        recursion_limit=24,
        timeout_seconds=180,
        execution_mode="background_research",
    ),
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


def run_agent_once(
    prompt: str,
    mode: AgentRunMode = "agentic",
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
        dependencies = runtime_dependencies or build_runtime_dependencies()
        agent = _resolve_agent(dependencies, profile)
        raw_result = agent.invoke(
            _build_inputs(prompt),
            _build_runtime_config(profile),
        )
        return AgentRunResult(
            run_id=run_id,
            status="completed",
            final_answer=_extract_final_answer(raw_result),
            tool_call_count=_count_tool_calls(raw_result),
            elapsed_ms=_elapsed_ms(started_at),
        )
    except Exception as exc:
        return _map_runtime_failure(exc=exc, run_id=run_id, started_at=started_at)


def build_runtime_dependencies() -> RuntimeDependencies:
    tools = _get_canonical_tools()
    _assert_canonical_tool_names(tools)
    return RuntimeDependencies(agent_factory=_build_default_agent)


def get_runtime_profile(mode: AgentRunMode) -> AgentRuntimeProfile:
    return RUNTIME_PROFILES[mode]


def _get_canonical_tools() -> tuple[Any, Any]:
    return (web_search, web_crawl)


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
) -> AgentExecutor:
    if runtime_dependencies.agent is not None:
        return runtime_dependencies.agent

    if runtime_dependencies.agent_factory is None:
        raise RuntimeError("Runtime dependencies must include an agent or agent_factory")

    tools = _get_canonical_tools()
    _assert_canonical_tool_names(tools)
    return runtime_dependencies.agent_factory(profile, tools)


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
        prompt=build_system_prompt(profile.name),
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


def _build_runtime_config(profile: AgentRuntimeProfile) -> dict[str, Any]:
    return {
        "recursion_limit": profile.recursion_limit,
        "run_mode": profile.name,
        "execution_mode": profile.execution_mode,
        "timeout_seconds": profile.timeout_seconds,
        "model": profile.model,
    }


def _extract_final_answer(raw_result: Any) -> str:
    if isinstance(raw_result, str):
        return raw_result.strip()

    if isinstance(raw_result, dict):
        messages = raw_result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                content = _coerce_message_content(message)
                if content:
                    return content

        output = raw_result.get("output")
        if isinstance(output, str) and output.strip():
            return output.strip()

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
