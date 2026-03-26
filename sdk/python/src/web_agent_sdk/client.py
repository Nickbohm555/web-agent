from __future__ import annotations

from typing import Any

from openai import OpenAI

from .errors import WebAgentSdkError
from .schemas.agentic_search import (
    AgenticSearchRequest,
    AgenticSearchResponse,
    AgenticSearchSource,
)
from .schemas.quick_search import QuickSearchRequest, QuickSearchResponse, QuickSearchSource

QUICK_SEARCH_INSTRUCTIONS = (
    "Answer the query quickly using web search. Keep the response concise and factual."
)
AGENTIC_SEARCH_INSTRUCTIONS = (
    "Investigate the query thoroughly using web search in a single stateless run. "
    "Synthesize a complete answer and cite the strongest sources."
)
WEB_SEARCH_TOOL = {"type": "web_search"}


class WebAgentClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        openai_client: Any | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        if not self._api_key:
            raise ValueError("api_key must not be empty")
        if not self._model:
            raise ValueError("model must not be empty")
        self._openai_client = openai_client or OpenAI(api_key=self._api_key)

    def quick_search(self, query: str) -> QuickSearchResponse:
        request = QuickSearchRequest(query=query)
        response = self._create_response(
            input_text=request.query,
            instructions=QUICK_SEARCH_INSTRUCTIONS,
        )
        return QuickSearchResponse(
            query=request.query,
            answer=_read_output_text(response),
            model=self._model,
            sources=[
                QuickSearchSource(title=source["title"], url=source["url"])
                for source in _extract_sources(response)
            ],
        )

    def agentic_search(self, query: str) -> AgenticSearchResponse:
        request = AgenticSearchRequest(query=query)
        response = self._create_response(
            input_text=request.query,
            instructions=AGENTIC_SEARCH_INSTRUCTIONS,
        )
        return AgenticSearchResponse(
            query=request.query,
            answer=_read_output_text(response),
            model=self._model,
            sources=[
                AgenticSearchSource(title=source["title"], url=source["url"])
                for source in _extract_sources(response)
            ],
        )

    def _create_response(self, *, input_text: str, instructions: str) -> Any:
        try:
            return self._openai_client.responses.create(
                model=self._model,
                input=input_text,
                instructions=instructions,
                tools=[WEB_SEARCH_TOOL],
                store=False,
            )
        except Exception as exc:
            raise WebAgentSdkError(
                str(exc) or "OpenAI request failed.",
                status_code=500,
                code="OPENAI_REQUEST_FAILED",
                retryable=False,
            ) from exc


def quick_search(
    query: str,
    *,
    api_key: str,
    model: str,
) -> QuickSearchResponse:
    return WebAgentClient(api_key=api_key, model=model).quick_search(query)


def agentic_search(
    query: str,
    *,
    api_key: str,
    model: str,
) -> AgenticSearchResponse:
    return WebAgentClient(api_key=api_key, model=model).agentic_search(query)


def _read_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "")
    normalized = output_text.strip()
    if normalized:
        return normalized
    raise WebAgentSdkError(
        "OpenAI response did not include output text.",
        status_code=500,
        code="INVALID_RESPONSE",
        retryable=False,
    )


def _extract_sources(response: Any) -> list[dict[str, str]]:
    collected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for output_item in _as_list(getattr(response, "output", [])):
        for content_item in _as_list(getattr(output_item, "content", [])):
            for annotation in _as_list(getattr(content_item, "annotations", [])):
                annotation_record = _as_record(annotation)
                title = str(annotation_record.get("title", "")).strip()
                url = str(annotation_record.get("url", "")).strip()
                if not title or not url:
                    continue
                source_key = (title, url)
                if source_key in seen:
                    continue
                seen.add(source_key)
                collected.append({"title": title, "url": url})

    return collected


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}
