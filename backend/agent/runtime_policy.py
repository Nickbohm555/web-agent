from __future__ import annotations

from typing import Any

from backend.agent.schemas import AgentRuntimeProfile


def build_runtime_config(profile: AgentRuntimeProfile) -> dict[str, Any]:
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


def build_retrieval_brief(
    *,
    prompt: str,
    profile: AgentRuntimeProfile,
) -> str:
    normalized_prompt = " ".join(prompt.strip().split())
    if not normalized_prompt:
        return ""

    return (
        "Retrieval strategy:\n"
        f"- Answer objective: {normalized_prompt}\n"
        "- Search plan: use web_search to find likely-answering sources\n"
        f"- Crawl plan: {build_crawl_plan(profile)}\n"
        f"- Mode plan: {build_mode_plan(profile)}"
    )


def build_crawl_plan(profile: AgentRuntimeProfile) -> str:
    if profile.name == "deep_research":
        return "crawl only high-value pages that look useful for the answer"
    return "crawl only pages whose search excerpts look promising"


def build_mode_plan(profile: AgentRuntimeProfile) -> str:
    if profile.name == "agentic":
        return "use a small number of decisive searches and only enough crawls to answer accurately"
    if profile.name == "deep_research":
        return "compare multiple promising sources, validate conflicts, and expand only when needed"
    return "optimize for one decisive search pass"
