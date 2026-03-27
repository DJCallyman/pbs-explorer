from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin


MEDICINE_STATUS_BASE_URL = "https://www.pbs.gov.au"
SEARCH_RESULT_RE = re.compile(r"<search-result\b[^>]*:result=\"([^\"]+)\"", re.IGNORECASE | re.DOTALL)
DT_DD_RE = re.compile(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", re.IGNORECASE | re.DOTALL)
LINK_RE = re.compile(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class MedicineStatusSearchEntry:
    medicine_status_id: str
    document_url: str
    drug_name: str
    brand_names: str
    sponsor: str
    purpose: str
    meeting_date: date | None
    meeting_date_label: str
    listing_outcome_status: str


@dataclass(slots=True)
class MedicineStatusSearchPage:
    page: int
    total_pages: int
    total_results: int
    entries: list[MedicineStatusSearchEntry]


@dataclass(slots=True)
class MedicineStatusDetail:
    drug_name: str
    brand_names: str
    sponsor: str
    purpose: str
    submission_received_for: str
    pbac_meeting_date: date | None
    pbac_outcome_published_text: str
    pbac_outcome_published_url: str
    public_summary_title: str
    public_summary_url: str
    status: str
    page_last_updated: date | None


def normalize_medicine_name(value: str | None) -> str:
    cleaned = SPACE_RE.sub(" ", re.sub(r"[^A-Za-z0-9]+", " ", (value or "").upper())).strip()
    return cleaned


def _strip_html(value: str) -> str:
    text = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", unescape(text)).strip()


def _extract_first_link(html: str) -> tuple[str, str]:
    match = LINK_RE.search(html)
    if not match:
        return "", ""
    return urljoin(MEDICINE_STATUS_BASE_URL, unescape(match.group(1)).strip()), _strip_html(match.group(2))


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _extract_result_payload(html: str) -> dict[str, Any]:
    match = SEARCH_RESULT_RE.search(html)
    if not match:
        raise ValueError("Could not find embedded Medicine Status search results")
    return json.loads(unescape(match.group(1)))


def _normalize_purpose(value: Any) -> str:
    if isinstance(value, list):
        parts = [str(part).strip(" ;") for part in value if str(part).strip(" ;")]
        return "; ".join(parts)
    return str(value or "").strip()


def parse_search_page(html: str) -> MedicineStatusSearchPage:
    payload = _extract_result_payload(html)
    entries: list[MedicineStatusSearchEntry] = []
    for row in payload.get("results", []):
        psid = str(row.get("psid") or "").strip()
        if not psid:
            continue
        entries.append(
            MedicineStatusSearchEntry(
                medicine_status_id=psid,
                document_url=f"{MEDICINE_STATUS_BASE_URL}/medicinestatus/document/{psid}.html",
                drug_name=str(row.get("pspropertyDrugName") or "").strip(),
                brand_names=str(row.get("pspropertyBrandNames") or "").strip(),
                sponsor=str(row.get("pspropertySponsors") or "").strip(),
                purpose=_normalize_purpose(row.get("pspropertyPurpose")),
                meeting_date=_parse_date(row.get("pspropertyMeetingDate")),
                meeting_date_label=str(row.get("pspropertyMeetingDatepspropertyFormattedMeetingDate") or "").strip(),
                listing_outcome_status=str(row.get("pspropertyPbacOutcomeStatus") or "").strip(),
            )
        )
    return MedicineStatusSearchPage(
        page=int(payload.get("page") or 1),
        total_pages=int(payload.get("totalPages") or 1),
        total_results=int(payload.get("totalResults") or len(entries)),
        entries=entries,
    )


def parse_detail_page(html: str) -> MedicineStatusDetail:
    pairs: dict[str, tuple[str, str]] = {}
    for dt_html, dd_html in DT_DD_RE.findall(html):
        label = _strip_html(dt_html).rstrip(":").strip().lower()
        if not label:
            continue
        pairs[label] = (_strip_html(dd_html), dd_html)

    heading_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    drug_name = _strip_html(heading_match.group(1)) if heading_match else ""
    pbac_meeting_text = pairs.get("pbac meeting", ("", ""))[0]
    pbac_outcome_text, pbac_outcome_html = pairs.get("pbac outcome published", ("", ""))
    public_summary_text, public_summary_html = pairs.get("public summary document", ("", ""))
    page_last_updated_text = pairs.get("page last updated", ("", ""))[0]
    pbac_outcome_url, _ = _extract_first_link(pbac_outcome_html)
    public_summary_url, public_summary_title = _extract_first_link(public_summary_html)
    held_match = re.search(r"(\d{2}/\d{2}/\d{4})", pbac_meeting_text)

    page_last_updated = None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        if not page_last_updated_text:
            break
        try:
            page_last_updated = datetime.strptime(page_last_updated_text, fmt).date()
            break
        except ValueError:
            continue

    return MedicineStatusDetail(
        drug_name=drug_name,
        brand_names=pairs.get("brand name", ("", ""))[0],
        sponsor=pairs.get("submission sponsor", ("", ""))[0],
        purpose=pairs.get("condition/indication: (therapeutic use)", ("", ""))[0],
        submission_received_for=pairs.get("submission received for", ("", ""))[0],
        pbac_meeting_date=_parse_date(held_match.group(1) if held_match else ""),
        pbac_outcome_published_text=pbac_outcome_text,
        pbac_outcome_published_url=pbac_outcome_url,
        public_summary_title=public_summary_title or public_summary_text,
        public_summary_url=public_summary_url,
        status=pairs.get("status", ("", ""))[0],
        page_last_updated=page_last_updated,
    )
