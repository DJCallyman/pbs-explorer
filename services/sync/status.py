from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SyncStatus:
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    in_progress: bool = False
    records_processed: int = 0
    current_endpoint: Optional[str] = None
