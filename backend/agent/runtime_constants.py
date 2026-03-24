from __future__ import annotations

from backend.agent.quick_search import DEFAULT_QUICK_SEARCH_MAX_RESULTS
from backend.agent.schemas import AgentRunMode, AgentRuntimeProfile


QUICK_RUNTIME_MODE = "quick"
AGENTIC_RUNTIME_MODE = "agentic"
DEEP_RESEARCH_RUNTIME_MODE = "deep_research"
CANONICAL_TOOL_NAMES = ("web_search", "open_url")
DEFAULT_RECURSION_LIMIT = 12
QUICK_RUNTIME_MAX_CRAWLS = 3
STANDARD_AGENT_MAX_SEARCH_RESULTS = 4
STANDARD_AGENT_MAX_CRAWL_CHARS = 4000
RUNTIME_PROFILES: dict[AgentRunMode, AgentRuntimeProfile] = {
    QUICK_RUNTIME_MODE: AgentRuntimeProfile(
        name=QUICK_RUNTIME_MODE,
        model="gpt-4.1-mini",
        recursion_limit=4,
        timeout_seconds=20,
        execution_mode="single_pass",
        max_tool_steps=1,
        max_search_results=DEFAULT_QUICK_SEARCH_MAX_RESULTS,
        max_crawl_chars=0,
    ),
    AGENTIC_RUNTIME_MODE: AgentRuntimeProfile(
        name=AGENTIC_RUNTIME_MODE,
        model="gpt-4.1-mini",
        recursion_limit=DEFAULT_RECURSION_LIMIT,
        timeout_seconds=45,
        execution_mode="bounded_agent_loop",
        max_tool_steps=6,
        max_search_results=STANDARD_AGENT_MAX_SEARCH_RESULTS,
        max_crawl_chars=STANDARD_AGENT_MAX_CRAWL_CHARS,
    ),
    DEEP_RESEARCH_RUNTIME_MODE: AgentRuntimeProfile(
        name=DEEP_RESEARCH_RUNTIME_MODE,
        model="gpt-4.1",
        recursion_limit=DEFAULT_RECURSION_LIMIT,
        timeout_seconds=180,
        execution_mode="background_research",
        max_tool_steps=16,
        max_search_results=STANDARD_AGENT_MAX_SEARCH_RESULTS,
        max_crawl_chars=STANDARD_AGENT_MAX_CRAWL_CHARS,
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
