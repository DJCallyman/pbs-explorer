from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Iterable
from urllib.parse import urljoin, urlparse

import httpx
from httpx import HTTPStatusError
from sqlalchemy.orm import Session

from services.sync.client import PBSAPIClient
from services.sync.parser import parse_json
from services.sync.status import SyncStatus
from services.sync.status_store import status_store
from services.sync.upsert import upsert_rows


class SyncOrchestrator:
    def __init__(self, session: Session, request_delay_seconds: float = 1.0) -> None:
        self.session = session
        self.client = PBSAPIClient()
        self.status = SyncStatus()
        self.logger = logging.getLogger("sync")
        status_store.set(self.status)
        self.start_time = None
        self.endpoint_times = {}
        self.request_delay_seconds = request_delay_seconds
        self.last_request_time = 0

    async def _enforce_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
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
        
        # Add limit parameter to fetch 40000 records per page
        if "?" not in endpoint:
            next_url = f"{endpoint}?limit=40000"
        else:
            next_url = f"{endpoint}&limit=40000"
        
        while next_url:
            try:
                # Enforce rate limiting before each request
                await self._enforce_rate_limit()
                
                if page_count == 0:
                    # First page - use endpoint with limit parameter
                    self.logger.debug(f"Fetching page 1 from {endpoint}...")
                    response = await self.client.get(next_url)
                else:
                    # Subsequent pages - use full URL path from API metadata
                    self.logger.debug(f"Fetching page {page_count + 1} from {endpoint}...")
                    response = await self.client.get(next_url)
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Hit rate limit on this page - pause and retry this specific page request
                    wait_time = 60
                    self.logger.warning(
                        f"⚠️  Rate limited (429) on {endpoint} page {page_count + 1}. "
                        f"Pausing {wait_time}s before retry..."
                    )
                    await asyncio.sleep(wait_time)
                    # Don't increment page_count, just retry the same page
                    continue
                else:
                    # Not a rate limit error
                    raise
            except httpx.ReadTimeout:
                # Hit read timeout on this page - pause and retry this specific page request
                wait_time = 60
                self.logger.warning(
                    f"⚠️  Read timeout on {endpoint} page {page_count + 1}. "
                    f"Pausing {wait_time}s before retry..."
                )
                await asyncio.sleep(wait_time)
                # Don't increment page_count, just retry the same page
                continue
            
            rows, metadata = parse_json(response.text)
            all_rows.extend(rows)
            total_rows_fetched += len(rows)
            page_count += 1
            
            self.logger.info(f"  Page {page_count}: {len(rows)} records (total so far: {total_rows_fetched})")
            
            # Check for next page in _links from metadata
            next_url = None
            if metadata.get("_links"):
                for link in metadata["_links"]:
                    if link.get("rel") == "next":
                        href = link.get("href")
                        if href:
                            # Extract path and query from the href URL
                            # API returns full paths like "/api/v3/organisations?limit=1000&page=2"
                            # Remove leading "/api/v3/" to get just the endpoint path
                            if href.startswith("/api/v3/"):
                                next_url = href[8:]  # Remove "/api/v3/"
                            elif href.startswith("https://") or href.startswith("http://"):
                                # If it's a full URL, extract the path and query
                                parsed = urlparse(href)
                                next_url = parsed.path.replace("/api/v3/", "", 1)
                                if parsed.query:
                                    next_url = f"{next_url}?{parsed.query}"
                            else:
                                next_url = href
                        break
        
        self.logger.info(f"All pages fetched for {endpoint}. Processing {total_rows_fetched} total records...")
        count = upsert_rows(self.session, model, all_rows, key_fields, extra_fields=extra_fields)
        
        self.status.records_processed += count
        self.status.last_success_at = datetime.utcnow()
        self.status.in_progress = False
        self.status.current_endpoint = None
        
        elapsed = time.time() - endpoint_start
        self.endpoint_times[endpoint] = elapsed
        
        self.logger.info(
            f"✓ Sync complete: {endpoint}\n"
            f"  Records: {count} | Pages: {page_count} | Time: {elapsed:.1f}s"
        )
        return count

    async def sync_all(self, plan: Dict[str, Dict]) -> Dict[str, int]:
        self.start_time = time.time()
        results: Dict[str, int] = {}
        total_endpoints = len(plan)
        current_endpoint_num = 0
        
        self.logger.info("=" * 80)
        self.logger.info(f"Starting PBS API Sync - {total_endpoints} endpoints to process")
        self.logger.info("=" * 80)
        
        for endpoint, meta in plan.items():
            current_endpoint_num += 1
            elapsed_total = time.time() - self.start_time
            
            # Calculate estimated time remaining
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
                results[endpoint] = await self.sync_endpoint(
                    endpoint=endpoint,
                    model=meta["model"],
                    key_fields=meta.get("key_fields", []),
                    extra_fields=meta.get("extra_fields"),
                )
            except Exception as exc:  # noqa: BLE001
                self.status.last_error = str(exc)
                self.status.in_progress = False
                self.logger.exception(f"❌ Sync failed: {endpoint}")
                raise
        
        # Print summary
        total_time = time.time() - self.start_time
        total_records = sum(results.values())
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info("✓ SYNC COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"Total endpoints: {total_endpoints}")
        self.logger.info(f"Total records synced: {total_records}")
        self.logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f}m)")
        self.logger.info(f"Average time per endpoint: {total_time/total_endpoints:.1f}s")
        
        if self.endpoint_times:
            slowest = max(self.endpoint_times.items(), key=lambda x: x[1])
            fastest = min(self.endpoint_times.items(), key=lambda x: x[1])
            self.logger.info(f"Slowest endpoint: {slowest[0]} ({slowest[1]:.1f}s)")
            self.logger.info(f"Fastest endpoint: {fastest[0]} ({fastest[1]:.1f}s)")
        
        self.logger.info("=" * 80)
        
        return results
