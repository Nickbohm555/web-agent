from __future__ import annotations

from typing import Any, Protocol

from backend.agent.answer_synthesis import (
    QuickAnswerClient,
    build_quick_answer_evidence_bundle,
    synthesize_quick_answer,
)
from backend.agent.quick_evidence import build_quick_evidence
from backend.agent.quick_search import (
    DEFAULT_QUICK_SEARCH_MAX_RESULTS,
    QuickSearchRunner,
    run_quick_search,
    synthesize_quick_answer as synthesize_quick_answer_text,
)
from backend.agent.quick_selection import select_quick_urls
from backend.agent.runtime_constants import QUICK_RUNTIME_MAX_CRAWLS
from backend.agent.runtime_errors import (
    coerce_tool_error,
    elapsed_ms,
    failed_result,
    map_quick_search_error_category,
    map_quick_search_error_message,
)
from backend.agent.schemas import (
    AgentRunError,
    AgentRunResult,
    AgentRunRetrievalPolicy,
    AgentStructuredAnswer,
)
from backend.app.tools.schemas.web_search import WebSearchResponse
from backend.app.tools.web_crawl import run_web_crawl


class QuickCrawlRunner(Protocol):
    def __call__(self, *, url: str) -> Any:
        ...


def run_quick_runtime(
    *,
    prompt: str,
    run_id: str,
    started_at: float,
    retrieval_policy: AgentRunRetrievalPolicy,
    search_runner: QuickSearchRunner | None = None,
    crawl_runner: QuickCrawlRunner | None = None,
    answer_client: QuickAnswerClient | None = None,
) -> AgentRunResult:
    """Run the deterministic quick retrieval pipeline.

    Example input: `run_quick_runtime(prompt="What is the pricing?", run_id="run-1", started_at=0.0, retrieval_policy=AgentRunRetrievalPolicy())`
    Example output: `AgentRunResult(status="completed", ...)`
    """
    search_payload = run_quick_search(
        query=prompt,
        max_results=DEFAULT_QUICK_SEARCH_MAX_RESULTS,
        search_runner=search_runner,
    )

    error = coerce_tool_error(search_payload)
    if error is not None:
        return failed_result(
            run_id=run_id,
            started_at=started_at,
            category=map_quick_search_error_category(error.error.kind),
            message=map_quick_search_error_message(error.error.kind),
            retryable=error.error.retryable,
        )

    try:
        search_response = WebSearchResponse.model_validate(search_payload)
    except Exception:
        return failed_result(
            run_id=run_id,
            started_at=started_at,
            category="tool_failure",
            message="quick search returned invalid payload",
            retryable=False,
        )

    selected_urls = select_quick_urls(
        search_response,
        max_urls=QUICK_RUNTIME_MAX_CRAWLS,
    )

    crawl_payloads: list[Any] = []
    for url in selected_urls:
        try:
            payload = (crawl_runner or run_web_crawl)(url=url)
        except Exception as exc:
            payload = {
                "error": {
                    "kind": "internal_error",
                    "message": str(exc) or "quick crawl failed",
                    "retryable": False,
                    "operation": "web_crawl",
                },
                "meta": {
                    "operation": "web_crawl",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 0,
                    "timings": {"total_ms": 0},
                },
            }
        crawl_payloads.append(payload)

    evidence = build_quick_evidence(
        prompt=prompt,
        search_response=search_response,
        crawl_payloads=crawl_payloads,
    )
    if not evidence.successful_crawls:
        return AgentRunResult(
            run_id=run_id,
            status="failed",
            final_answer=None,
            sources=[],
            tool_call_count=1 + len(crawl_payloads),
            elapsed_ms=elapsed_ms(started_at),
            error=AgentRunError(
                category="tool_failure",
                message="quick retrieval crawl pipeline failed",
                retryable=False,
            ),
        )

    quick_answer_evidence = build_quick_answer_evidence_bundle(
        question=prompt,
        sources=evidence.sources,
    )
    if answer_client is None:
        return AgentRunResult(
            run_id=run_id,
            status="completed",
            final_answer=AgentStructuredAnswer(text=synthesize_quick_answer_text(search_response)),
            sources=list(evidence.sources),
            tool_call_count=1 + len(crawl_payloads),
            elapsed_ms=elapsed_ms(started_at),
        )

    try:
        return synthesize_quick_answer(
            run_id=run_id,
            started_at=started_at,
            question=prompt,
            evidence=quick_answer_evidence,
            client=answer_client,
            tool_call_count=1 + len(crawl_payloads),
        )
    except Exception as exc:
        return AgentRunResult(
            run_id=run_id,
            status="failed",
            final_answer=None,
            sources=list(evidence.sources),
            tool_call_count=1 + len(crawl_payloads),
            elapsed_ms=elapsed_ms(started_at),
            error=AgentRunError(
                category="provider_failure",
                message=str(exc) or "quick answer synthesis failed",
                retryable=True,
            ),
        )
