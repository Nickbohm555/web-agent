from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from backend.agent.prompts import SYSTEM_PROMPT
from backend.agent.types import AgentRunResult
from backend.app.tools.web_crawl import web_crawl
from backend.app.tools.web_search import web_search

CANONICAL_TOOL_NAMES = ("web_search", "web_crawl")


class AgentExecutor(Protocol):
    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> Any:
        ...


@dataclass(frozen=True)
class RuntimeDependencies:
    agent: AgentExecutor


def run_agent_once(
    prompt: str,
    *,
    runtime_dependencies: RuntimeDependencies | None = None,
) -> AgentRunResult:
    run_id = str(uuid4())
    started_at = perf_counter()
    dependencies = runtime_dependencies or build_runtime_dependencies()
    raw_result = dependencies.agent.invoke(_build_inputs(prompt))

    return AgentRunResult(
        run_id=run_id,
        status="completed",
        final_answer=_extract_final_answer(raw_result),
        tool_call_count=_count_tool_calls(raw_result),
        elapsed_ms=int((perf_counter() - started_at) * 1000),
    )


def build_runtime_dependencies() -> RuntimeDependencies:
    tools = _get_canonical_tools()
    _assert_canonical_tool_names(tools)
    return RuntimeDependencies(agent=_build_default_agent(tools))


def _get_canonical_tools() -> tuple[Any, Any]:
    return (web_search, web_crawl)


def _assert_canonical_tool_names(tools: tuple[Any, ...]) -> None:
    actual_names = tuple(getattr(tool, "name", None) for tool in tools)
    if actual_names != CANONICAL_TOOL_NAMES:
        raise ValueError(
            "Canonical tool binding mismatch: "
            f"expected {CANONICAL_TOOL_NAMES}, got {actual_names}"
        )


def _build_default_agent(tools: tuple[Any, ...]) -> AgentExecutor:
    try:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # pragma: no cover - exercised only in integrated environments
        raise RuntimeError(
            "Agent runtime dependencies are unavailable; install compatible langchain packages"
        ) from exc

    model = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
    return create_agent(model=model, tools=list(tools), system_prompt=SYSTEM_PROMPT)


def _build_inputs(prompt: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": prompt}]}


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
