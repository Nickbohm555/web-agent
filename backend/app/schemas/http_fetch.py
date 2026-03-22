from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .tool_errors import ToolError, ToolMeta


class HttpFetchSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str
    final_url: str
    status_code: int
    content_type: str
    body: str
    meta: ToolMeta


class HttpFetchFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: str
    final_url: Optional[str]
    status_code: Optional[int]
    content_type: Optional[str]
    error: ToolError
    meta: ToolMeta
