from __future__ import annotations

from typing import Any, Callable

from openai import OpenAI

from web_agent_backend.responses import OpenAIResponsesBackend

from .schemas.agentic_search import (
    AgenticSearchRequest,
    AgenticSearchResponse,
    AgenticSearchSource,
)
from .schemas.quick_search import QuickSearchRequest, QuickSearchResponse, QuickSearchSource

OpenAIClientFactory = Callable[[Any], Any]


class WebAgentClient:
    def __init__(
        self,
        *,
        chat_model: Any,
        openai_client_factory: OpenAIClientFactory | None = None,
    ) -> None:
        self._backend = OpenAIResponsesBackend.from_chat_model(
            chat_model,
            openai_client_factory=openai_client_factory or _build_openai_client,
        )

    def quick_search(self, query: str) -> QuickSearchResponse:
        request = QuickSearchRequest(query=query)
        result = self._backend.quick_search(request.query)
        return QuickSearchResponse(
            query=request.query,
            answer=result.answer,
            model=result.model,
            sources=[
                QuickSearchSource(title=source["title"], url=source["url"])
                for source in result.sources
            ],
        )

    def agentic_search(self, query: str) -> AgenticSearchResponse:
        request = AgenticSearchRequest(query=query)
        result = self._backend.agentic_search(request.query)
        return AgenticSearchResponse(
            query=request.query,
            answer=result.answer,
            model=result.model,
            sources=[
                AgenticSearchSource(title=source["title"], url=source["url"])
                for source in result.sources
            ],
        )


def quick_search(
    query: str,
    *,
    chat_model: Any,
    openai_client_factory: OpenAIClientFactory | None = None,
) -> QuickSearchResponse:
    return WebAgentClient(
        chat_model=chat_model,
        openai_client_factory=openai_client_factory,
    ).quick_search(query)


def agentic_search(
    query: str,
    *,
    chat_model: Any,
    openai_client_factory: OpenAIClientFactory | None = None,
) -> AgenticSearchResponse:
    return WebAgentClient(
        chat_model=chat_model,
        openai_client_factory=openai_client_factory,
    ).agentic_search(query)


def _build_openai_client(chat_model: Any) -> OpenAI:
    config = OpenAIResponsesBackend.extract_chat_model_config(chat_model)
    return OpenAI(api_key=config.api_key)
