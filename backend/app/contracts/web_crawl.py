from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .tool_errors import ToolErrorEnvelope, ToolMeta

CrawlFallbackReason = Literal["network-error", "low-content-quality", "unsupported-content-type"]
ExtractionState = Literal["ok", "low-content-quality", "unsupported-content-type", "network-error"]


class WebCrawlInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl

    @field_validator("url")
    @classmethod
    def validate_scheme(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("url must use http or https")
        return value


class WebCrawlSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    final_url: HttpUrl
    text: str
    markdown: str
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    fallback_reason: Optional[CrawlFallbackReason] = None
    meta: ToolMeta

    @field_validator("text", "markdown", "content_type")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class WebCrawlError(ToolErrorEnvelope):
    model_config = ConfigDict(extra="forbid", strict=True)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    state: ExtractionState
    text: str
    markdown: str
    fallback_reason: Optional[CrawlFallbackReason] = None

    @field_validator("text", "markdown")
    @classmethod
    def normalize_output(cls, value: str) -> str:
        return value.strip()
