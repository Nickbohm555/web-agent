from __future__ import annotations

from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit, urlunsplit
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
from backend.app.contracts.web_crawl import WebCrawlSuccess
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


@dataclass
class RuntimeSourceRegistry:
    _sources_by_key: dict[str, AgentSourceReference]
    _aliases: dict[str, str]

    @classmethod
    def empty(cls) -> "RuntimeSourceRegistry":
        return cls(_sources_by_key={}, _aliases={})

    def register(
        self,
        *,
        url: str,
        title: str,
        snippet: str = "",
        alias_urls: tuple[str, ...] = (),
    ) -> None:
        canonical_key = _normalize_source_url(url)
        if canonical_key is None:
            return

        target_key = self._aliases.get(canonical_key, canonical_key)
        related_keys = {
            canonical_key,
            *(key for key in (_normalize_source_url(alias) for alias in alias_urls) if key is not None),
        }
        existing_source_keys = {
            self._aliases.get(key, key)
            for key in related_keys
        }

        source = self._sources_by_key.get(target_key)
        if source is None:
            source = AgentSourceReference(title=title, url=canonical_key, snippet=snippet)
        else:
            source = source.model_copy(
                update=_merge_source_metadata(
                    source=source,
                    incoming_title=title,
                    incoming_url=canonical_key,
                    incoming_snippet=snippet,
                )
            )

        self._sources_by_key[target_key] = source
        self._merge_alias_sources(target_key, existing_source_keys)
        for key in related_keys:
            self._aliases[key] = target_key

    def _merge_alias_sources(self, target_key: str, related_source_keys: set[str]) -> None:
        target_source = self._sources_by_key[target_key]
        for source_key in tuple(related_source_keys):
            if source_key == target_key or source_key not in self._sources_by_key:
                continue
            target_source = target_source.model_copy(
                update=_merge_source_metadata(
                    source=target_source,
                    incoming_title=self._sources_by_key[source_key].title,
                    incoming_url=str(self._sources_by_key[source_key].url),
                    incoming_snippet=self._sources_by_key[source_key].snippet,
                )
            )
            self._sources_by_key[target_key] = target_source
            del self._sources_by_key[source_key]
            for alias, mapped_key in tuple(self._aliases.items()):
                if mapped_key == source_key:
                    self._aliases[alias] = target_key

    def source_lookup(self) -> dict[str, AgentSourceReference]:
        lookup = _build_source_lookup(self.sources())
        for alias_key, source_key in self._aliases.items():
            source = self._sources_by_key.get(source_key)
            if source is not None:
                lookup[alias_key] = source
        return lookup

    def sources(self) -> list[AgentSourceReference]:
        return sorted(self._sources_by_key.values(), key=lambda source: source.source_id)


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
        source_registry = _extract_sources(raw_result)
        sources = source_registry.sources()
        return AgentRunResult(
            run_id=run_id,
            status="completed",
            final_answer=_extract_final_answer(raw_result, source_registry.source_lookup()),
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
        sources=_extract_search_sources(response).sources(),
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
    source_lookup: dict[str, AgentSourceReference] | None = None,
) -> AgentStructuredAnswer:
    source_lookup = source_lookup or {}

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


def _extract_sources(raw_result: Any) -> RuntimeSourceRegistry:
    registry = RuntimeSourceRegistry.empty()
    if not isinstance(raw_result, dict):
        return registry

    direct_sources = raw_result.get("sources")
    if isinstance(direct_sources, list):
        _register_source_payload(registry, direct_sources)

    direct_final_answer = raw_result.get("final_answer")
    if isinstance(direct_final_answer, dict):
        _register_citation_sources(registry, direct_final_answer.get("citations"))

    messages = raw_result.get("messages")
    if isinstance(messages, list):
        for message in messages:
            source_payload = _coerce_message_sources(message)
            if source_payload:
                _register_source_payload(registry, source_payload)
            _register_citation_sources(
                registry,
                _coerce_message_typed_field(message, "citations", list),
            )
            _register_message_tool_sources(registry, message)

    return registry


def _coerce_message_sources(message: Any) -> list[AgentSourceReference]:
    source_payload = _coerce_message_typed_field(message, "sources", list)
    if isinstance(source_payload, list):
        return _validate_sources(source_payload)

    return []


