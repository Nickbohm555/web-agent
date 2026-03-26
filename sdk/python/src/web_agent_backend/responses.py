from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI

from .errors import WebAgentSdkError

QUICK_SEARCH_INSTRUCTIONS = (
    "Answer the query quickly using web search. Keep the response concise and factual."
)
AGENTIC_SEARCH_INSTRUCTIONS = (
    "Investigate the query thoroughly using web search in a single stateless run. "
    "Synthesize a complete answer and cite the strongest sources."
)
WEB_SEARCH_TOOL = {"type": "web_search"}


@dataclass(frozen=True)
class ChatModelConfig:
    model: str
    api_key: str


@dataclass(frozen=True)
class BackendSearchResult:
    answer: str
    model: str
    sources: list[dict[str, str]]


class OpenAIResponsesBackend:
    def __init__(
        self,
        *,
        model: str,
        openai_client: Any,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("chat_model must expose a non-empty OpenAI model name")
        self._model = normalized_model
        self._openai_client = openai_client

    @classmethod
    def from_chat_model(
        cls,
        chat_model: Any,
        *,
        openai_client_factory: Callable[[Any], Any] | None = None,
    ) -> "OpenAIResponsesBackend":
        config = extract_chat_model_config(chat_model)
        client_factory = openai_client_factory or (lambda _: OpenAI(api_key=config.api_key))
        return cls(
            model=config.model,
            openai_client=client_factory(chat_model),
        )

    @staticmethod
    def extract_chat_model_config(chat_model: Any) -> ChatModelConfig:
        return extract_chat_model_config(chat_model)

    def quick_search(self, query: str) -> BackendSearchResult:
        response = self._create_response(
            input_text=query,
            instructions=QUICK_SEARCH_INSTRUCTIONS,
        )
        return BackendSearchResult(
            answer=_read_output_text(response),
            model=self._model,
            sources=_extract_sources(response),
        )

    def agentic_search(self, query: str) -> BackendSearchResult:
        response = self._create_response(
            input_text=query,
            instructions=AGENTIC_SEARCH_INSTRUCTIONS,
        )
        return BackendSearchResult(
            answer=_read_output_text(response),
            model=self._model,
            sources=_extract_sources(response),
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


def extract_chat_model_config(chat_model: Any) -> ChatModelConfig:
    model = _read_chat_model_name(chat_model)
    if not model:
        raise ValueError("chat_model must expose a non-empty OpenAI model name")

    api_key = _read_chat_model_api_key(chat_model)
    if not api_key:
        raise ValueError("chat_model must expose a non-empty OpenAI api key")

    return ChatModelConfig(
        model=model,
        api_key=api_key,
    )


def _read_chat_model_name(chat_model: Any) -> str:
    for attribute in ("model_name", "model"):
        value = getattr(chat_model, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_chat_model_api_key(chat_model: Any) -> str:
    for attribute in ("openai_api_key", "api_key"):
        value = getattr(chat_model, attribute, None)
        if value is None:
            continue
        if hasattr(value, "get_secret_value"):
            secret = value.get_secret_value()
            if isinstance(secret, str) and secret.strip():
                return secret.strip()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


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
