from __future__ import annotations

from datetime import datetime, timezone

from services.psd.crawler import PSDCrawler
from services.psd.search_index import build_search_index
from services.psd.status import PSDSyncStatus
from services.psd.status_store import psd_status_store


def get_or_create_status() -> PSDSyncStatus:
    existing = psd_status_store.get()
    if existing:
        return existing
    status = PSDSyncStatus()
    psd_status_store.set(status)
    return status


async def run_psd_job(
    *,
    mode: str,
    output_dir: str = "data/pbs_documents",
    delay_seconds: float = 1.5,
    max_concurrency: int = 2,
    max_documents: int | None = None,
    sample_per_source: int | None = None,
) -> dict:
    status = get_or_create_status()
    status.in_progress = True
    status.mode = mode
    status.last_run_at = datetime.now(timezone.utc)
    status.last_error = None
    status.current_step = "Starting PSD crawler"
    status.pages_fetched = 0
    status.pages_skipped = 0
    status.pages_missing = 0
    status.documents_downloaded = 0
    status.documents_skipped = 0
    status.documents_discovered = 0
    status.documents_missing = 0
    status.current_url = None
    status.output_dir = output_dir
    status.manifest_path = f"{output_dir.rstrip('/')}/manifest.json"

    async def on_progress(progress: dict) -> None:
        status.current_step = progress.get("current_step")
        status.current_url = progress.get("current_url")
        status.pages_fetched = progress.get("pages_fetched", 0)
        status.pages_skipped = progress.get("pages_skipped", 0)
        status.pages_missing = progress.get("pages_missing", 0)
        status.documents_downloaded = progress.get("documents_downloaded", 0)
        status.documents_skipped = progress.get("documents_skipped", 0)
        status.documents_discovered = progress.get("documents_discovered", 0)
        status.documents_missing = progress.get("documents_missing", 0)
        status.output_dir = progress.get("output_dir", status.output_dir)
        status.manifest_path = progress.get("manifest_path", status.manifest_path)

    crawler = PSDCrawler(
        output_dir=output_dir,
        delay_seconds=delay_seconds,
        max_concurrency=max_concurrency,
        progress_callback=on_progress,
    )
    try:
        if mode == "discover":
            status.current_step = "Scanning PSD pages"
            result = await crawler.crawl_with_options(download_documents=False)
        elif mode in {"download", "sample"}:
            status.current_step = "Downloading preferred files"
            result = await crawler.download_from_manifest(
                max_documents=max_documents,
                sample_per_source=sample_per_source,
            )
        else:
            raise ValueError(f"Unsupported PSD job mode: {mode}")
        if mode in {"download", "sample"}:
            status.current_step = "Building search index"
            search_index = build_search_index(f"{output_dir.rstrip('/')}/manifest.json")
            result["search_index"] = {
                "built_entries": search_index["built_entries"],
                "searchable_entries": search_index["searchable_entries"],
            }
        status.pages_fetched = result["stats"]["pages_fetched"]
        status.pages_skipped = result["stats"]["pages_skipped"]
        status.pages_missing = result["stats"]["pages_missing"]
        status.documents_downloaded = result["stats"]["documents_downloaded"]
        status.documents_skipped = result["stats"]["documents_skipped"]
        status.documents_discovered = result["stats"]["documents_discovered"]
        status.documents_missing = result["stats"]["documents_missing"]
        status.last_success_at = datetime.now(timezone.utc)
        status.last_result = result
        status.current_step = "Completed"
        status.current_url = None
        return result
    except Exception as exc:
        status.last_error = str(exc)
        status.current_step = "Failed"
        status.current_url = None
        raise
    finally:
        status.in_progress = False