def _register_source_payload(
    registry: RuntimeSourceRegistry,
    source_payload: list[Any] | list[AgentSourceReference],
) -> None:
    for source in _validate_sources(list(source_payload)):
        registry.register(
            url=str(source.url),
            title=source.title,
            snippet=source.snippet,
        )


def _register_citation_sources(
    registry: RuntimeSourceRegistry,
    citation_payload: Any,
) -> None:
    if not isinstance(citation_payload, list):
        return

    for entry in citation_payload:
        if not isinstance(entry, dict):
            continue

        url = entry.get("url")
        if url is None:
            continue

        title = str(entry.get("title") or url).strip()
        if not title:
            continue

        registry.register(
            url=str(url),
            title=title,
        )


def _register_message_tool_sources(registry: RuntimeSourceRegistry, message: Any) -> None:
    tool_name = _coerce_message_tool_name(message)
    if tool_name not in CANONICAL_TOOL_NAMES:
        return

    payload = _coerce_message_tool_payload(message)
    if not isinstance(payload, dict):
        return

    if tool_name == "web_search":
        try:
            response = WebSearchResponse.model_validate(payload)
        except ValidationError:
            return
        _merge_search_sources_into_registry(registry, response)
        return

    try:
        crawl_result = WebCrawlSuccess.model_validate(payload)
    except ValidationError:
        return

    source_record = crawl_result.to_source_record()
    registry.register(
        url=source_record["url"],
        title=source_record["title"],
        snippet=source_record["snippet"],
        alias_urls=crawl_result.source_alias_urls(),
    )


def _coerce_message_final_answer(message: Any) -> dict[str, Any] | None:
    return _coerce_message_typed_field(message, "final_answer", dict)


def _validate_sources(source_payload: list[Any]) -> list[AgentSourceReference]:
    sources: list[AgentSourceReference] = []
    for entry in source_payload:
        try:
            sources.append(AgentSourceReference.model_validate(entry))
        except Exception:
            continue
    return sources


def _extract_search_sources(response: WebSearchResponse) -> RuntimeSourceRegistry:
    registry = RuntimeSourceRegistry.empty()
    _merge_search_sources_into_registry(registry, response)
    return registry


def _merge_search_sources_into_registry(
    registry: RuntimeSourceRegistry,
    response: WebSearchResponse,
) -> None:
    for result in response.results[:3]:
        source_record = result.to_source_record()
        registry.register(
            url=source_record["url"],
            title=source_record["title"],
            snippet=source_record["snippet"],
        )


def _build_source_lookup(
    sources: list[AgentSourceReference],
) -> dict[str, AgentSourceReference]:
    lookup: dict[str, AgentSourceReference] = {}
    for source in sources:
        lookup[source.source_id] = source
        lookup[str(source.url)] = source
        normalized_url = _normalize_source_url(str(source.url))
        if normalized_url is not None:
            lookup[normalized_url] = source
    return lookup


def _coerce_message_tool_name(message: Any) -> str | None:
    return _coerce_named_message_field(message, ("name", "tool_name")) or _coerce_named_message_field(
        _message_additional_kwargs(message),
        ("name", "tool_name"),
    )


def _coerce_message_tool_payload(message: Any) -> dict[str, Any] | None:
    payload = _coerce_message_payload_mapping(message)
    if isinstance(payload, dict):
        return payload

    return _coerce_message_payload_mapping(_message_additional_kwargs(message))


def _decode_json_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    try:
        decoded = json.loads(value)
    except ValueError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _coerce_message_citations(
    message: Any,
    source_lookup: dict[str, AgentSourceReference],
) -> list[AgentAnswerCitation]:
    citation_payload = _coerce_message_typed_field(message, "citations", list)
    if isinstance(citation_payload, list):
        return _validate_citations(citation_payload, source_lookup)

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
    citations: list[AgentAnswerCitation] = []
    for entry in citation_payload:
        hydrated = _hydrate_citation(entry, source_lookup)
        if not isinstance(hydrated, dict):
            citations.append(AgentAnswerCitation.model_validate(hydrated))
            continue

        if not _citation_references_known_source(hydrated, source_lookup):
            raise ValueError("citation must reference a policy-cleared source")

        citations.append(AgentAnswerCitation.model_validate(hydrated))

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
        lookup_key = _normalize_source_url(str(source_url)) or str(source_url).strip()

    source = source_lookup.get(lookup_key) if lookup_key else None
    if source is not None:
        citation["source_id"] = source.source_id
        citation["title"] = source.title
        citation["url"] = str(source.url)

    return citation


