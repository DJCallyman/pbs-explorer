from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable

from sqlalchemy.orm import Session

from services.sync.client import PBSAPIClient
from services.sync.parser import parse_csv
from services.sync.status import SyncStatus
from services.sync.status_store import status_store
from services.sync.upsert import upsert_rows


class SyncOrchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = PBSAPIClient()
        self.status = SyncStatus()
        self.logger = logging.getLogger("sync")
        status_store.set(self.status)

    async def sync_endpoint(
        self,
        endpoint: str,
        model,
        key_fields: Iterable[str],
        extra_fields: Dict | None = None,
    ) -> int:
        self.status.in_progress = True
        self.status.current_endpoint = endpoint
        self.status.last_run_at = datetime.utcnow()
        self.logger.info("Sync start: %s", endpoint)
        response = await self.client.get(endpoint)
        rows = parse_csv(response.text)
        count = upsert_rows(self.session, model, rows, key_fields, extra_fields=extra_fields)
        self.status.records_processed += count
        self.status.last_success_at = datetime.utcnow()
        self.status.in_progress = False
        self.status.current_endpoint = None
        self.logger.info("Sync complete: %s (%s rows)", endpoint, count)
        return count

    async def sync_all(self, plan: Dict[str, Dict]) -> Dict[str, int]:
        results: Dict[str, int] = {}
        for endpoint, meta in plan.items():
            try:
                results[endpoint] = await self.sync_endpoint(
                    endpoint=endpoint,
                    model=meta["model"],
                    key_fields=meta.get("key_fields", []),
                    extra_fields=meta.get("extra_fields"),
                )
            except Exception as exc:  # noqa: BLE001
                self.status.last_error = str(exc)
                self.status.in_progress = False
                self.logger.exception("Sync failed: %s", endpoint)
                raise
        return results
