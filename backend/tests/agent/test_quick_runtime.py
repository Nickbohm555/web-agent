from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from backend.agent.quick_evidence import build_quick_evidence
from backend.agent.quick_runtime import run_quick_runtime
from backend.agent.quick_selection import select_quick_urls
from backend.agent.schemas import AgentRunResult
from backend.app.tools.schemas.web_crawl import WebCrawlError
from backend.app.tools.schemas.web_search import WebSearchResponse


@dataclass
class StubQuickSearchRunner:
    payload: dict[str, Any]
    captured_query: str | None = None
    captured_max_results: int | None = None

    def __call__(
        self,
        *,
        query: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        self.captured_query = query
        self.captured_max_results = max_results
        return self.payload


@dataclass
class StubQuickCrawlRunner:
    payloads_by_url: dict[str, Any]
    requested_urls: list[str] | None = None
    requested_objectives: list[str | None] | None = None

    def __call__(self, *, url: str, objective: str | None = None) -> Any:
        if self.requested_urls is None:
            self.requested_urls = []
        if self.requested_objectives is None:
            self.requested_objectives = []
        self.requested_urls.append(url)
        self.requested_objectives.append(objective)
        return self.payloads_by_url[url]


def test_run_quick_runtime_searches_once_crawls_top_three_and_returns_sources() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "What is the pricing?",
            "results": [
                {
                    "title": "One",
                    "url": "https://example.com/1",
                    "snippet": "Result one",
                    "rank": {"position": 1, "provider_position": 1},
                },
                {
                    "title": "Two",
                    "url": "https://example.com/2",
                    "snippet": "Result two",
                    "rank": {"position": 2, "provider_position": 2},
                },
                {
                    "title": "Two duplicate",
                    "url": "https://example.com/2",
                    "snippet": "Duplicate result",
                    "rank": {"position": 3, "provider_position": 3},
                },
                {
                    "title": "Three",
                    "url": "https://example.com/3",
                    "snippet": "Result three",
                    "rank": {"position": 4, "provider_position": 4},
                },
                {
                    "title": "Blocked",
                    "url": "https://blocked.example.com/4",
                    "snippet": "Blocked result",
                    "rank": {"position": 5, "provider_position": 5},
                },
            ],
            "metadata": {"result_count": 5, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    crawl_runner = StubQuickCrawlRunner(
        payloads_by_url={
            "https://example.com/1": {
                "url": "https://example.com/1",
                "final_url": "https://example.com/1",
                "text": "Crawl one.",
                "markdown": "Crawl one.",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            },
            "https://example.com/2": {
                "url": "https://example.com/2",
                "final_url": "https://example.com/2",
                "text": "Crawl two.",
                "markdown": "Crawl two.",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            },
            "https://example.com/3": {
                "url": "https://example.com/3",
                "final_url": "https://example.com/3",
                "text": "Crawl three.",
                "markdown": "Crawl three.",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            },
        }
    )
    result = run_quick_runtime(
        prompt="What is the pricing?",
        run_id="run-quick",
        started_at=0.0,
        search_runner=search_runner,
        crawl_runner=crawl_runner,
    )

    assert isinstance(result, AgentRunResult)
    assert search_runner.captured_query == "What is the pricing?"
    assert search_runner.captured_max_results == 5
    assert crawl_runner.requested_urls == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]
    assert result.status == "completed"
    assert result.run_id == "run-quick"
    assert result.final_answer is not None
    assert (
        result.final_answer.text
        == "One: Result one. Two: Result two. Two duplicate: Duplicate result.\n\n"
        "Sources:\n"
        "- One: https://example.com/1\n"
        "- Two: https://example.com/2\n"
        "- Two duplicate: https://example.com/2"
    )
    assert result.sources and [str(source.url) for source in result.sources] == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]


