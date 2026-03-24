from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.crawler.schemas.session_profile import SessionCookie, StorageSeedEntry
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta


class StorageStateApplied(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cookies: bool = False
    headers: bool = False
    local_storage: bool = False
    session_storage: bool = False


class BrowserContextSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cookies: list[SessionCookie] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    local_storage: list[StorageSeedEntry] = Field(default_factory=list)
    session_storage: list[StorageSeedEntry] = Field(default_factory=list)

    @field_validator("headers")
    @classmethod
    def normalize_headers(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for name, header_value in value.items():
            normalized[name.strip()] = header_value.strip()
        return normalized


class BrowserFetchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str = Field(min_length=1)
    final_url: str = Field(min_length=1)
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    body: str
    seed_applied: StorageStateApplied
    session_profile_id: Optional[str] = None
    rendered: bool = True
    meta: Optional[ToolMeta] = None

    @field_validator("url", "final_url", "content_type", "body", "session_profile_id")
    @classmethod
    def normalize_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("browser fetch text fields must not be empty")
        return normalized


class BrowserFetchFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str = Field(min_length=1)
    final_url: Optional[str] = None
    status_code: Optional[int] = Field(default=None, ge=100, le=599)
    content_type: Optional[str] = None
    error: ToolError
    seed_applied: StorageStateApplied
    meta: ToolMeta


BrowserFetchResult = Union[BrowserFetchSuccess, BrowserFetchFailure]
