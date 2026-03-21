from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")
MAX_RETRY_ATTEMPTS = 5
MIN_RETRY_WAIT_SECONDS = 0.25
MAX_RETRY_WAIT_SECONDS = 2.0


@dataclass(frozen=True)
class RetryResult(Generic[T]):
    value: T
    attempts: int


def execute_with_retry(
    operation: Callable[[int], T],
    *,
    retryable_exceptions: tuple[type[BaseException], ...],
    max_attempts: int = 3,
) -> RetryResult[T]:
    validated_max_attempts = _validate_max_attempts(max_attempts)
    for attempt in Retrying(
        stop=stop_after_attempt(validated_max_attempts),
        wait=wait_exponential(
            multiplier=MIN_RETRY_WAIT_SECONDS,
            min=MIN_RETRY_WAIT_SECONDS,
            max=MAX_RETRY_WAIT_SECONDS,
        ),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True,
    ):
        with attempt:
            attempt_number = attempt.retry_state.attempt_number
            value = operation(attempt_number)
            return RetryResult(value=value, attempts=attempt_number)

    raise RuntimeError("retry loop exited without returning a result")


def _validate_max_attempts(max_attempts: int) -> int:
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")

    if max_attempts > MAX_RETRY_ATTEMPTS:
        raise ValueError(
            f"max_attempts must not exceed {MAX_RETRY_ATTEMPTS}"
        )

    return max_attempts
