from __future__ import annotations

from backend.agent.schemas import AgentRunRetrievalPolicy, AgentRuntimeProfile

BASE_SYSTEM_PROMPT = """
You are a web research agent.

Use only these tools when needed:
- web_search
- web_crawl

Gather enough context to answer accurately, then stop and provide a concise final answer.
Do not keep calling tools once you have enough evidence to answer the user's prompt.
If a tool fails, either recover with the other available tool when appropriate or stop and explain the limitation.
Do not expose provider internals or raw tool payload details unless they are directly relevant.
Translate clear prompt intent like official-docs-only, latest filings, and recent coverage into concrete source and freshness constraints, and keep those constraints stable unless the user explicitly broadens them.
Use web_search to shortlist likely-answering sources before crawling unless the user already gave you a specific page to inspect.
Treat search excerpts as a triage layer; do not crawl results that do not appear useful.
When you call web_crawl, always include an objective that states the exact fact, section, or claim you need from that page.
""".strip()

PROFILE_PROMPT_APPENDICES: dict[str, str] = {
    "quick": "Optimize for speed. Prefer a single decisive pass and avoid exploratory follow-up.",
    "agentic": "Use bounded multi-step reasoning when the prompt needs verification or synthesis across sources.",
    "deep_research": "Work methodically, validate competing claims, and spend more budget on coverage before answering.",
}


def build_system_prompt(
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    retrieval_brief: str | None = None,
) -> str:
    appendix = PROFILE_PROMPT_APPENDICES[profile.name]
    bounded_guidance = (
        f"Tool budget: at most {profile.max_tool_steps} tool calls total. "
        f"Use web_search for no more than {profile.max_search_results} results per call. "
        f"Use web_crawl selectively and keep extracted evidence under about {profile.max_crawl_chars} characters per page."
    )
    policy = retrieval_policy or AgentRunRetrievalPolicy()
    policy_guidance = (
        f"Retrieval policy: freshness={policy.search.freshness}; "
        f"include domains={policy.search.include_domains or ['*']}; "
        f"exclude domains={policy.search.exclude_domains or []}; "
        f"fetch fresh={policy.fetch.fresh}; "
        f"fetch max_age_ms={policy.fetch.max_age_ms}."
    )
    strategy_guidance = f"\n{retrieval_brief}" if retrieval_brief else ""
    return (
        f"{BASE_SYSTEM_PROMPT}\n\nMode guidance: {appendix}\n"
        f"{bounded_guidance}\n{policy_guidance}{strategy_guidance}"
    )