def _citation_references_known_source(
    citation: dict[str, Any],
    source_lookup: dict[str, AgentSourceReference],
) -> bool:
    source_id = citation.get("source_id")
    if isinstance(source_id, str) and source_id.strip() and source_id.strip() in source_lookup:
        return True

    source_url = citation.get("url")
    if source_url is None:
        return False

    normalized_source_url = _normalize_source_url(str(source_url))
    if normalized_source_url is None:
        return False

    return normalized_source_url in source_lookup


def _merge_source_metadata(
    *,
    source: AgentSourceReference,
    incoming_title: str,
    incoming_url: str,
    incoming_snippet: str,
) -> dict[str, str]:
    return {
        "title": _select_preferred_title(
            existing_title=source.title,
            existing_url=str(source.url),
            incoming_title=incoming_title,
            incoming_url=incoming_url,
        ),
        "url": source.url,
        "snippet": _select_preferred_snippet(source.snippet, incoming_snippet),
    }


def _select_preferred_title(
    *,
    existing_title: str,
    existing_url: str,
    incoming_title: str,
    incoming_url: str,
) -> str:
    if not existing_title.strip():
        return incoming_title
    if not incoming_title.strip():
        return existing_title
    if _looks_like_fallback_title(existing_title, existing_url) and not _looks_like_fallback_title(
        incoming_title, incoming_url
    ):
        return incoming_title
    if _looks_like_fallback_title(incoming_title, incoming_url):
        return existing_title
    return incoming_title if len(incoming_title) >= len(existing_title) else existing_title


def _select_preferred_snippet(existing_snippet: str, incoming_snippet: str) -> str:
    existing = existing_snippet.strip()
    incoming = incoming_snippet.strip()
    if not existing:
        return incoming
    if not incoming:
        return existing
    return incoming if len(incoming) >= len(existing) else existing


def _looks_like_fallback_title(title: str, url: str) -> bool:
    normalized_title = title.strip().lower()
    normalized_url = url.strip().lower()
    if normalized_title == normalized_url:
        return True

    normalized_title_url = _normalize_source_url(title)
    normalized_url_key = _normalize_source_url(url)
    if normalized_title_url is not None and normalized_title_url == normalized_url_key:
        return True

    normalized_key = normalized_url_key
    if normalized_key is None:
        return False

    parsed = urlsplit(normalized_key)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.strip("/").lower()
    return normalized_title in {hostname, f"{hostname}/{path}".strip("/")}


def _normalize_source_url(url: str | None) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None

    stripped_url = url.strip()
    parsed = urlsplit(stripped_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return None

    if parsed.username or parsed.password:
        return None

    hostname = (parsed.hostname or "").lower()
    if not hostname or not hostname.replace(".", ""):
        return None

    port = parsed.port
    netloc = hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def _coerce_message_content(message: Any) -> str:
    return _normalize_content_value(_message_field(message, "content"))


def _message_field(message: Any, key: str) -> Any:
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)


def _message_additional_kwargs(message: Any) -> dict[str, Any] | None:
    additional_kwargs = _message_field(message, "additional_kwargs")
    return additional_kwargs if isinstance(additional_kwargs, dict) else None


def _message_additional_field(message: Any, key: str) -> Any:
    additional_kwargs = _message_additional_kwargs(message)
    return additional_kwargs.get(key) if additional_kwargs is not None else None


def _coerce_message_typed_field(
    message: Any,
    key: str,
    expected_type: type[Any],
) -> Any:
    value = _message_field(message, key)
    if isinstance(value, expected_type):
        return value

    value = _message_additional_field(message, key)
    if isinstance(value, expected_type):
        return value

    return None


def _coerce_named_message_field(message: Any, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _message_field(message, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coerce_message_payload_mapping(message: Any) -> dict[str, Any] | None:
    for key in ("tool_output", "artifact", "payload"):
        payload = _message_field(message, key)
        if isinstance(payload, dict):
            return payload

    return _decode_json_object(_message_field(message, "content"))


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
