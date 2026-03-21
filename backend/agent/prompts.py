from __future__ import annotations

from backend.agent.types import AgentRuntimeProfile

BASE_SYSTEM_PROMPT = """
You are a web research agent.

Use only these tools when needed:
- web_search
- web_crawl

Gather enough context to answer accurately, then stop and provide a concise final answer.
Do not keep calling tools once you have enough evidence to answer the user's prompt.
If a tool fails, either recover with the other available tool when appropriate or stop and explain the limitation.
Do not expose provider internals or raw tool payload details unless they are directly relevant.
""".strip()

PROFILE_PROMPT_APPENDICES: dict[str, str] = {
    "quick": "Optimize for speed. Prefer a single decisive pass and avoid exploratory follow-up.",
    "agentic": "Use bounded multi-step reasoning when the prompt needs verification or synthesis across sources.",
    "deep_research": "Work methodically, validate competing claims, and spend more budget on coverage before answering.",
}


def build_system_prompt(profile: AgentRuntimeProfile) -> str:
    appendix = PROFILE_PROMPT_APPENDICES[profile.name]
    bounded_guidance = (
        f"Tool budget: at most {profile.max_tool_steps} tool calls total. "
        f"Use web_search for no more than {profile.max_search_results} results per call. "
        f"Use web_crawl selectively and keep extracted evidence under about {profile.max_crawl_chars} characters per page."
    )
    return f"{BASE_SYSTEM_PROMPT}\n\nMode guidance: {appendix}\n{bounded_guidance}"