def test_run_quick_runtime_does_not_accept_answer_client_override() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "What is the refund policy?",
            "results": [
                {
                    "title": "Refunds",
                    "url": "https://example.com/refunds",
                    "snippet": "30-day refund policy",
                    "rank": {"position": 1, "provider_position": 1},
                }
            ],
            "metadata": {"result_count": 1, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    crawl_runner = StubQuickCrawlRunner(
        payloads_by_url={
            "https://example.com/refunds": {
                "url": "https://example.com/refunds",
                "final_url": "https://example.com/refunds",
                "text": "Customers can request a refund within 30 days.",
                "markdown": "Customers can request a refund within 30 days.",
                "status_code": 200,
                "content_type": "text/html",
                "fallback_reason": None,
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            }
        }
    )
    with pytest.raises(TypeError, match="answer_client"):
        run_quick_runtime(
            prompt="What is the refund policy?",
            run_id="run-quick",
            started_at=0.0,
            search_runner=search_runner,
            crawl_runner=crawl_runner,
            answer_client=object(),
        )


def test_select_quick_urls_skips_duplicate_urls() -> None:
    search_response = WebSearchResponse.model_validate(
        {
            "query": "pricing",
            "results": [
                {
                    "title": "Allowed A",
                    "url": "https://allowed.example.com/a",
                    "snippet": "A",
                    "rank": {"position": 1, "provider_position": 1},
                },
                {
                    "title": "Duplicate A",
                    "url": "https://allowed.example.com/a",
                    "snippet": "A duplicate",
                    "rank": {"position": 2, "provider_position": 2},
                },
                {
                    "title": "Blocked",
                    "url": "https://blocked.example.com/x",
                    "snippet": "Blocked",
                    "rank": {"position": 3, "provider_position": 3},
                },
                {
                    "title": "Allowed B",
                    "url": "https://allowed.example.com/b",
                    "snippet": "B",
                    "rank": {"position": 4, "provider_position": 4},
                },
            ],
            "metadata": {"result_count": 4, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    selected = select_quick_urls(search_response, max_urls=3)

    assert selected == [
        "https://allowed.example.com/a",
        "https://blocked.example.com/x",
        "https://allowed.example.com/b",
    ]


def test_build_quick_evidence_keeps_successful_crawl_sources() -> None:
    search_response = WebSearchResponse.model_validate(
        {
            "query": "pricing",
            "results": [
                {
                    "title": "Search One",
                    "url": "https://example.com/a",
                    "snippet": "A",
                    "rank": {"position": 1, "provider_position": 1},
                }
            ],
            "metadata": {"result_count": 1, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    crawl_payloads = [
        {
            "url": "https://example.com/a",
            "final_url": "https://example.com/a/final",
            "text": "Expanded crawl content.",
            "markdown": "Expanded crawl content.",
            "status_code": 200,
            "content_type": "text/html",
            "fallback_reason": None,
            "meta": {
                "operation": "web_crawl",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 10,
                "timings": {"total_ms": 10},
            },
        },
        WebCrawlError.model_validate(
            {
                "error": {
                    "kind": "network_error",
                    "message": "crawl failed",
                    "retryable": True,
                    "attempt_number": 1,
                    "operation": "web_crawl",
                    "timings": {"total_ms": 10},
                },
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            }
        ),
    ]

    evidence = build_quick_evidence(
        prompt="What is the pricing?",
        search_response=search_response,
        crawl_payloads=crawl_payloads,
    )

    assert evidence.search_response.query == "pricing"
    assert str(evidence.sources[0].url) == "https://example.com/a/final"
    assert evidence.selected_urls == ("https://example.com/a",)
    assert str(evidence.successful_crawls[0].final_url) == "https://example.com/a/final"


def test_run_quick_runtime_returns_failure_when_all_crawls_fail() -> None:
    search_runner = StubQuickSearchRunner(
        payload={
            "query": "What is the pricing?",
            "results": [
                {
                    "title": "One",
                    "url": "https://example.com/1",
                    "snippet": "Result one",
                    "rank": {"position": 1, "provider_position": 1},
                },
                {
                    "title": "Two",
                    "url": "https://example.com/2",
                    "snippet": "Result two",
                    "rank": {"position": 2, "provider_position": 2},
                },
            ],
            "metadata": {"result_count": 2, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12, "provider_ms": 8},
            },
        }
    )
    crawl_runner = StubQuickCrawlRunner(
        payloads_by_url={
            "https://example.com/1": {
                "error": {
                    "kind": "network_error",
                    "message": "crawl failed",
                    "retryable": True,
                    "attempt_number": 1,
                    "operation": "web_crawl",
                    "timings": {"total_ms": 10},
                },
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            },
            "https://example.com/2": {
                "error": {
                    "kind": "network_error",
                    "message": "crawl failed",
                    "retryable": True,
                    "attempt_number": 1,
                    "operation": "web_crawl",
                    "timings": {"total_ms": 10},
                },
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10},
                },
            },
        }
    )

    result = run_quick_runtime(
        prompt="What is the pricing?",
        run_id="run-quick",
        started_at=0.0,
        search_runner=search_runner,
        crawl_runner=crawl_runner,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.category == "tool_failure"
