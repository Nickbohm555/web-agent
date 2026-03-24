from __future__ import annotations

import re

from backend.agent.quick_search import DEFAULT_QUICK_SEARCH_MAX_RESULTS
from backend.agent.schemas import AgentRunMode, AgentRuntimeProfile


QUICK_RUNTIME_MODE = "quick"
AGENTIC_RUNTIME_MODE = "agentic"
DEEP_RESEARCH_RUNTIME_MODE = "deep_research"
CANONICAL_TOOL_NAMES = ("web_search", "web_crawl")
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
PROMPT_DOMAIN_HINTS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\bopenai\b", re.IGNORECASE), ("openai.com", "platform.openai.com")),
    (re.compile(r"\breact\b", re.IGNORECASE), ("react.dev",)),
    (re.compile(r"\bnext(?:\.js|js)?\b", re.IGNORECASE), ("nextjs.org", "vercel.com")),
    (re.compile(r"\bvercel\b", re.IGNORECASE), ("vercel.com",)),
    (re.compile(r"\bnode(?:\.js|js)?\b", re.IGNORECASE), ("nodejs.org",)),
    (re.compile(r"\bpython\b", re.IGNORECASE), ("docs.python.org", "python.org")),
    (re.compile(r"\bfastapi\b", re.IGNORECASE), ("fastapi.tiangolo.com",)),
    (re.compile(r"\bdocker\b", re.IGNORECASE), ("docs.docker.com", "docker.com")),
    (re.compile(r"\bstripe\b", re.IGNORECASE), ("docs.stripe.com", "stripe.com")),
    (re.compile(r"\baws\b|amazon web services", re.IGNORECASE), ("docs.aws.amazon.com", "aws.amazon.com")),
    (re.compile(r"\btailwind(?:css)?\b", re.IGNORECASE), ("tailwindcss.com",)),
)
OFFICIAL_SOURCE_PATTERN = re.compile(
    r"\b(official docs?(?: only)?|official documentation|official source(?:s)?|official site|primary source(?:s)?|company filing|regulatory filing|sec filing)\b",
    re.IGNORECASE,
)
SEC_FILING_PATTERN = re.compile(
    r"\b(sec filing|10-k|10-q|8-k|annual report|quarterly report|earnings filing)\b",
    re.IGNORECASE,
)
TODAY_PATTERN = re.compile(
    r"\b(today|breaking|just announced|just released|as of today|newly announced)\b",
    re.IGNORECASE,
)
WEEK_PATTERN = re.compile(
    r"\b(this week|past week|last week|recent|recent coverage|latest|most recent|newest|current)\b",
    re.IGNORECASE,
)
MONTH_PATTERN = re.compile(r"\b(this month|past month|last month)\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(this year|past year|last year)\b", re.IGNORECASE)
DOMAIN_PATTERN = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)
FETCH_MAX_AGE_BY_FRESHNESS = {
    "any": 300_000,
    "day": 60 * 60 * 1000,
    "week": 6 * 60 * 60 * 1000,
    "month": 24 * 60 * 60 * 1000,
    "year": 24 * 60 * 60 * 1000,
}
DEFAULT_FETCH_MAX_AGE_MS = FETCH_MAX_AGE_BY_FRESHNESS["any"]
