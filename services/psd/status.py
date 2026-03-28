from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PSDSyncStatus:
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    in_progress: bool = False
    mode: str | None = None
    pages_fetched: int = 0
    pages_skipped: int = 0
    pages_missing: int = 0
    documents_downloaded: int = 0
    documents_skipped: int = 0
    documents_discovered: int = 0
    documents_missing: int = 0
    current_step: str | None = None
    current_url: str | None = None
    output_dir: str | None = None
    manifest_path: str | None = None
    last_result: dict[str, Any] = field(default_factory=dict)
