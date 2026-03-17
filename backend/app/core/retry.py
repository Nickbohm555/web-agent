from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")


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
    for attempt in Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.25, min=0.25, max=2.0),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True,
    ):
        with attempt:
            attempt_number = attempt.retry_state.attempt_number
            value = operation(attempt_number)
            return RetryResult(value=value, attempts=attempt_number)

    raise RuntimeError("retry loop exited without returning a result")

