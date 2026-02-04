from __future__ import annotations

from threading import Lock
from typing import Optional

from services.sync.status import SyncStatus


class SyncStatusStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._status: Optional[SyncStatus] = None

    def set(self, status: SyncStatus) -> None:
        with self._lock:
            self._status = status

    def get(self) -> Optional[SyncStatus]:
        with self._lock:
            return self._status


status_store = SyncStatusStore()
