from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import MedicineStatusEntry
from services.medicine_status.parser import (
    MEDICINE_STATUS_BASE_URL,
    normalize_medicine_name,
    parse_detail_page,
    parse_search_page,
)
from services.psd.client import PoliteHTTPClient


@dataclass(slots=True)
class MedicineStatusSyncStats:
    search_pages_fetched: int = 0
    detail_pages_fetched: int = 0
    detail_pages_skipped: int = 0
    entries_upserted: int = 0
    total_results: int = 0


class MedicineStatusSync:
    def __init__(self, db: Session, *, delay_seconds: float = 0.5, detail_refresh_days: int = 30) -> None:
        self.db = db
        self.client = PoliteHTTPClient(delay_seconds=delay_seconds)
        self.stats = MedicineStatusSyncStats()
        self.detail_refresh_interval = timedelta(days=max(detail_refresh_days, 0))

    async def aclose(self) -> None:
        await self.client.aclose()

    async def run(self, *, max_pages: int | None = None) -> dict[str, int]:
        first_page = await self._fetch_search_page(1)
        total_pages = first_page.total_pages if max_pages is None else min(first_page.total_pages, max_pages)
        await self._sync_entries(first_page.entries)

        for page_number in range(2, total_pages + 1):
            page = await self._fetch_search_page(page_number)
            await self._sync_entries(page.entries)

        self.db.commit()
        return asdict(self.stats)

    async def _fetch_search_page(self, page_number: int):
        url = f"{MEDICINE_STATUS_BASE_URL}/medicinestatus/search.html?sort=psproperty-drug-name&page={page_number}"
        response = await self.client.request("GET", url)
        page = parse_search_page(response.text)
        self.stats.search_pages_fetched += 1
        self.stats.total_results = max(self.stats.total_results, page.total_results)
        return page

    async def _sync_entries(self, entries) -> None:
        for entry in entries:
            record = self.db.get(MedicineStatusEntry, entry.medicine_status_id)
            if record is None:
                record = MedicineStatusEntry(medicine_status_id=entry.medicine_status_id)
                self.db.add(record)

            needs_detail_refresh = self._needs_detail_refresh(record, entry)

            record.document_url = entry.document_url
            record.drug_name = entry.drug_name
            record.drug_name_normalized = normalize_medicine_name(entry.drug_name)
            record.brand_names = entry.brand_names
            record.sponsor = entry.sponsor
            record.purpose = entry.purpose
            record.meeting_date = entry.meeting_date
            record.meeting_date_label = entry.meeting_date_label
            record.listing_outcome_status = entry.listing_outcome_status

            if not needs_detail_refresh:
                record.last_synced_at = datetime.now(timezone.utc)
                self.stats.detail_pages_skipped += 1
                self.stats.entries_upserted += 1
                continue

            response = await self.client.request("GET", entry.document_url)
            detail = parse_detail_page(response.text)
            record.drug_name = detail.drug_name or entry.drug_name
            record.drug_name_normalized = normalize_medicine_name(detail.drug_name or entry.drug_name)
            record.brand_names = detail.brand_names or entry.brand_names
            record.sponsor = detail.sponsor or entry.sponsor
            record.purpose = detail.purpose or entry.purpose
            record.pbac_meeting_date = detail.pbac_meeting_date
            record.pbac_outcome_published_text = detail.pbac_outcome_published_text
            record.pbac_outcome_published_url = detail.pbac_outcome_published_url
            record.public_summary_title = detail.public_summary_title
            record.public_summary_url = detail.public_summary_url
            record.status = detail.status
            record.page_last_updated = detail.page_last_updated
            record.last_synced_at = datetime.now(timezone.utc)

            self.stats.detail_pages_fetched += 1
            self.stats.entries_upserted += 1

    def _needs_detail_refresh(self, record: MedicineStatusEntry, entry) -> bool:
        if not record.pbac_outcome_published_text and not record.public_summary_url and not record.status:
            return True

        if (
            record.document_url != entry.document_url
            or record.drug_name != entry.drug_name
            or (record.brand_names or "") != (entry.brand_names or "")
            or (record.sponsor or "") != (entry.sponsor or "")
            or (record.purpose or "") != (entry.purpose or "")
            or record.meeting_date != entry.meeting_date
            or (record.meeting_date_label or "") != (entry.meeting_date_label or "")
            or (record.listing_outcome_status or "") != (entry.listing_outcome_status or "")
        ):
            return True

        if self.detail_refresh_interval == timedelta(0):
            return False

        if record.last_synced_at is None:
            return True

        last_synced = record.last_synced_at
        if last_synced.tzinfo is None:
            last_synced = last_synced.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) - last_synced >= self.detail_refresh_interval
