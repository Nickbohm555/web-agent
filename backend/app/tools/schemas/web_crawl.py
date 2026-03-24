from __future__ import annotations

from typing import Literal, Optional, Union
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .tool_errors import ToolErrorEnvelope, ToolMeta

CrawlFallbackReason = Literal["network-error", "low-content-quality", "unsupported-content-type"]
ExtractionState = Literal["ok", "low-content-quality", "unsupported-content-type", "network-error"]


def _strip_text(value: str) -> str:
    return value.strip()


def _strip_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _strip_text(value)


def _coerce_web_crawl_meta(value: object) -> "WebCrawlMeta":
    if isinstance(value, WebCrawlMeta):
        return value
    if isinstance(value, ToolMeta):
        return WebCrawlMeta.model_validate(value.model_dump())
    if isinstance(value, dict):
        return WebCrawlMeta.model_validate(value)
    raise TypeError("meta must be a ToolMeta, WebCrawlMeta, or mapping")


class WebCrawlToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: Optional[HttpUrl] = None
    urls: Optional[list[HttpUrl]] = Field(default=None, min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "WebCrawlToolInput":
        if (self.url is None) == (self.urls is None):
            raise ValueError("exactly one of url or urls must be provided")
        return self

    @field_validator("url")
    @classmethod
    def validate_scheme(cls, value: Optional[HttpUrl]) -> Optional[HttpUrl]:
        if value is None:
            return None
        if value.scheme not in {"http", "https"}:
            raise ValueError("url must use http or https")
        return value

    @field_validator("urls")
    @classmethod
    def validate_url_schemes(cls, value: Optional[list[HttpUrl]]) -> Optional[list[HttpUrl]]:
        if value is None:
            return None
        for item in value:
            if item.scheme not in {"http", "https"}:
                raise ValueError("urls must use http or https")
        return value


class WebCrawlExcerpt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(min_length=1)
    markdown: str = Field(min_length=1)

    @field_validator("text", "markdown")
    @classmethod
    def normalize_output(cls, value: str) -> str:
        return _strip_text(value)


class WebCrawlMeta(ToolMeta):
    model_config = ConfigDict(extra="forbid", strict=True)

    strategy_used: Optional[str] = None
    escalation_count: int = Field(default=0, ge=0)
    session_profile_id: Optional[str] = None
    block_reason: Optional[str] = None
    rendered: bool = False
    challenge_detected: bool = False

    @field_validator("strategy_used", "session_profile_id", "block_reason")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        normalized = _strip_optional_text(value)
        if normalized is None:
            return None
        if not normalized:
            raise ValueError("meta text fields must not be empty")
        return normalized


class WebCrawlSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    final_url: HttpUrl
    text: str
    markdown: str
    excerpts: list[WebCrawlExcerpt] = Field(default_factory=list)
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    fallback_reason: Optional[CrawlFallbackReason] = None
    meta: WebCrawlMeta

    @field_validator("text", "markdown", "content_type")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _strip_text(value)

    @field_validator("meta", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> WebCrawlMeta:
        return _coerce_web_crawl_meta(value)

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

    def has_evidence(self) -> bool:
        return bool(self.excerpts or self.text or self.markdown)


class WebCrawlError(ToolErrorEnvelope):
    model_config = ConfigDict(extra="forbid", strict=True)
    meta: WebCrawlMeta

    @field_validator("meta", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> WebCrawlMeta:
        return _coerce_web_crawl_meta(value)


WebCrawlInput = WebCrawlToolInput


from .web_crawl_batch import WebCrawlBatchSuccess


WebCrawlToolResult = Union[WebCrawlSuccess, WebCrawlBatchSuccess, WebCrawlError]


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
