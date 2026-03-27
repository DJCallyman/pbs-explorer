from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SEARCH_INDEX_PATH = Path("data/pbs_documents/search_index.json")
WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    parts = [node.text for node in root.findall(".//w:t", WORD_NAMESPACE) if node.text]
    return " ".join(parts)


def _extract_doc_text(path: Path) -> str:
    textutil = shutil.which("textutil")
    if not textutil:
        return ""
    try:
        result = subprocess.run(
            [textutil, "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return ""
    return result.stdout


def extract_text(path: str | Path) -> str:
    document_path = Path(path)
    suffix = document_path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx_text(document_path)
    if suffix == ".doc":
        return _extract_doc_text(document_path)
    return ""


def build_search_index(
    manifest_path: str | Path = "data/pbs_documents/manifest.json",
    output_path: str | Path = SEARCH_INDEX_PATH,
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    pages = manifest.get("pages", {})
    documents = manifest.get("documents", {})

    entries: list[dict[str, Any]] = []
    indexed = 0

    for page in pages.values():
        if not page.get("is_product_page"):
            continue
        preferred_url = page.get("preferred_document_url")
        if not preferred_url:
            continue
        document = documents.get(preferred_url)
        if not document or not document.get("local_path"):
            continue

        local_path = Path(document["local_path"])
        text = extract_text(local_path)
        normalized_text = re.sub(r"\s+", " ", text).strip()
        pdf_url = next(
            (url for url in page.get("document_links", []) if url.lower().endswith(".pdf")),
            None,
        )
        entry = {
            "source": page.get("source"),
            "entry_url": page.get("url"),
            "title": page.get("title") or page.get("url"),
            "preferred_url": preferred_url,
            "pdf_url": pdf_url,
            "local_path": str(local_path),
            "text": normalized_text,
        }
        entries.append(entry)
        if normalized_text:
            indexed += 1

    output = {
        "built_entries": len(entries),
        "searchable_entries": indexed,
        "entries": entries,
    }
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def search_index(
    query: str,
    output_path: str | Path = SEARCH_INDEX_PATH,
    limit: int = 20,
) -> dict[str, Any]:
    q = re.sub(r"\s+", " ", query).strip().lower()
    if not q:
        return {"query": query, "count": 0, "results": []}

    output = json.loads(Path(output_path).read_text(encoding="utf-8"))
    matches: list[dict[str, Any]] = []
    for entry in output.get("entries", []):
        haystack = f"{entry.get('title', '')} {entry.get('text', '')}".lower()
        if q not in haystack:
            continue
        text = entry.get("text", "")
        lower_text = text.lower()
        idx = lower_text.find(q)
        snippet = text[max(0, idx - 80): idx + len(q) + 160].strip() if idx >= 0 else ""
        matches.append(
            {
                "source": entry.get("source"),
                "title": entry.get("title"),
                "entry_url": entry.get("entry_url"),
                "preferred_url": entry.get("preferred_url"),
                "pdf_url": entry.get("pdf_url"),
                "local_path": entry.get("local_path"),
                "snippet": snippet,
            }
        )

    return {"query": query, "count": len(matches), "results": matches[:limit]}
