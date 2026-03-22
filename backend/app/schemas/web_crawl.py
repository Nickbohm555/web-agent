from __future__ import annotations

from urllib.parse import urlsplit
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .tool_errors import ToolErrorEnvelope, ToolMeta

CrawlFallbackReason = Literal["network-error", "low-content-quality", "unsupported-content-type"]
ExtractionState = Literal["ok", "low-content-quality", "unsupported-content-type", "network-error"]


def _strip_text(value: str) -> str:
    return value.strip()


def _strip_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _strip_text(value)


class WebCrawlInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    objective: Optional[str] = Field(default=None, min_length=1)

    @field_validator("url")
    @classmethod
    def validate_scheme(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("url must use http or https")
        return value

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: Optional[str]) -> Optional[str]:
        normalized = _strip_optional_text(value)
        if normalized is None:
            return None
        if not normalized:
            raise ValueError("objective must not be empty")
        return normalized


class WebCrawlExcerpt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(min_length=1)
    markdown: str = Field(min_length=1)

    @field_validator("text", "markdown")
    @classmethod
    def normalize_output(cls, value: str) -> str:
        return _strip_text(value)


class WebCrawlSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    final_url: HttpUrl
    text: str
    markdown: str
    objective: Optional[str] = None
    excerpts: list[WebCrawlExcerpt] = Field(default_factory=list)
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    fallback_reason: Optional[CrawlFallbackReason] = None
    meta: ToolMeta

    @field_validator("text", "markdown", "content_type", "objective")
    @classmethod
    def normalize_text(cls, value: Optional[str]) -> Optional[str]:
        return _strip_optional_text(value)

    def to_source_record(self) -> dict[str, str]:
        snippet_source = self.excerpts[0].text if self.excerpts else self.text
        snippet = snippet_source[:280].strip()
        return {
            "title": _derive_source_title(str(self.final_url)),
            "url": str(self.final_url),
            "snippet": snippet,
        }

    def source_alias_urls(self) -> tuple[str, ...]:
        original_url = str(self.url)
        final_url = str(self.final_url)
        if original_url == final_url:
            return ()
        return (original_url,)


class WebCrawlError(ToolErrorEnvelope):
    model_config = ConfigDict(extra="forbid", strict=True)


WebCrawlToolResult = Union[WebCrawlSuccess, WebCrawlError]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    state: ExtractionState
    text: str
    markdown: str
    excerpts: list[WebCrawlExcerpt] = Field(default_factory=list)
    fallback_reason: Optional[CrawlFallbackReason] = None

    @field_validator("text", "markdown")
    @classmethod
    def normalize_output(cls, value: str) -> str:
        return _strip_text(value)


def _derive_source_title(url: str) -> str:
    parsed = urlsplit(url)
    hostname = parsed.hostname or url
    path = parsed.path.rstrip("/")
    if not path or path == "/":
        return hostname
    path_tail = path.split("/")[-1]
    return f"{hostname}{('/' + path_tail) if path_tail else ''}"
