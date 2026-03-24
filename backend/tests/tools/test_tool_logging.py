from __future__ import annotations

import logging

from backend.app.tools.tool_logging import (
    log_web_crawl_result,
    log_web_search_result,
)


def test_log_web_search_result_includes_result_preview_urls(caplog) -> None:
    payload = {
        "query": "Iraq War Wikipedia",
        "results": [
            {
                "title": "Iraq War - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Iraq_War",
                "snippet": "Overview of the Iraq War.",
                "rank": {
                    "position": 1,
                    "provider_position": 1,
                    "rerank_score": 18.5,
                },
            }
        ],
        "metadata": {
            "provider": "serper",
            "result_count": 1,
        },
        "meta": {
            "operation": "web_search",
            "attempts": 1,
            "retries": 0,
            "duration_ms": 40,
            "timings": {"total_ms": 40, "provider_ms": 25},
        },
    }

    with caplog.at_level(logging.INFO, logger="backend.app.tools"):
        log_web_search_result(query="Iraq War Wikipedia", payload=payload)

    assert "tool.web_search" in caplog.text
    assert '"query": "Iraq War Wikipedia"' in caplog.text
    assert '"results_preview"' in caplog.text
    assert '"url": "https://en.wikipedia.org/wiki/Iraq_War"' in caplog.text


def test_log_web_crawl_result_includes_terminal_http_error_details(caplog) -> None:
    payload = {
        "error": {
            "kind": "http_error",
            "message": "origin returned a terminal HTTP status",
            "retryable": False,
            "status_code": 403,
            "attempt_number": 1,
            "operation": "web_crawl",
            "timings": {"total_ms": 144},
        },
        "meta": {
            "operation": "web_crawl",
            "attempts": 1,
            "retries": 0,
            "duration_ms": 144,
            "timings": {"total_ms": 144},
        },
    }

    with caplog.at_level(logging.INFO, logger="backend.app.tools"):
        log_web_crawl_result(
            url="https://en.wikipedia.org/wiki/Iraq_War",
            objective="Summarize the main points",
            payload=payload,
        )

    assert "tool.web_crawl" in caplog.text
    assert '"url": "https://en.wikipedia.org/wiki/Iraq_War"' in caplog.text
    assert '"status_code": 403' in caplog.text
    assert '"error_kind": "http_error"' in caplog.text
