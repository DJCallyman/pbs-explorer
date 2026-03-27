from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _select_preferred_document(document_urls: list[str]) -> str | None:
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


@dataclass(slots=True)
class ManifestStore:
    path: Path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "pages": {},
                "documents": {},
            }

        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = utc_now_iso()
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def summarize_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {
            "exists": False,
            "path": str(manifest_path),
            "page_count": 0,
            "product_page_count": 0,
            "document_count": 0,
            "downloaded_document_count": 0,
            "entry_counts": {"PSD": 0, "DUSC": 0},
            "source_counts": {"PSD": 0, "DUSC": 0},
            "recent_documents": [],
            "updated_at": None,
        }

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = raw.get("pages", {})
    documents = raw.get("documents", {})
    psd_entry_count = sum(
        1 for page in pages.values() if page.get("source") == "PSD" and page.get("is_product_page")
    )
    dusc_entry_count = sum(
        1 for page in pages.values() if page.get("source") == "DUSC" and page.get("is_product_page")
    )
    preferred_document_urls = {
        page.get("preferred_document_url") or _select_preferred_document(page.get("document_links", []))
        for page in pages.values()
        if page.get("is_product_page")
    }
    preferred_document_urls.discard(None)
    downloaded_preferred_urls = {
        url for url in preferred_document_urls if documents.get(url, {}).get("local_path")
    }

    recent_documents = sorted(
        documents.values(),
        key=lambda doc: doc.get("last_seen_at", ""),
        reverse=True,
    )[:10]

    return {
        "exists": True,
        "path": str(manifest_path),
        "page_count": len(pages),
        "product_page_count": sum(1 for page in pages.values() if page.get("is_product_page")),
        "document_count": len(documents),
        "downloaded_document_count": sum(1 for doc in documents.values() if doc.get("local_path")),
        "preferred_document_count": len(preferred_document_urls),
        "downloaded_preferred_document_count": len(downloaded_preferred_urls),
        "entry_counts": {
            "PSD": psd_entry_count,
            "DUSC": dusc_entry_count,
        },
        "source_counts": {
            "PSD": sum(1 for doc in documents.values() if doc.get("source") == "PSD"),
            "DUSC": sum(1 for doc in documents.values() if doc.get("source") == "DUSC"),
        },
        "recent_documents": recent_documents,
        "updated_at": raw.get("updated_at"),
    }
