from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta

from .session_profile import SessionCookie


class BrowserContextSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cookies: list[SessionCookie] = Field(default_factory=list)
    extra_headers: dict[str, str] = Field(default_factory=dict)
    local_storage: dict[str, str] = Field(default_factory=dict)
    session_storage: dict[str, str] = Field(default_factory=dict)


class BrowserFetchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str
    final_url: str
    status_code: int = Field(ge=100, le=599)
    content_type: str = Field(min_length=1)
    html: str
    text: str
    rendered: bool = True
    session_profile_id: Optional[str] = None
    meta: Optional[ToolMeta] = None


class BrowserFetchFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str
    final_url: Optional[str] = None
    status_code: Optional[int] = Field(default=None, ge=100, le=599)
    content_type: Optional[str] = None
    navigation_error_kind: Literal[
        "timeout",
        "browser_unavailable",
        "navigation_error",
    ]
    error: ToolError
    meta: ToolMeta
    rendered: bool = True
    session_profile_id: Optional[str] = None
