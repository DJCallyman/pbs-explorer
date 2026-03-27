from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx

from services.psd.client import PoliteHTTPClient
from services.psd.manifest import ManifestStore, utc_now_iso
from services.psd.parser import detect_source, is_product_page, parse_psd_page


DEFAULT_INDEX_URLS = [
    "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/public-summary-documents-by-product",
    "https://www.pbs.gov.au/info/industry/listing/participants/public-release-docs/dusc-public-release-documents-by-medicine",
]


@dataclass(slots=True)
class CrawlStats:
    pages_fetched: int = 0
    pages_skipped: int = 0
    pages_missing: int = 0
    documents_downloaded: int = 0
    documents_skipped: int = 0
    documents_missing: int = 0


class PSDCrawler:
    def __init__(
        self,
        output_dir: str | Path = "data/pbs_documents",
        delay_seconds: float = 1.5,
        max_concurrency: int = 2,
        progress_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.manifest_store = ManifestStore(self.output_dir / "manifest.json")
        self.client = PoliteHTTPClient(delay_seconds=delay_seconds)
        self.max_concurrency = max_concurrency
        self.stats = CrawlStats()
        self.progress_callback = progress_callback

    async def aclose(self) -> None:
        await self.client.aclose()

    async def crawl(self, download_documents: bool = False, max_documents: int | None = None) -> dict[str, Any]:
        return await self.crawl_with_options(
            download_documents=download_documents,
            max_documents=max_documents,
        )

    async def download_from_manifest(
        self,
        *,
        max_documents: int | None = None,
        sample_per_source: int | None = None,
    ) -> dict[str, Any]:
        manifest = self.manifest_store.load()
        if not manifest.get("pages"):
            raise ValueError("No document manifest found yet. Run a scan first.")

        await self._download_documents(
            manifest,
            max_documents=max_documents,
            sample_per_source=sample_per_source,
        )
        self.manifest_store.save(manifest)
        return {
            "output_dir": str(self.output_dir),
            "stats": {
                "pages_fetched": self.stats.pages_fetched,
                "pages_skipped": self.stats.pages_skipped,
                "pages_missing": self.stats.pages_missing,
                "documents_downloaded": self.stats.documents_downloaded,
                "documents_skipped": self.stats.documents_skipped,
                "documents_missing": self.stats.documents_missing,
                "documents_discovered": len(manifest["documents"]),
            },
            "manifest_path": str(self.manifest_store.path),
        }

    async def crawl_with_options(
        self,
        *,
        download_documents: bool = False,
        max_documents: int | None = None,
        sample_per_source: int | None = None,
    ) -> dict[str, Any]:
        manifest = self.manifest_store.load()
        queue: list[str] = list(DEFAULT_INDEX_URLS)
        queued: set[str] = set(queue)
        visited: set[str] = set()

        while queue:
            batch = []
            while queue and len(batch) < self.max_concurrency:
                url = queue.pop(0)
                queued.discard(url)
                if url in visited:
                    continue
                visited.add(url)
                batch.append(url)

            results = await asyncio.gather(*(self._process_page(manifest, url) for url in batch))
            for discovered_urls in results:
                for discovered in discovered_urls:
                    if discovered in visited or discovered in queued:
                        continue
                    queue.append(discovered)
                    queued.add(discovered)

        if download_documents:
            await self._download_documents(
                manifest,
                max_documents=max_documents,
                sample_per_source=sample_per_source,
            )

        self.manifest_store.save(manifest)
        return {
            "output_dir": str(self.output_dir),
            "stats": {
                "pages_fetched": self.stats.pages_fetched,
                "pages_skipped": self.stats.pages_skipped,
                "pages_missing": self.stats.pages_missing,
                "documents_downloaded": self.stats.documents_downloaded,
                "documents_skipped": self.stats.documents_skipped,
                "documents_missing": self.stats.documents_missing,
                "documents_discovered": len(manifest["documents"]),
            },
            "manifest_path": str(self.manifest_store.path),
        }

    async def _process_page(self, manifest: dict[str, Any], url: str) -> list[str]:
        known_page = manifest["pages"].get(url, {})
        await self._emit_progress(
            event="page_started",
            current_url=url,
            current_step="Scanning PSD pages",
            manifest=manifest,
        )
        try:
            response = await self.client.request("GET", url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            self.stats.pages_missing += 1
            manifest["pages"][url] = {
                **known_page,
                "url": url,
                "source": detect_source(url),
                "status": "missing",
                "last_error": "404 Not Found",
                "last_seen_at": utc_now_iso(),
            }
            await self._emit_progress(
                event="page_missing",
                current_url=url,
                current_step="Skipped missing page",
                manifest=manifest,
            )
            return []
        html = response.text
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        if known_page.get("content_hash") == content_hash:
            self.stats.pages_skipped += 1
            known_page["last_seen_at"] = utc_now_iso()
            manifest["pages"][url] = known_page
            await self._emit_progress(
                event="page_skipped",
                current_url=url,
                current_step="Scanning PSD pages",
                manifest=manifest,
            )
            return known_page.get("links", [])

        parsed = parse_psd_page(url, html)
        preferred_document_url = self._select_preferred_document(parsed.document_links)
        page_record = {
            "url": url,
            "source": parsed.source,
            "content_hash": content_hash,
            "page_last_updated": parsed.page_last_updated,
            "links": parsed.links,
            "document_links": parsed.document_links,
            "preferred_document_url": preferred_document_url,
            "is_product_page": is_product_page(url),
            "last_seen_at": utc_now_iso(),
            "last_fetched_at": utc_now_iso(),
        }
        manifest["pages"][url] = page_record
        self.stats.pages_fetched += 1

        for document_url in parsed.document_links:
            document_record = manifest["documents"].get(document_url, {})
            source_pages = set(document_record.get("source_pages", []))
            source_pages.add(url)
            manifest["documents"][document_url] = {
                **document_record,
                "url": document_url,
                "source": document_record.get("source") or parsed.source or detect_source(document_url),
                "source_pages": sorted(source_pages),
                "discovered_at": document_record.get("discovered_at", utc_now_iso()),
                "last_seen_at": utc_now_iso(),
                "last_error": document_record.get("last_error"),
            }

        await self._emit_progress(
            event="page_processed",
            current_url=url,
            current_step="Scanning PSD pages",
            manifest=manifest,
        )

        return parsed.links

    async def _download_documents(
        self,
        manifest: dict[str, Any],
        max_documents: int | None = None,
        sample_per_source: int | None = None,
    ) -> None:
        preferred_document_urls = self._preferred_document_urls(
            manifest,
            sample_per_source=sample_per_source,
        )
        downloaded = 0
        for document_url in preferred_document_urls:
            if max_documents is not None and downloaded >= max_documents:
                break

            document_record = manifest["documents"].get(document_url, {})

            source_pages = document_record.get("source_pages", [])
            should_fetch = self._should_download_document(manifest, document_record, source_pages)
            if not should_fetch:
                self.stats.documents_skipped += 1
                await self._emit_progress(
                    event="document_skipped",
                    current_url=document_url,
                    current_step="Downloading changed documents",
                    manifest=manifest,
                )
                continue

            await self._emit_progress(
                event="document_started",
                current_url=document_url,
                current_step="Downloading preferred files",
                manifest=manifest,
            )
            try:
                response = await self.client.request("GET", document_url)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                self.stats.documents_missing += 1
                document_record.update(
                    {
                        "last_error": "404 Not Found",
                        "last_seen_at": utc_now_iso(),
                    }
                )
                manifest["documents"][document_url] = document_record
                await self._emit_progress(
                    event="document_missing",
                    current_url=document_url,
                    current_step="Skipped missing preferred file",
                    manifest=manifest,
                )
                continue
            content = response.content
            sha256 = hashlib.sha256(content).hexdigest()

            if document_record.get("sha256") == sha256 and document_record.get("local_path"):
                self.stats.documents_skipped += 1
                await self._emit_progress(
                    event="document_unchanged",
                    current_url=document_url,
                    current_step="Downloading preferred files",
                    manifest=manifest,
                )
                continue

            local_path = self._document_path(document_url)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(content)

            document_record.update(
                {
                    "content_type": response.headers.get("content-type"),
                    "etag": response.headers.get("etag"),
                    "last_modified": response.headers.get("last-modified"),
                    "sha256": sha256,
                    "size_bytes": len(content),
                    "downloaded_at": utc_now_iso(),
                    "local_path": str(local_path),
                    "last_error": None,
                }
            )
            manifest["documents"][document_url] = document_record
            self.stats.documents_downloaded += 1
            downloaded += 1
            await self._emit_progress(
                event="document_downloaded",
                current_url=document_url,
                current_step="Downloading preferred files",
                manifest=manifest,
            )

    def _should_download_document(
        self,
        manifest: dict[str, Any],
        document_record: dict[str, Any],
        source_pages: list[str],
    ) -> bool:
        if not document_record.get("local_path"):
            return True

        known_downloaded_at = document_record.get("downloaded_at", "")
        for page_url in source_pages:
            page_record = manifest["pages"].get(page_url, {})
            if page_record.get("last_fetched_at", "") > known_downloaded_at:
                return True
        return False

    def _document_path(self, url: str) -> Path:
        parsed = urlparse(url)
        relative_path = parsed.path.lstrip("/")
        return self.output_dir / "documents" / relative_path

    def _select_preferred_document(self, document_urls: list[str]) -> str | None:
        if not document_urls:
            return None
        docxs = [url for url in document_urls if urlparse(url).path.lower().endswith(".docx")]
        if docxs:
            return sorted(docxs)[0]
        docs = [url for url in document_urls if urlparse(url).path.lower().endswith(".doc")]
        if docs:
            return sorted(docs)[0]
        pdfs = [url for url in document_urls if urlparse(url).path.lower().endswith(".pdf")]
        if pdfs:
            return sorted(pdfs)[0]
        return sorted(document_urls)[0]

    def _preferred_document_urls(
        self,
        manifest: dict[str, Any],
        sample_per_source: int | None = None,
    ) -> list[str]:
        preferred_urls: list[str] = []
        seen: set[str] = set()
        per_source_counts: dict[str, int] = {}
        for page in manifest["pages"].values():
            if not page.get("is_product_page"):
                continue
            preferred_url = page.get("preferred_document_url") or self._select_preferred_document(
                page.get("document_links", [])
            )
            source = page.get("source") or "Unknown"
            if not preferred_url or preferred_url in seen:
                continue
            if sample_per_source is not None and per_source_counts.get(source, 0) >= sample_per_source:
                continue
            seen.add(preferred_url)
            preferred_urls.append(preferred_url)
            per_source_counts[source] = per_source_counts.get(source, 0) + 1
        return preferred_urls

    async def _emit_progress(
        self,
        *,
        event: str,
        current_url: str,
        current_step: str,
        manifest: dict[str, Any],
    ) -> None:
        if not self.progress_callback:
            return
        payload = {
            "event": event,
            "current_url": current_url,
            "current_step": current_step,
            "pages_fetched": self.stats.pages_fetched,
            "pages_skipped": self.stats.pages_skipped,
            "pages_missing": self.stats.pages_missing,
            "documents_downloaded": self.stats.documents_downloaded,
            "documents_skipped": self.stats.documents_skipped,
            "documents_missing": self.stats.documents_missing,
            "documents_discovered": len(manifest["documents"]),
            "preferred_documents": len(self._preferred_document_urls(manifest)),
            "manifest_path": str(self.manifest_store.path),
            "output_dir": str(self.output_dir),
        }
        result = self.progress_callback(payload)
        if asyncio.iscoroutine(result):
            await result
