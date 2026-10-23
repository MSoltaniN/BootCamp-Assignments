"""Bounded retry policy with Retry-After support and an injectable clock.

No real sleeping happens: the caller passes a `sleep` callable, and the default records the
scheduled delay instead of blocking, so the timeline is reproducible in a notebook.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

# Retry only what can plausibly succeed on its own.
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# 400/401/403/409/422 are contract or configuration mistakes: repeating them cannot help.
NON_RETRYABLE_STATUS = frozenset({400, 401, 403, 404, 409, 422})

MAX_ATTEMPTS = 3
BASE_DELAY = 0.5
MAX_DELAY = 5.0


@dataclass
class Attempt:
    number: int
    status: int
    retry_after: float | None = None


@dataclass
class RetryResult:
    attempts: list[Attempt] = field(default_factory=list)
    scheduled_waits: list[float] = field(default_factory=list)
    final_status: int | None = None
    ok: bool = False
    stopped_reason: str = ""

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def total_wait(self) -> float:
        return round(sum(self.scheduled_waits), 4)


def backoff_delay(attempt_number: int) -> float:
    """Exponential, capped: 0.5, 1.0, 2.0, ..."""
    return min(BASE_DELAY * (2 ** (attempt_number - 1)), MAX_DELAY)


def run_with_retry(
    responses: Iterable[int],
    *,
    retry_after: float | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    inner_deadline: float | None = None,
    sleep: Callable[[float], None] | None = None,
) -> RetryResult:
    """Walk a scripted status sequence and record what would have been waited.

    `inner_deadline` is the time still available to *this call*; if the next scheduled wait would
    exceed it, the loop stops instead of overrunning the caller's budget.
    """
    result = RetryResult()
    planned = list(responses)
    waited = 0.0
    record = sleep or (lambda seconds: None)

    for index, status in enumerate(planned[:max_attempts], start=1):
        result.attempts.append(Attempt(index, status, retry_after if status == 429 else None))
        if 200 <= status < 300:
            result.final_status, result.ok, result.stopped_reason = status, True, "success"
            break
        if status in NON_RETRYABLE_STATUS:
            result.final_status = status
            result.stopped_reason = f"non_retryable_{status}"
            break
        if status not in RETRYABLE_STATUS:
            result.final_status = status
            result.stopped_reason = f"unclassified_{status}"
            break
        if index == max_attempts or index == len(planned):
            result.final_status = status
            result.stopped_reason = "attempts_exhausted"
            break

        delay = retry_after if status == 429 and retry_after is not None else backoff_delay(index)
        if inner_deadline is not None and waited + delay > inner_deadline:
            result.final_status = status
            result.stopped_reason = "deadline_would_be_exceeded"
            break
        record(delay)
        result.scheduled_waits.append(round(delay, 4))
        waited += delay

    return result
