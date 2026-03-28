from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import time


WINDOW_SECONDS = 15 * 60
MAX_FAILURES = 8
BLOCK_SECONDS = 30 * 60
MAX_TRACKED_KEYS = 2048


@dataclass(slots=True)
class _Entry:
    failures: deque[float]
    blocked_until: float = 0.0


class AuthRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, _Entry] = {}

    def _prune(self, now: float) -> None:
        stale_before = now - max(WINDOW_SECONDS, BLOCK_SECONDS)
        removable = [
            key
            for key, entry in self._entries.items()
            if not entry.failures and entry.blocked_until < stale_before
        ]
        for key in removable:
            self._entries.pop(key, None)
        if len(self._entries) > MAX_TRACKED_KEYS:
            oldest_keys = sorted(
                self._entries.keys(),
                key=lambda key: (
                    self._entries[key].blocked_until,
                    self._entries[key].failures[0] if self._entries[key].failures else 0.0,
                ),
            )[: len(self._entries) - MAX_TRACKED_KEYS]
            for key in oldest_keys:
                self._entries.pop(key, None)

    def _entry_for(self, key: str) -> _Entry:
        entry = self._entries.get(key)
        if entry is None:
            entry = _Entry(failures=deque())
            self._entries[key] = entry
        return entry

    def _trim_failures(self, entry: _Entry, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while entry.failures and entry.failures[0] < cutoff:
            entry.failures.popleft()

    def check(self, key: str) -> int:
        now = time()
        with self._lock:
            self._prune(now)
            entry = self._entries.get(key)
            if entry is None:
                return 0
            self._trim_failures(entry, now)
            if entry.blocked_until > now:
                return max(int(entry.blocked_until - now), 1)
            if entry.blocked_until:
                entry.blocked_until = 0.0
            return 0

    def record_failure(self, key: str) -> int:
        now = time()
        with self._lock:
            self._prune(now)
            entry = self._entry_for(key)
            self._trim_failures(entry, now)
            entry.failures.append(now)
            if len(entry.failures) >= MAX_FAILURES:
                entry.blocked_until = now + BLOCK_SECONDS
                entry.failures.clear()
                return BLOCK_SECONDS
            return 0

    def clear(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)


auth_rate_limiter = AuthRateLimiter()

