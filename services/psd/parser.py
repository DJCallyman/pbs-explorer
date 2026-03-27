from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse


PAGE_LAST_UPDATED_RE = re.compile(r"Page last updated:\s*(.+)", re.IGNORECASE)
PSD_PREFIX = "/info/industry/listing/elements/pbac-meetings/psd"
DUSC_PREFIX = "/info/industry/listing/participants/public-release-docs"
PSD_PRIMARY_INDEX_SUFFIX = "public-summary-documents-by-product"
DUSC_PRIMARY_INDEX_SUFFIX = "dusc-public-release-documents-by-medicine"
DUSC_INDEX_SUFFIXES = {
    "dusc-public-release-documents-by-medicine",
    "dusc-public-release-documents-by-condition",
    "dusc-public-release-documents-by-meeting",
}


@dataclass(slots=True)
class ParsedPage:
    url: str
    source: str | None = None
    page_last_updated: str | None = None
    links: list[str] = field(default_factory=list)
    document_links: list[str] = field(default_factory=list)


class _AnchorCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attr_map = dict(attrs)
        href = attr_map.get("href")
        if not href:
            return

        absolute = urljoin(self.base_url, href.strip())
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            return

        normalized = parsed._replace(fragment="").geturl()
        self.links.append(normalized)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def extract_page_last_updated(html: str) -> str | None:
    match = PAGE_LAST_UPDATED_RE.search(html)
    if not match:
        return None
    return " ".join(match.group(1).split())


def collect_links(base_url: str, html: str) -> list[str]:
    parser = _AnchorCollector(base_url)
    parser.feed(html)
    return _dedupe(parser.links)


def detect_source(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path.startswith(PSD_PREFIX):
        return "PSD"
    if path.startswith(DUSC_PREFIX):
        return "DUSC"
    return None


def is_psd_listing_page(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.startswith(PSD_PREFIX)


def is_dusc_listing_page(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.startswith(DUSC_PREFIX)


def is_supported_listing_page(url: str) -> bool:
    return is_psd_listing_page(url) or is_dusc_listing_page(url)


def is_psd_primary_index(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.rstrip("/").endswith(PSD_PRIMARY_INDEX_SUFFIX)


def is_dusc_primary_index(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.rstrip("/").endswith(DUSC_PRIMARY_INDEX_SUFFIX)


def is_product_page(url: str) -> bool:
    source = detect_source(url)
    if source == "PSD":
        return is_psd_product_page(url)
    if source == "DUSC":
        return is_dusc_item_page(url)
    return False


def is_psd_product_page(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not is_psd_listing_page(url):
        return False

    last_segment = path.rsplit("/", 1)[-1]
    if "public-summary-documents" in last_segment:
        return False
    if last_segment == "psd":
        return False
    return "-PSD-" in last_segment or "-psd-" in last_segment


def is_dusc_item_page(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not is_dusc_listing_page(url):
        return False

    last_segment = path.rsplit("/", 1)[-1]
    if last_segment in DUSC_INDEX_SUFFIXES:
        return False
    if last_segment == "public-release-docs":
        return False
    return True


def is_downloadable_document(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith(".pdf") or path.endswith(".doc") or path.endswith(".docx")


def is_crawlable_page(url: str) -> bool:
    source = detect_source(url)
    if source == "PSD":
        return is_psd_primary_index(url) or is_psd_product_page(url)
    if source == "DUSC":
        return is_dusc_primary_index(url) or is_dusc_item_page(url)
    return False


def parse_psd_page(url: str, html: str) -> ParsedPage:
    all_links = collect_links(url, html)
    page_links = [link for link in all_links if is_crawlable_page(link)]
    document_links = [link for link in all_links if is_downloadable_document(link)]
    return ParsedPage(
        url=url,
        source=detect_source(url),
        page_last_updated=extract_page_last_updated(html),
        links=_dedupe(page_links),
        document_links=_dedupe(document_links),
    )
