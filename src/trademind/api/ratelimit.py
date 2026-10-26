"""A small in-memory rate limiter, so one visitor cannot use up the server.

It counts uploads per client address over a sliding window. Nothing is written to disk. Addresses
are kept only until their window passes. Behind a proxy, run the server with proxy headers on so
the address is the visitor's, not the proxy's.
"""

import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

_MAX_TRACKED_ADDRESSES = 10_000


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window: timedelta,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._limit = limit
        self._window = window
        self._now = now
        self._hits: dict[str, deque[datetime]] = {}
        self._lock = threading.Lock()

    def allow(self, address: str) -> bool:
        """Record an attempt. False if this address has used up its allowance."""
        with self._lock:
            now = self._now()
            self._forget_old(now)
            hits = self._hits.setdefault(address, deque())
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True

    def retry_after_seconds(self, address: str) -> int:
        """How long until this address may try again. 0 if it may now."""
        with self._lock:
            hits = self._hits.get(address)
            if not hits or len(hits) < self._limit:
                return 0
            wait = hits[0] + self._window - self._now()
            return max(1, int(wait.total_seconds()) + 1)

    def _forget_old(self, now: datetime) -> None:
        cutoff = now - self._window
        for address in list(self._hits):
            hits = self._hits[address]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if not hits:
                del self._hits[address]
        # A flood of different addresses must not fill memory.
        while len(self._hits) > _MAX_TRACKED_ADDRESSES:
            del self._hits[next(iter(self._hits))]
