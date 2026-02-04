from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Iterable, Optional
from urllib.parse import urljoin, urlparse

import httpx
from httpx import HTTPStatusError
from sqlalchemy.orm import Session

from services.sync.client import PBSAPIClient
from services.sync.incremental import IncrementalSync
from services.sync.parser import parse_json
from services.sync.status import SyncStatus
from services.sync.status_store import status_store
from services.sync.upsert import upsert_rows
from services.sync.plan import SYNC_PLAN, STATIC_ENDPOINTS
from db.models import SyncState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SyncOrchestrator:
    def __init__(self, session: Session, request_delay_seconds: float = 1.0) -> None:
        self.session = session
        self.client = PBSAPIClient()
        self.incremental_sync = IncrementalSync(session)
        # Only create new status if none exists in store (running sync keeps its status)
        existing_status = status_store.get()
        if existing_status:
            self.status = existing_status
        else:
            self.status = SyncStatus()
            status_store.set(self.status)
        self.logger = logging.getLogger("sync")
        self.start_time = None
        self.endpoint_times = {}
        self.request_delay_seconds = request_delay_seconds
        self.last_request_time = 0

    async def _enforce_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay_seconds:
            wait_time = self.request_delay_seconds - elapsed
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()

    async def sync_endpoint(
        self,
        endpoint: str,
        model,
        key_fields: Iterable[str],
        extra_fields: Dict | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> int:
        endpoint_start = time.time()
        self.status.in_progress = True
        self.status.current_endpoint = endpoint
        self.status.last_run_at = datetime.utcnow()

        self.logger.info(f"Starting sync for endpoint: {endpoint}")

        all_rows = []
        next_url = endpoint
        page_count = 0
        total_rows_fetched = 0

        if "?" not in endpoint:
            next_url = f"{endpoint}?limit=40000"
        else:
            next_url = f"{endpoint}&limit=40000"

        while next_url:
            try:
                await self._enforce_rate_limit()

                if page_count == 0:
                    self.logger.debug(f"Fetching page 1 from {endpoint}...")
                    response = await self.client.get(next_url)
                else:
                    self.logger.debug(f"Fetching page {page_count + 1} from {endpoint}...")
                    response = await self.client.get(next_url)
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 60
                    self.logger.warning(
                        f"Rate limited (429) on {endpoint} page {page_count + 1}. "
                        f"Pausing {wait_time}s before retry..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
            except httpx.ReadTimeout:
                wait_time = 60
                self.logger.warning(
                    f"Read timeout on {endpoint} page {page_count + 1}. "
                    f"Pausing {wait_time}s before retry..."
                )
                await asyncio.sleep(wait_time)
                continue

            rows, metadata = parse_json(response.text)
            all_rows.extend(rows)
            total_rows_fetched += len(rows)
            page_count += 1

            self.logger.info(f"  Page {page_count}: {len(rows)} records (total so far: {total_rows_fetched})")

            next_url = None
            if metadata.get("_links"):
                for link in metadata["_links"]:
                    if link.get("rel") == "next":
                        href = link.get("href")
                        if href:
                            if href.startswith("/api/v3/"):
                                next_url = href[8:]
                            elif href.startswith("https://") or href.startswith("http://"):
                                parsed = urlparse(href)
                                next_url = parsed.path.replace("/api/v3/", "", 1)
                                if parsed.query:
                                    next_url = f"{next_url}?{parsed.query}"
                            else:
                                next_url = href
                        break

        self.logger.info(f"All pages fetched for {endpoint}. Processing {total_rows_fetched} total records...")
        synced_count = upsert_rows(self.session, model, all_rows, key_fields, extra_fields=extra_fields)

        # Extract schedule_code from the first row if available
        used_schedule_code = None
        if all_rows:
            for row in all_rows:
                if row.get("schedule_code"):
                    used_schedule_code = str(row["schedule_code"])
                    break

        self.status.records_processed += synced_count
        self.status.last_success_at = datetime.utcnow()
        self.status.in_progress = False
        self.status.current_endpoint = None

        elapsed = time.time() - endpoint_start
        self.endpoint_times[endpoint] = elapsed

        self.logger.info(
            f"Sync complete: {endpoint}\n"
            f"  Records: {synced_count} | Pages: {page_count} | Time: {elapsed:.1f}s"
        )
        return total_rows_fetched, synced_count, used_schedule_code

    async def sync_all_full(self) -> Dict[str, int]:
        # Reset status for new sync run
        self.status.in_progress = True
        self.status.current_endpoint = None
        self.status.last_error = None
        self.status.records_processed = 0
        
        self.start_time = time.time()
        results: Dict[str, int] = {}
        total_endpoints = len(SYNC_PLAN)
        current_endpoint_num = 0

        self.logger.info("=" * 80)
        self.logger.info("Starting FULL PBS API Sync - all endpoints")
        self.logger.info("=" * 80)

        for endpoint, meta in SYNC_PLAN.items():
            current_endpoint_num += 1
            elapsed_total = time.time() - self.start_time

            if current_endpoint_num > 1:
                avg_time_per_endpoint = elapsed_total / (current_endpoint_num - 1)
                est_remaining = avg_time_per_endpoint * (total_endpoints - current_endpoint_num)
                est_remaining_str = f" | Est. remaining: {est_remaining:.0f}s"
            else:
                est_remaining_str = ""

            self.logger.info(
                f"\n[{current_endpoint_num}/{total_endpoints}] Processing {endpoint}"
                f" | Elapsed: {elapsed_total:.0f}s{est_remaining_str}"
            )

            try:
                fetched, synced, used_schedule = await self.sync_endpoint(
                    endpoint=endpoint,
                    model=meta["model"],
                    key_fields=meta.get("key_fields", []),
                    extra_fields=meta.get("extra_fields"),
                )
                results[endpoint] = {"fetched": fetched, "synced": synced}
                self._update_sync_state(endpoint, fetched, synced, used_schedule, "full")
            except Exception as exc:
                self.status.last_error = str(exc)
                self.status.in_progress = False
                self.logger.exception(f"Sync failed: {endpoint}")
                raise

        total_time = time.time() - self.start_time
        total_synced = sum(r.get("synced", 0) for r in results.values())
        total_fetched = sum(r.get("fetched", 0) for r in results.values())

        self.logger.info("\n" + "=" * 80)
        self.logger.info("FULL SYNC COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"Total endpoints: {total_endpoints}")
        self.logger.info(f"Total records fetched: {total_fetched}")
        self.logger.info(f"Total records synced: {total_synced}")
        self.logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f}m)")

        if self.endpoint_times:
            slowest = max(self.endpoint_times.items(), key=lambda x: x[1])
            fastest = min(self.endpoint_times.items(), key=lambda x: x[1])
            slowest_time = slowest[1]
            fastest_time = fastest[1]
            self.logger.info(f"Slowest endpoint: {slowest[0]} ({slowest_time:.1f}s)")
            self.logger.info(f"Fastest endpoint: {fastest[0]} ({fastest_time:.1f}s)")

        self.logger.info("=" * 80)

        # Mark sync as complete
        self.status.in_progress = False
        self.status.last_success_at = datetime.utcnow()
        self.status.current_endpoint = None

        return results

    async def sync_endpoints(self, endpoints: list) -> Dict[str, int]:
        """Sync only specific endpoints."""
        # Reset status for new sync run
        self.status.in_progress = True
        self.status.current_endpoint = None
        self.status.last_error = None
        self.status.records_processed = 0

        self.start_time = time.time()
        results: Dict[str, int] = {}
        total_endpoints = len(endpoints)
        current_endpoint_num = 0

        self.logger.info("=" * 80)
        self.logger.info(f"Starting SYNC for {len(endpoints)} endpoints: {', '.join(endpoints[:5])}{'...' if len(endpoints) > 5 else ''}")
        self.logger.info("=" * 80)

        for endpoint in endpoints:
            if endpoint not in SYNC_PLAN:
                self.logger.warning(f"Unknown endpoint: {endpoint}, skipping")
                continue

            current_endpoint_num += 1
            meta = SYNC_PLAN[endpoint]
            elapsed_total = time.time() - self.start_time

            if current_endpoint_num > 1:
                avg_time_per_endpoint = elapsed_total / (current_endpoint_num - 1)
                est_remaining = avg_time_per_endpoint * (total_endpoints - current_endpoint_num)
                est_remaining_str = f" | Est. remaining: {est_remaining:.0f}s"
            else:
                est_remaining_str = ""

            self.logger.info(
                f"\n[{current_endpoint_num}/{total_endpoints}] Processing {endpoint}"
                f" | Elapsed: {elapsed_total:.0f}s{est_remaining_str}"
            )

            try:
                fetched, synced, used_schedule = await self.sync_endpoint(
                    endpoint=endpoint,
                    model=meta["model"],
                    key_fields=meta.get("key_fields", []),
                    extra_fields=meta.get("extra_fields"),
                )
                results[endpoint] = {"fetched": fetched, "synced": synced}
                self._update_sync_state(endpoint, fetched, synced, used_schedule, "endpoint")
            except Exception as exc:
                self.status.last_error = str(exc)
                self.status.in_progress = False
                self.logger.exception(f"Sync failed: {endpoint}")
                raise

        total_time = time.time() - self.start_time
        total_synced = sum(r.get("synced", 0) for r in results.values())
        total_fetched = sum(r.get("fetched", 0) for r in results.values())

        self.logger.info("\n" + "=" * 80)
        self.logger.info("ENDPOINT SYNC COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"Total endpoints: {total_endpoints}")
        self.logger.info(f"Total records fetched: {total_fetched}")
        self.logger.info(f"Total records synced: {total_synced}")
        self.logger.info(f"Total time: {total_time:.1f}s")
        self.logger.info("=" * 80)

        # Mark sync as complete
        self.status.in_progress = False
        self.status.last_success_at = datetime.utcnow()
        self.status.current_endpoint = None

        return results

    async def sync_all_incremental(self) -> Dict[str, int]:
        # Reset status for new sync run
        self.status.in_progress = True
        self.status.current_endpoint = None
        self.status.last_error = None
        self.status.records_processed = 0

        self.start_time = time.time()

        latest_api_schedule = await self.incremental_sync.get_latest_schedule_code()
        current_db_schedule = await self.incremental_sync.get_current_db_schedule()

        if not latest_api_schedule:
            raise Exception("Could not get latest schedule from API")

        if not current_db_schedule:
            self.logger.warning("No schedule found in database. Performing full sync instead.")
            return await self.sync_all_full()

        if latest_api_schedule == current_db_schedule:
            self.logger.info(f"Database is already at latest schedule ({latest_api_schedule}). No sync needed.")
            return {}

        previous_schedule = await self.incremental_sync.get_previous_db_schedule(latest_api_schedule)

        self.logger.info("=" * 80)
        self.logger.info("Starting INCREMENTAL PBS API Sync")
        self.logger.info(f"Previous DB schedule: {previous_schedule or 'none'}")
        self.logger.info(f"Current DB schedule: {current_db_schedule}")
        self.logger.info(f"Latest API schedule: {latest_api_schedule}")
        self.logger.info("=" * 80)

        results: Dict[str, int] = {}
        total_endpoints = len(SYNC_PLAN)
        current_endpoint_num = 0

        for endpoint, meta in SYNC_PLAN.items():
            current_endpoint_num += 1
            is_static = meta.get("is_static", False)

            self.logger.info(
                f"\n[{current_endpoint_num}/{total_endpoints}] Processing {endpoint} "
                f"({'static - full sync' if is_static else 'incremental'})"
            )

            try:
                if is_static:
                    fetched, synced, used_schedule = await self.sync_endpoint(
                        endpoint=endpoint,
                        model=meta["model"],
                        key_fields=meta.get("key_fields", []),
                        extra_fields=meta.get("extra_fields"),
                    )
                else:
                    synced = await self.incremental_sync.sync_endpoint_incremental(
                        endpoint=endpoint,
                        model=meta["model"],
                        key_fields=meta.get("key_fields", []),
                        source_schedule=current_db_schedule,
                        target_schedule=latest_api_schedule,
                    )
                    fetched = synced  # Incremental applies changes directly
                    used_schedule = latest_api_schedule

                results[endpoint] = {"fetched": fetched, "synced": synced}
                self._update_sync_state(endpoint, fetched, synced, used_schedule, "incremental")

            except Exception as exc:
                self.logger.warning(f"Incremental sync failed for {endpoint}: {exc}")
                self.logger.info(f"Falling back to full sync for {endpoint}...")
                try:
                    fetched, synced, used_schedule = await self.sync_endpoint(
                        endpoint=endpoint,
                        model=meta["model"],
                        key_fields=meta.get("key_fields", []),
                        extra_fields=meta.get("extra_fields"),
                    )
                    results[endpoint] = {"fetched": fetched, "synced": synced}
                    self._update_sync_state(endpoint, fetched, synced, used_schedule, "incremental_fallback")
                except Exception as e:
                    self.status.last_error = str(e)
                    self.logger.exception(f"Sync failed: {endpoint}")
                    raise

        total_time = time.time() - self.start_time
        total_synced = sum(r.get("synced", 0) for r in results.values())
        total_fetched = sum(r.get("fetched", 0) for r in results.values())

        self.logger.info("\n" + "=" * 80)
        self.logger.info("INCREMENTAL SYNC COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"Total endpoints: {total_endpoints}")
        self.logger.info(f"Total records synced: {total_synced}")
        self.logger.info(f"Total time: {total_time:.1f}s")
        self.logger.info("=" * 80)

        # Mark sync as complete
        self.status.in_progress = False
        self.status.last_success_at = datetime.utcnow()
        self.status.current_endpoint = None

        return results

    def _update_sync_state(
        self,
        endpoint: str,
        records_fetched: int,
        records_synced: int,
        used_schedule: str | None,
        sync_type: str,
    ) -> None:
        from sqlalchemy import select
        from db.models import Schedule

        # Use the schedule that was actually used during sync, or fall back to latest
        schedule_to_record = used_schedule
        if not schedule_to_record:
            result = self.session.execute(
                select(Schedule.schedule_code).order_by(Schedule.effective_date.desc()).limit(1)
            )
            schedule_to_record = result.scalar()

        existing = self.session.query(SyncState).filter_by(endpoint=endpoint).first()

        if existing:
            existing.last_synced_schedule_code = schedule_to_record
            existing.last_synced_at = datetime.utcnow()
            existing.records_synced = records_synced
            existing.records_fetched = records_fetched
            existing.sync_type = sync_type
        else:
            sync_state = SyncState(
                endpoint=endpoint,
                last_synced_schedule_code=schedule_to_record,
                last_synced_at=datetime.utcnow(),
                records_synced=records_synced,
                records_fetched=records_fetched,
                sync_type=sync_type,
            )
            self.session.add(sync_state)

        self.session.commit()

    def get_sync_status(self) -> Dict[str, Any]:
        from sqlalchemy import select, func
        from db.models import Schedule

        result = self.session.execute(select(func.max(Schedule.schedule_code)))
        latest_schedule = result.scalar()

        result = self.session.execute(select(func.count(SyncState.endpoint)))
        sync_state_count = result.scalar()

        result = self.session.execute(
            select(SyncState).order_by(SyncState.last_synced_at.desc()).limit(1)
        )
        last_sync = result.scalar_one_or_none()

        # Get the global status from the store (not the local instance)
        global_status = status_store.get()

        return {
            "in_progress": global_status.in_progress if global_status else False,
            "current_endpoint": global_status.current_endpoint if global_status else None,
            "last_run_at": global_status.last_run_at.isoformat() if global_status and global_status.last_run_at else None,
            "last_success_at": global_status.last_success_at.isoformat() if global_status and global_status.last_success_at else None,
            "last_error": global_status.last_error if global_status else None,
            "records_processed": global_status.records_processed if global_status else 0,
            "latest_db_schedule": latest_schedule,
            "sync_state_count": sync_state_count,
            "last_sync": {
                "type": last_sync.sync_type if last_sync else None,
                "at": last_sync.last_synced_at.isoformat() if last_sync and last_sync.last_synced_at else None,
                "records": last_sync.records_synced if last_sync else None,
            } if last_sync else None,
        }

    def get_sync_history(self) -> list:
        from sqlalchemy import select
        from db.models import SyncState

        result = self.session.execute(
            select(SyncState).order_by(SyncState.last_synced_at.desc()).limit(100)
        )
        rows = result.scalars().all()

        return [
            {
                "endpoint": row.endpoint,
                "sync_type": row.sync_type,
                "records_synced": row.records_synced,
                "records_fetched": row.records_fetched,
                "schedule_code": row.last_synced_schedule_code,
                "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
            }
            for row in rows
        ]
