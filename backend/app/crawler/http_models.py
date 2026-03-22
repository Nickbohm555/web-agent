from __future__ import annotations

from dataclasses import dataclass

from backend.app.contracts.tool_errors import ToolError, ToolMeta


@dataclass(frozen=True)
class HttpFetchSuccess:
    url: str
    final_url: str
    status_code: int
    content_type: str
    body: str
    meta: ToolMeta


@dataclass(frozen=True)
class HttpFetchFailure:
    url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    error: ToolError
    meta: ToolMeta
