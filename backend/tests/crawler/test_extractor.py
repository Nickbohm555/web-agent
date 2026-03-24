from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings
from backend.app.crawler.extractor import (
    MIN_EXTRACTED_TEXT_CHARS,
    extract_content,
    extraction_result_from_fetch_failure,
)
from backend.app.crawler.http_worker import HttpFetchFailure


def test_extract_content_returns_ok_for_rich_html_fixture() -> None:
    result = extract_content(body=_rich_article_html(), content_type="text/html")

    assert result.state == "ok"
    assert result.fallback_reason is None
    assert len(result.text) >= MIN_EXTRACTED_TEXT_CHARS
    assert "agent systems" in result.text.lower()
    assert result.markdown


def test_extract_content_returns_low_content_quality_for_boilerplate_only_html() -> None:
    result = extract_content(body=_boilerplate_html(), content_type="text/html")

    assert result.state == "low-content-quality"
    assert result.fallback_reason == "low-content-quality"
    assert len(result.text) < MIN_EXTRACTED_TEXT_CHARS


def test_extract_content_returns_unsupported_content_type_for_non_html_payload() -> None:
    result = extract_content(body="%PDF-1.7", content_type="application/pdf")

    assert result.state == "unsupported-content-type"
    assert result.fallback_reason == "unsupported-content-type"
    assert result.text == ""
    assert result.markdown == ""


def test_extract_content_returns_lead_excerpt_even_when_objective_is_provided() -> None:
    result = extract_content(
        body=_objective_ranked_article_html(),
        content_type="text/html",
    )

    assert result.state == "ok"
    assert result.excerpts
    assert "agent systems need a crisp retrieval objective" in result.excerpts[0].text.lower()


def test_extract_content_uses_lead_excerpt_when_objective_has_no_strong_match() -> None:
    result = extract_content(
        body=_objective_ranked_article_html(),
        content_type="text/html",
    )

    assert result.state == "ok"
    assert result.excerpts
    assert "agent systems need a crisp retrieval objective" in result.excerpts[0].text.lower()


def test_extraction_result_from_fetch_failure_maps_network_error_state() -> None:
    failure = HttpFetchFailure(
        url="https://example.com/page",
        final_url=None,
        status_code=None,
        content_type=None,
        error=ToolError(
            kind="network_error",
            message="request failed before a response was received",
            retryable=True,
            attempt_number=3,
            operation="open_url",
            timings=ToolTimings(total_ms=125),
        ),
        meta=ToolMeta(
            operation="open_url",
            attempts=3,
            retries=2,
            duration_ms=125,
            timings=ToolTimings(total_ms=125),
        ),
    )

    result = extraction_result_from_fetch_failure(failure)

    assert result.state == "network-error"
    assert result.fallback_reason == "network-error"
    assert result.text == ""
    assert result.markdown == ""


def _rich_article_html() -> str:
    paragraphs = [
        "Agent systems need consistent retrieval contracts so orchestration layers can reason about success and failure without leaking provider payloads.",
        "A high quality extraction should preserve the main narrative, remove navigation chrome, and produce enough text for downstream summarization and answer synthesis.",
        "Deterministic quality thresholds keep crawl behavior debuggable by ensuring weak pages become explicit fallback states instead of silent empty successes.",
    ]
    article = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    return f"""
    <html>
      <body>
        <header><nav>Home Docs Pricing</nav></header>
        <main>
          <article>
            <h1>Reliable agent systems</h1>
            {article}
          </article>
        </main>
        <footer>Footer links and contact info</footer>
      </body>
    </html>
    """


def _boilerplate_html() -> str:
    return """
    <html>
      <body>
        <header>Home Docs Login</header>
        <nav>Products Pricing About</nav>
        <footer>Copyright Example</footer>
      </body>
    </html>
    """


def _objective_ranked_article_html() -> str:
    paragraphs = [
        "Agent systems need a crisp retrieval objective before they open long pages so they can avoid summarizing navigation chrome and unrelated prose.",
        "Structured run telemetry helps operators understand when search, crawling, and answer synthesis are moving forward together.",
        "The deployment rollback checklist starts by pausing queued jobs, restoring the last known good build artifact, and validating database migrations before traffic returns.",
        "Post-incident retrospectives should capture timeline gaps, user impact, and follow-up owners without turning into generic blame documents.",
        "A stable retrieval contract should preserve focused excerpts for the runtime while still exposing the full extracted body for broader synthesis.",
    ]
    article = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    return f"""
    <html>
      <body>
        <main>
          <article>
            <h1>Operating reliable research agents</h1>
            {article}
          </article>
        </main>
      </body>
    </html>
    """
