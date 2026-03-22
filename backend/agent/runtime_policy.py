from __future__ import annotations

from typing import Any

from backend.agent.runtime_constants import (
    DEFAULT_FETCH_MAX_AGE_MS,
    DOMAIN_PATTERN,
    FETCH_MAX_AGE_BY_FRESHNESS,
    MONTH_PATTERN,
    OFFICIAL_SOURCE_PATTERN,
    PROMPT_DOMAIN_HINTS,
    SEC_FILING_PATTERN,
    TODAY_PATTERN,
    WEEK_PATTERN,
    YEAR_PATTERN,
)
from backend.agent.schemas import (
    AgentRetrievalFreshness,
    AgentRunRetrievalFetchPolicy,
    AgentRunRetrievalPolicy,
    AgentRunRetrievalSearchPolicy,
    AgentRuntimeProfile,
)


def resolve_effective_retrieval_policy(
    *,
    prompt: str,
    retrieval_policy: AgentRunRetrievalPolicy | None,
) -> AgentRunRetrievalPolicy:
    inferred_policy = infer_retrieval_policy_from_prompt(prompt)
    if retrieval_policy is None:
        return inferred_policy

    return AgentRunRetrievalPolicy.model_validate(
        {
            "search": merge_search_policy(
                explicit_policy=retrieval_policy.search,
                inferred_policy=inferred_policy.search,
            ),
            "fetch": merge_fetch_policy(
                explicit_policy=retrieval_policy.fetch,
                inferred_policy=inferred_policy.fetch,
            ),
        }
    )


def infer_retrieval_policy_from_prompt(prompt: str) -> AgentRunRetrievalPolicy:
    normalized_prompt = prompt.strip()
    inferred_freshness = infer_prompt_freshness(normalized_prompt)
    inferred_domains = infer_prompt_include_domains(normalized_prompt)
    return AgentRunRetrievalPolicy.model_validate(
        {
            "search": {
                "freshness": inferred_freshness,
                "include_domains": inferred_domains,
            },
            "fetch": {
                "max_age_ms": FETCH_MAX_AGE_BY_FRESHNESS[inferred_freshness],
                "fresh": inferred_freshness != "any",
            },
        }
    )


def merge_search_policy(
    *,
    explicit_policy: AgentRunRetrievalSearchPolicy,
    inferred_policy: AgentRunRetrievalSearchPolicy,
) -> dict[str, Any]:
    return {
        "country": explicit_policy.country or inferred_policy.country,
        "language": explicit_policy.language or inferred_policy.language,
        "freshness": (
            explicit_policy.freshness
            if explicit_policy.freshness != "any"
            else inferred_policy.freshness
        ),
        "include_domains": explicit_policy.include_domains or inferred_policy.include_domains,
        "exclude_domains": explicit_policy.exclude_domains or inferred_policy.exclude_domains,
    }


def merge_fetch_policy(
    *,
    explicit_policy: AgentRunRetrievalFetchPolicy,
    inferred_policy: AgentRunRetrievalFetchPolicy,
) -> dict[str, Any]:
    return {
        "max_age_ms": (
            explicit_policy.max_age_ms
            if explicit_policy.max_age_ms != DEFAULT_FETCH_MAX_AGE_MS
            else inferred_policy.max_age_ms
        ),
        "fresh": explicit_policy.fresh or inferred_policy.fresh,
    }


def infer_prompt_freshness(prompt: str) -> AgentRetrievalFreshness:
    if not prompt:
        return "any"
    if TODAY_PATTERN.search(prompt):
        return "day"
    if MONTH_PATTERN.search(prompt) or SEC_FILING_PATTERN.search(prompt):
        return "month"
    if YEAR_PATTERN.search(prompt):
        return "year"
    if WEEK_PATTERN.search(prompt):
        return "week"
    return "any"


