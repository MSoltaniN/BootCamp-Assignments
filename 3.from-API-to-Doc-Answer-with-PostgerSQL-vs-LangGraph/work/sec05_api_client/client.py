"""Client helpers: stable cursor pagination and a deadline-aware request wrapper."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


@dataclass
class PageWalk:
    items: list[dict] = field(default_factory=list)
    pages: int = 0
    duplicates: int = 0
    applied_limits: list[int] = field(default_factory=list)

    @property
    def unique_ids(self) -> int:
        return len({item["case_id"] for item in self.items})


def collect_all_cases(client: httpx.Client, user_id: str, *, page_limit: int = 50, max_pages: int = 100) -> PageWalk:
    """Walk every page and collect unique cases.

    `page_limit` is intentionally larger than the server cap: the walk must still terminate and
    must not duplicate rows, which proves the client trusts `next_cursor` rather than `limit`.
    """
    walk = PageWalk()
    seen: set[str] = set()
    cursor: str | None = None

    for _ in range(max_pages):
        params: dict[str, object] = {"limit": page_limit}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/cases", params=params, headers={"X-User-ID": user_id})
        response.raise_for_status()
        body = response.json()
        walk.pages += 1
        walk.applied_limits.append(body["limit_applied"])
        for item in body["items"]:
            if item["case_id"] in seen:
                walk.duplicates += 1
                continue
            seen.add(item["case_id"])
            walk.items.append(item)
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return walk


@dataclass
class Deadline:
    """One budget for the whole call chain, not per attempt."""

    total_seconds: float
    started: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_seconds - self.elapsed)

    @property
    def expired(self) -> bool:
        return self.remaining <= 0.0


class TimeoutBudgetError(Exception):
    """Raised when the total budget is gone; never converted into a success."""


def call_with_budget(
    client: httpx.Client,
    path: str,
    *,
    deadline: Deadline,
    connect_timeout: float = 0.5,
    read_timeout: float = 0.5,
    **kwargs,
) -> httpx.Response:
    """Split connect/read timeouts, then clamp both by what is left of the total budget."""
    if deadline.expired:
        raise TimeoutBudgetError(f"deadline of {deadline.total_seconds}s already exhausted before the call")
    budget = deadline.remaining
    timeout = httpx.Timeout(
        connect=min(connect_timeout, budget),
        read=min(read_timeout, budget),
        write=min(read_timeout, budget),
        pool=min(connect_timeout, budget),
    )
    try:
        return client.request(kwargs.pop("method", "GET"), path, timeout=timeout, **kwargs)
    except httpx.ReadTimeout as exc:
        raise TimeoutBudgetError(
            f"read timeout after {read_timeout}s (connect timeout was {connect_timeout}s); "
            f"{deadline.remaining:.2f}s of the total budget remained"
        ) from exc
    except httpx.ConnectTimeout as exc:
        raise TimeoutBudgetError(f"connect timeout after {connect_timeout}s") from exc
