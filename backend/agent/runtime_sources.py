from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from backend.agent.runtime_constants import CANONICAL_TOOL_NAMES
from backend.agent.schemas import (
    AgentAnswerBasis,
    AgentAnswerCitation,
    AgentSourceReference,
    AgentStructuredAnswer,
)
from backend.app.tools.schemas.tool_errors import ToolErrorEnvelope
from backend.app.tools.schemas.web_crawl import WebCrawlSuccess
from backend.app.tools.schemas.web_crawl_batch import WebCrawlBatchSuccess
from backend.app.tools.schemas.web_search import WebSearchResponse


WEB_SEARCH_RESULT_REPR_PATTERN = re.compile(
    r"WebSearchResult\("
    r"title=(?P<title>'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"), "
    r"url=HttpUrl\((?P<url>'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")\), "
    r"snippet=(?P<snippet>'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")",
    re.DOTALL,
)
WEB_CRAWL_FINAL_URL_REPR_PATTERN = re.compile(
    r"final_url=HttpUrl\((?P<url>'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")\)"
)
WEB_CRAWL_TEXT_REPR_PATTERN = re.compile(
    r"text=(?P<text>'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")",
    re.DOTALL,
)
PLACEHOLDER_ANSWER_PATTERN = re.compile(
    r"\b(?:sorry[, ]+)?(?:i\s+)?need more steps to process this request\b",
    re.IGNORECASE,
)


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
        canonical_key = normalize_source_url(url)
        if canonical_key is None:
            return

        target_key = self._aliases.get(canonical_key, canonical_key)
        related_keys = {
            canonical_key,
            *(key for key in (normalize_source_url(alias) for alias in alias_urls) if key is not None),
        }
        existing_source_keys = {self._aliases.get(key, key) for key in related_keys}

        source = self._sources_by_key.get(target_key)
        if source is None:
            source = AgentSourceReference(title=title, url=canonical_key, snippet=snippet)
        else:
            source = source.model_copy(
                update=merge_source_metadata(
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
                update=merge_source_metadata(
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
        lookup = build_source_lookup(self.sources())
        for alias_key, source_key in self._aliases.items():
            source = self._sources_by_key.get(source_key)
            if source is not None:
                lookup[alias_key] = source
        return lookup

    def sources(self) -> list[AgentSourceReference]:
        return sorted(self._sources_by_key.values(), key=lambda source: source.source_id)


def extract_final_answer(
    raw_result: Any,
    source_lookup: dict[str, AgentSourceReference] | None = None,
) -> AgentStructuredAnswer:
    source_lookup = source_lookup or {}

    if isinstance(raw_result, str):
        return AgentStructuredAnswer(text=raw_result.strip())

    if isinstance(raw_result, dict):
        direct_final_answer = raw_result.get("final_answer")
        if isinstance(direct_final_answer, dict):
            return validate_structured_answer(direct_final_answer, source_lookup)

        messages = raw_result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                direct_final_answer = coerce_message_final_answer(message)
                if isinstance(direct_final_answer, dict):
                    return validate_structured_answer(direct_final_answer, source_lookup)

                content = coerce_message_content(message)
                if content:
                    citations = coerce_message_citations(message, source_lookup)
                    return AgentStructuredAnswer(text=content, citations=citations)

        output = raw_result.get("output")
        if isinstance(output, str) and output.strip():
            direct_citations = raw_result.get("citations")
            if isinstance(direct_citations, list):
                return AgentStructuredAnswer(
                    text=output.strip(),
                    citations=validate_citations(direct_citations, source_lookup),
                )
            return AgentStructuredAnswer(text=output.strip())

    raise ValueError("Agent runtime did not return a final answer")


def replace_placeholder_answer_with_source_summary(
    answer: AgentStructuredAnswer,
    *,
    sources: list[AgentSourceReference],
) -> AgentStructuredAnswer:
    if not is_placeholder_answer(answer.text) or not sources:
        return answer

    return AgentStructuredAnswer(text=summarize_sources_as_answer(sources))


def is_placeholder_answer(text: str) -> bool:
    return bool(PLACEHOLDER_ANSWER_PATTERN.search(text.strip()))


def summarize_sources_as_answer(sources: list[AgentSourceReference]) -> str:
    top_sources = sources[:3]
    summaries: list[str] = []
    for source in top_sources:
        snippet = source.snippet.rstrip(".").strip()
        if snippet:
            summaries.append(f"{source.title}: {snippet}.")
        else:
            summaries.append(f"{source.title}: {source.url}.")

    source_lines = "\n".join(f"- {source.title}: {source.url}" for source in top_sources)
    return f"{' '.join(summaries)}\n\nSources:\n{source_lines}"


def count_tool_calls(raw_result: Any) -> int:
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


def extract_crawl_error(raw_result: Any) -> ToolErrorEnvelope | None:
    if not isinstance(raw_result, dict):
        return None

    messages = raw_result.get("messages")
    if not isinstance(messages, list):
        return None

    crawl_error: ToolErrorEnvelope | None = None
    for message in messages:
        if coerce_message_tool_name(message) != "open_url":
            continue

        payload = coerce_message_tool_payload(message)
        if not isinstance(payload, dict):
            continue

        if "error" in payload:
            try:
                crawl_error = ToolErrorEnvelope.model_validate(payload)
            except ValidationError:
                continue
            continue

        try:
            WebCrawlSuccess.model_validate(payload)
        except ValidationError:
            continue

        crawl_error = None

    return crawl_error


def has_zero_evidence_crawl_success(raw_result: Any) -> bool:
    if not isinstance(raw_result, dict):
        return False

    messages = raw_result.get("messages")
    if not isinstance(messages, list):
        return False

    for message in messages:
        if coerce_message_tool_name(message) != "open_url":
            continue

        payload = coerce_message_tool_payload(message)
        if not isinstance(payload, dict) or "error" in payload:
            continue

        try:
            crawl_result = WebCrawlSuccess.model_validate(payload)
        except ValidationError:
            continue

        if not crawl_result.has_evidence():
            return True

    return False


def extract_sources(raw_result: Any) -> RuntimeSourceRegistry:
    registry = RuntimeSourceRegistry.empty()
    if not isinstance(raw_result, dict):
        return registry

    direct_sources = raw_result.get("sources")
    if isinstance(direct_sources, list):
        register_source_payload(registry, direct_sources)

    direct_final_answer = raw_result.get("final_answer")
    if isinstance(direct_final_answer, dict):
        register_citation_sources(registry, direct_final_answer.get("citations"))

    messages = raw_result.get("messages")
    if isinstance(messages, list):
        for message in messages:
            source_payload = coerce_message_sources(message)
            if source_payload:
                register_source_payload(registry, source_payload)
            register_citation_sources(
                registry,
                coerce_message_typed_field(message, "citations", list),
            )
            register_message_tool_sources(registry, message)

    return registry


def coerce_message_sources(message: Any) -> list[AgentSourceReference]:
    source_payload = coerce_message_typed_field(message, "sources", list)
    if isinstance(source_payload, list):
        return validate_sources(source_payload)
    return []


def register_source_payload(
    registry: RuntimeSourceRegistry,
    source_payload: list[Any] | list[AgentSourceReference],
) -> None:
    for source in validate_sources(list(source_payload)):
        registry.register(
            url=str(source.url),
            title=source.title,
            snippet=source.snippet,
        )


def register_citation_sources(
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


def register_message_tool_sources(registry: RuntimeSourceRegistry, message: Any) -> None:
    tool_name = coerce_message_tool_name(message)
    if tool_name not in CANONICAL_TOOL_NAMES:
        return

    payload = coerce_message_tool_payload(message)
    content = coerce_message_content(message)
    if not isinstance(payload, dict):
        merge_repr_encoded_tool_sources_into_registry(
            registry,
            tool_name=tool_name,
            content=content,
        )
        return

    if tool_name == "web_search":
        try:
            response = WebSearchResponse.model_validate(payload)
        except ValidationError:
            merge_repr_encoded_tool_sources_into_registry(
                registry,
                tool_name=tool_name,
                content=content,
            )
            return
        merge_search_sources_into_registry(registry, response)
        return

    try:
        batch_result = WebCrawlBatchSuccess.model_validate(payload)
    except ValidationError:
        batch_result = None

    if batch_result is not None:
        for item in batch_result.items:
            if item.result is None:
                continue
            source_record = item.result.to_source_record()
            registry.register(
                url=source_record["url"],
                title=source_record["title"],
                snippet=source_record["snippet"],
                alias_urls=item.result.source_alias_urls(),
            )
        return

    try:
        crawl_result = WebCrawlSuccess.model_validate(payload)
    except ValidationError:
        merge_repr_encoded_tool_sources_into_registry(
            registry,
            tool_name=tool_name,
            content=content,
        )
        return

    if not crawl_result.has_evidence():
        return

    source_record = crawl_result.to_source_record()
    registry.register(
        url=source_record["url"],
        title=source_record["title"],
        snippet=source_record["snippet"],
        alias_urls=crawl_result.source_alias_urls(),
    )


def merge_repr_encoded_tool_sources_into_registry(
    registry: RuntimeSourceRegistry,
    *,
    tool_name: str,
    content: str,
) -> None:
    if not content:
        return

    if tool_name == "web_search":
        for source in extract_search_sources_from_repr(content):
            registry.register(
                url=source["url"],
                title=source["title"],
                snippet=source["snippet"],
            )
        return

    if tool_name == "open_url":
        source = extract_crawl_source_from_repr(content)
        if source is None:
            return
        registry.register(
            url=source["url"],
            title=source["title"],
            snippet=source["snippet"],
        )


def extract_search_sources_from_repr(content: str) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for match in WEB_SEARCH_RESULT_REPR_PATTERN.finditer(content):
        title = decode_repr_string(match.group("title"))
        url = decode_repr_string(match.group("url"))
        snippet = decode_repr_string(match.group("snippet"))
        if title is None or url is None or snippet is None:
            continue
        sources.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )
    return sources


def extract_crawl_source_from_repr(content: str) -> dict[str, str] | None:
    url_match = WEB_CRAWL_FINAL_URL_REPR_PATTERN.search(content)
    if url_match is None:
        return None

    url = decode_repr_string(url_match.group("url"))
    if url is None:
        return None

    text_match = WEB_CRAWL_TEXT_REPR_PATTERN.search(content)
    text = decode_repr_string(text_match.group("text")) if text_match is not None else ""
    snippet = (text or "").strip()[:280]

    return {
        "title": derive_source_title_from_url(url),
        "url": url,
        "snippet": snippet,
    }


def decode_repr_string(value: str) -> str | None:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, str) else None


def derive_source_title_from_url(url: str) -> str:
    parsed = urlsplit(url)
    hostname = parsed.hostname or url
    path = parsed.path.rstrip("/")
    if not path or path == "/":
        return hostname
    path_tail = path.split("/")[-1]
    return f"{hostname}{('/' + path_tail) if path_tail else ''}"


def coerce_message_final_answer(message: Any) -> dict[str, Any] | None:
    return coerce_message_typed_field(message, "final_answer", dict)


def validate_sources(source_payload: list[Any]) -> list[AgentSourceReference]:
    sources: list[AgentSourceReference] = []
    for entry in source_payload:
        try:
            sources.append(AgentSourceReference.model_validate(entry))
        except Exception:
            continue
    return sources


def extract_search_sources(response: WebSearchResponse) -> RuntimeSourceRegistry:
    registry = RuntimeSourceRegistry.empty()
    merge_search_sources_into_registry(registry, response)
    return registry


def merge_search_sources_into_registry(
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


def build_source_lookup(
    sources: list[AgentSourceReference],
) -> dict[str, AgentSourceReference]:
    lookup: dict[str, AgentSourceReference] = {}
    for source in sources:
        lookup[source.source_id] = source
        lookup[str(source.url)] = source
        normalized_url = normalize_source_url(str(source.url))
        if normalized_url is not None:
            lookup[normalized_url] = source
    return lookup


def coerce_message_tool_name(message: Any) -> str | None:
    return coerce_named_message_field(message, ("name", "tool_name")) or coerce_named_message_field(
        message_additional_kwargs(message),
        ("name", "tool_name"),
    )


def coerce_message_tool_payload(message: Any) -> dict[str, Any] | None:
    payload = coerce_message_payload_mapping(message)
    if isinstance(payload, dict):
        return payload
    return coerce_message_payload_mapping(message_additional_kwargs(message))


def decode_json_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    try:
        decoded = json.loads(value)
    except ValueError:
        return None
    return decoded if isinstance(decoded, dict) else None


def coerce_message_citations(
    message: Any,
    source_lookup: dict[str, AgentSourceReference],
) -> list[AgentAnswerCitation]:
    citation_payload = coerce_message_typed_field(message, "citations", list)
    if isinstance(citation_payload, list):
        return validate_citations(citation_payload, source_lookup)
    return []


def validate_structured_answer(
    payload: dict[str, Any],
    source_lookup: dict[str, AgentSourceReference],
) -> AgentStructuredAnswer:
    answer_payload = dict(payload)
    citations = answer_payload.get("citations")
    if isinstance(citations, list):
        answer_payload["citations"] = validate_citations(citations, source_lookup)

    basis = answer_payload.get("basis")
    if isinstance(basis, list):
        answer_payload["basis"] = validate_basis_items(basis, source_lookup)

    return AgentStructuredAnswer.model_validate(answer_payload)


def validate_basis_items(
    basis_payload: list[Any],
    source_lookup: dict[str, AgentSourceReference],
) -> list[AgentAnswerBasis]:
    basis_items: list[AgentAnswerBasis] = []
    for entry in basis_payload:
        if not isinstance(entry, dict):
            basis_items.append(AgentAnswerBasis.model_validate(entry))
            continue

        hydrated_entry = dict(entry)
        citations = hydrated_entry.get("citations")
        if isinstance(citations, list):
            hydrated_entry["citations"] = validate_citations(citations, source_lookup)
        basis_items.append(AgentAnswerBasis.model_validate(hydrated_entry))

    return basis_items


def validate_citations(
    citation_payload: list[Any],
    source_lookup: dict[str, AgentSourceReference],
) -> list[AgentAnswerCitation]:
    citations: list[AgentAnswerCitation] = []
    for entry in citation_payload:
        hydrated = hydrate_citation(entry, source_lookup)
        if not isinstance(hydrated, dict):
            citations.append(AgentAnswerCitation.model_validate(hydrated))
            continue

        if not citation_references_known_source(hydrated, source_lookup):
            raise ValueError("citation must reference a policy-cleared source")

        citations.append(AgentAnswerCitation.model_validate(hydrated))

    citations.sort(key=lambda citation: (citation.start_index, citation.end_index, citation.source_id))
    return citations


def hydrate_citation(
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
        lookup_key = normalize_source_url(str(source_url)) or str(source_url).strip()

    source = source_lookup.get(lookup_key) if lookup_key else None
    if source is not None:
        citation["source_id"] = source.source_id
        citation["title"] = source.title
        citation["url"] = str(source.url)

    return citation


def citation_references_known_source(
    citation: dict[str, Any],
    source_lookup: dict[str, AgentSourceReference],
) -> bool:
    source_id = citation.get("source_id")
    if isinstance(source_id, str) and source_id.strip() and source_id.strip() in source_lookup:
        return True

    source_url = citation.get("url")
    if source_url is None:
        return False

    normalized_source_url = normalize_source_url(str(source_url))
    if normalized_source_url is None:
        return False

    return normalized_source_url in source_lookup


def merge_source_metadata(
    *,
    source: AgentSourceReference,
    incoming_title: str,
    incoming_url: str,
    incoming_snippet: str,
) -> dict[str, str]:
    return {
        "title": select_preferred_title(
            existing_title=source.title,
            existing_url=str(source.url),
            incoming_title=incoming_title,
            incoming_url=incoming_url,
        ),
        "url": source.url,
        "snippet": select_preferred_snippet(source.snippet, incoming_snippet),
    }


def select_preferred_title(
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
    if looks_like_fallback_title(existing_title, existing_url) and not looks_like_fallback_title(
        incoming_title, incoming_url
    ):
        return incoming_title
    if looks_like_fallback_title(incoming_title, incoming_url):
        return existing_title
    return incoming_title if len(incoming_title) >= len(existing_title) else existing_title


def select_preferred_snippet(existing_snippet: str, incoming_snippet: str) -> str:
    existing = existing_snippet.strip()
    incoming = incoming_snippet.strip()
    if not existing:
        return incoming
    if not incoming:
        return existing
    return incoming if len(incoming) >= len(existing) else existing


def looks_like_fallback_title(title: str, url: str) -> bool:
    normalized_title = title.strip().lower()
    normalized_url = url.strip().lower()
    if normalized_title == normalized_url:
        return True

    normalized_title_url = normalize_source_url(title)
    normalized_url_key = normalize_source_url(url)
    if normalized_title_url is not None and normalized_title_url == normalized_url_key:
        return True

    if normalized_url_key is None:
        return False

    parsed = urlsplit(normalized_url_key)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.strip("/").lower()
    return normalized_title in {hostname, f"{hostname}/{path}".strip("/")}


def normalize_source_url(url: str | None) -> str | None:
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


def coerce_message_content(message: Any) -> str:
    return normalize_content_value(message_field(message, "content"))


def message_field(message: Any, key: str) -> Any:
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)


def message_additional_kwargs(message: Any) -> dict[str, Any] | None:
    additional_kwargs = message_field(message, "additional_kwargs")
    return additional_kwargs if isinstance(additional_kwargs, dict) else None


def message_additional_field(message: Any, key: str) -> Any:
    additional_kwargs = message_additional_kwargs(message)
    return additional_kwargs.get(key) if additional_kwargs is not None else None


def coerce_message_typed_field(
    message: Any,
    key: str,
    expected_type: type[Any],
) -> Any:
    value = message_field(message, key)
    if isinstance(value, expected_type):
        return value

    value = message_additional_field(message, key)
    if isinstance(value, expected_type):
        return value

    return None


def coerce_named_message_field(message: Any, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = message_field(message, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def coerce_message_payload_mapping(message: Any) -> dict[str, Any] | None:
    for key in ("tool_output", "artifact", "payload"):
        payload = message_field(message, key)
        if isinstance(payload, dict):
            return payload

    return decode_json_object(message_field(message, "content"))


def normalize_content_value(content: Any) -> str:
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
