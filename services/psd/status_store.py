from __future__ import annotations

from threading import Lock
from typing import Optional

from services.psd.status import PSDSyncStatus


class PSDStatusStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._status: Optional[PSDSyncStatus] = None

    def set(self, status: PSDSyncStatus) -> None:
        with self._lock:
            self._status = status

    def get(self) -> Optional[PSDSyncStatus]:
        with self._lock:
            return self._status


psd_status_store = PSDStatusStore()
