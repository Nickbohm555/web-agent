from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .tool_errors import ToolError
from .open_url import (
    OpenUrlError,
    OpenUrlMeta,
    OpenUrlSuccess,
    _coerce_open_url_meta,
)


class OpenUrlBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    urls: list[HttpUrl] = Field(min_length=1, max_length=5)


class OpenUrlBatchItemResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    status: Literal["succeeded", "failed"]
    result: Optional[OpenUrlSuccess] = None
    error: Optional[ToolError] = None

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "OpenUrlBatchItemResult":
        if self.status == "succeeded":
            if self.result is None or self.error is not None:
                raise ValueError("succeeded batch items must include result and omit error")
        elif self.result is not None or self.error is None:
            raise ValueError("failed batch items must include error and omit result")
        return self


class OpenUrlBatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    attempted: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "OpenUrlBatchSummary":
        if self.attempted != self.succeeded + self.failed:
            raise ValueError("attempted must equal succeeded + failed")
        return self


class OpenUrlBatchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requested_urls: list[HttpUrl] = Field(min_length=1, max_length=5)
    items: list[OpenUrlBatchItemResult] = Field(min_length=1)
    meta: OpenUrlMeta
    summary: OpenUrlBatchSummary

    @field_validator("meta", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> OpenUrlMeta:
        return _coerce_open_url_meta(value)

    @model_validator(mode="after")
    def validate_item_order(self) -> "OpenUrlBatchSuccess":
        if len(self.requested_urls) != len(self.items):
            raise ValueError("requested_urls must match items length")

        actual_urls = [item.url for item in self.items]
        if actual_urls != self.requested_urls:
            raise ValueError("items must preserve requested_urls order")
        return self


OpenUrlBatchToolResult = Union[OpenUrlBatchSuccess, OpenUrlError]
