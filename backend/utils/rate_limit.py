"""In-process sliding-window rate limiter for login attempts.

Limitation: counters are per-process. Multi-pod deployments need a shared
store (e.g. Redis) before relying on this for production traffic.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from time import monotonic

_lock = threading.Lock()
_events: dict[str, deque[float]] = defaultdict(deque)


class RateLimitedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"rate limited; retry in {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


def check_rate_limit(
    keys: list[str],
    *,
    max_attempts: int,
    window_seconds: int,
) -> None:
    """Record one attempt against each key; raise RateLimitedError if any is over limit."""
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        for key in keys:
            bucket = _events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_attempts:
                retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
                raise RateLimitedError(retry_after)
            bucket.append(now)


def reset() -> None:
    """Clear all counters (tests)."""
    with _lock:
        _events.clear()
