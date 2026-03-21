import pytest

from backend.app.core.retry import MAX_RETRY_ATTEMPTS, execute_with_retry


class RetryableError(Exception):
    pass


def test_execute_with_retry_rejects_non_positive_attempt_budgets() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        execute_with_retry(
            lambda _attempt: "ok",
            retryable_exceptions=(RetryableError,),
            max_attempts=0,
        )


def test_execute_with_retry_rejects_attempt_budgets_above_guardrail() -> None:
    with pytest.raises(ValueError, match=str(MAX_RETRY_ATTEMPTS)):
        execute_with_retry(
            lambda _attempt: "ok",
            retryable_exceptions=(RetryableError,),
            max_attempts=MAX_RETRY_ATTEMPTS + 1,
        )


def test_execute_with_retry_returns_first_successful_attempt() -> None:
    attempts: list[int] = []

    result = execute_with_retry(
        lambda attempt_number: attempts.append(attempt_number) or "ok",
        retryable_exceptions=(RetryableError,),
        max_attempts=3,
    )

    assert result.value == "ok"
    assert result.attempts == 1
    assert attempts == [1]
