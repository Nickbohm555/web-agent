from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger("backend.app.tools")


def log_web_search_result(*, query: str, payload: Any) -> None:
    from backend.app.tools.web_search import build_web_search_action_record

    action_record = build_web_search_action_record(query=query, payload=payload)
    logger.log(
        _tool_log_level(action_record),
        "tool.web_search %s",
        _serialize(action_record),
    )


def log_web_crawl_result(
    *,
    url: str,
    objective: str | None,
    payload: Any,
) -> None:
    from backend.app.tools.web_crawl import build_web_crawl_action_record

    action_record = build_web_crawl_action_record(url=url, payload=payload)
    if objective and "objective" not in action_record:
        action_record["objective"] = objective
    logger.log(
        _tool_log_level(action_record),
        "tool.web_crawl %s",
        _serialize(action_record),
    )


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _tool_log_level(action_record: dict[str, Any]) -> int:
    return logging.WARNING if "error_kind" in action_record else logging.INFO
