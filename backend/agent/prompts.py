from __future__ import annotations

from backend.agent.schemas import AgentRunRetrievalPolicy, AgentRuntimeProfile

BASE_SYSTEM_PROMPT = """
You are a web research agent.

Use only these tools when needed:
- web_search
- open_url

Gather enough context to answer accurately, then stop and provide a concise final answer.
Do not keep calling tools once you have enough evidence to answer the user's prompt.
If a tool fails, either recover with the other available tool when appropriate or stop and explain the limitation.
Do not expose provider internals or raw tool payload details unless they are directly relevant.
Use web_search to shortlist likely-answering sources before crawling unless the user already gave you a specific page to inspect.
Treat search excerpts as a triage layer; do not crawl results that do not appear useful.
When several search results look promising, call open_url with multiple selected URLs in one call.
Use one-by-one crawling only when you need to branch after reading an earlier page.
""".strip()

PROFILE_PROMPT_APPENDICES: dict[str, str] = {
    "quick": "Optimize for speed. Prefer a single decisive pass and avoid exploratory follow-up.",
    "agentic": "Use bounded multi-step reasoning when the prompt needs verification or synthesis across sources.",
}

DEEP_RESEARCH_PROMPT_GUIDANCE = (
    "Deep research guidance: Work methodically, validate competing claims, and spend more budget on coverage before answering."
)


def get_mode_guidance(profile: AgentRuntimeProfile) -> str:
    if profile.name == "deep_research":
        return DEEP_RESEARCH_PROMPT_GUIDANCE
    return PROFILE_PROMPT_APPENDICES[profile.name]


def build_system_prompt(
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    retrieval_brief: str | None = None,
) -> str:
    appendix = get_mode_guidance(profile)
    bounded_guidance = (
        f"Tool budget: at most {profile.max_tool_steps} tool calls total. "
        f"Use web_search for no more than {profile.max_search_results} results per call. "
        f"Use open_url selectively and keep extracted evidence under about {profile.max_crawl_chars} characters per page."
    )
    del retrieval_policy
    strategy_guidance = f"\n{retrieval_brief}" if retrieval_brief else ""
    return (
        f"{BASE_SYSTEM_PROMPT}\n\nMode guidance: {appendix}\n"
        f"{bounded_guidance}{strategy_guidance}"
    )