def infer_prompt_include_domains(prompt: str) -> list[str]:
    if not prompt:
        return []

    has_sec_filing_hint = bool(SEC_FILING_PATTERN.search(prompt))
    explicit_domains = DOMAIN_PATTERN.findall(prompt)
    hinted_domains = [
        domain
        for pattern, domains in PROMPT_DOMAIN_HINTS
        if pattern.search(prompt)
        for domain in domains
    ]
    should_scope_to_official_sources = bool(
        OFFICIAL_SOURCE_PATTERN.search(prompt) or has_sec_filing_hint
    )
    if not should_scope_to_official_sources and not explicit_domains:
        return []

    inferred_domains = [
        *(["sec.gov"] if has_sec_filing_hint else []),
        *explicit_domains,
        *hinted_domains,
    ]
    normalized_domains = AgentRunRetrievalPolicy.model_validate(
        {"search": {"include_domains": inferred_domains}}
    ).search.include_domains
    return collapse_domains(normalized_domains)


def collapse_domains(domains: list[str]) -> list[str]:
    collapsed: list[str] = []
    for domain in sorted(domains):
        if any(domain == existing or domain.endswith(f".{existing}") for existing in collapsed):
            continue
        collapsed = [
            existing
            for existing in collapsed
            if not existing.endswith(f".{domain}")
        ]
        collapsed.append(domain)
    return collapsed


def build_runtime_config(
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


def build_retrieval_brief(
    *,
    prompt: str,
    profile: AgentRuntimeProfile,
    retrieval_policy: AgentRunRetrievalPolicy,
) -> str:
    normalized_prompt = " ".join(prompt.strip().split())
    if not normalized_prompt:
        return ""

    return (
        "Retrieval strategy:\n"
        f"- Answer objective: {normalized_prompt}\n"
        f"- Search plan: {build_search_plan(retrieval_policy)}\n"
        f"- Crawl plan: {build_crawl_plan(profile)}\n"
        f"- Source plan: {build_source_plan(retrieval_policy)}\n"
        f"- Mode plan: {build_mode_plan(profile)}"
    )


def build_search_plan(retrieval_policy: AgentRunRetrievalPolicy) -> str:
    scope_terms: list[str] = []
    if retrieval_policy.search.freshness != "any":
        scope_terms.append(f"prefer {retrieval_policy.search.freshness}-fresh sources")
    if retrieval_policy.search.include_domains:
        scope_terms.append("stay within " + ", ".join(retrieval_policy.search.include_domains))
    if retrieval_policy.search.exclude_domains:
        scope_terms.append("avoid " + ", ".join(retrieval_policy.search.exclude_domains))
    if not scope_terms:
        return (
            "start with narrow web_search queries that restate the exact fact or comparison"
            " you need, then use result excerpts to decide whether a page is worth opening"
        )
    return (
        "start with narrow web_search queries that restate the exact fact or comparison"
        f" you need and {'; '.join(scope_terms)}"
    )


def build_crawl_plan(profile: AgentRuntimeProfile) -> str:
    if profile.name == "deep_research":
        return (
            "crawl only high-value pages, and every web_crawl call must include an objective"
            " tied to the claim, section, or comparison you need to verify"
        )
    return (
        "crawl only pages whose search excerpts look promising, and every web_crawl call"
        " must include an objective describing the exact evidence needed from that page"
    )


def build_source_plan(retrieval_policy: AgentRunRetrievalPolicy) -> str:
    if retrieval_policy.search.include_domains:
        return (
            "keep source selection inside the allowed domains and do not broaden scope unless"
            " the user asks"
        )
    if retrieval_policy.search.exclude_domains:
        return "exclude blocked domains while favoring sources that directly answer the prompt"
    return "favor sources that directly answer the prompt over broad background reading"


def build_mode_plan(profile: AgentRuntimeProfile) -> str:
    if profile.name == "agentic":
        return "use a small number of decisive searches and only enough crawls to answer accurately"
    if profile.name == "deep_research":
        return "compare multiple promising sources, validate conflicts, and use objectives that separate sub-questions"
    return "optimize for one decisive search pass"
