from __future__ import annotations

import csv
import io
import json
import asyncio
import re as _re
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from api.deps import get_db
from config import get_settings
from db.models import (
    ATCCode,
    Item,
    Indication,
    ItemRestrictionRelationship,
    Organisation,
    PrescribingText,
    Program,
    Restriction,
    Schedule,
    SummaryOfChange,
)
from db.models.app_setting import AppSetting
from db.session import get_session
from services.sync.incremental import IncrementalSync
from services.sync.status_store import status_store
from services.sync.orchestrator import SyncOrchestrator
from services.auth_store import list_users as list_auth_users
from services.psd.manifest import summarize_manifest
from services.saved_reports import (
    can_manage_report as can_manage_saved_report,
    can_view_report as can_view_saved_report,
    create_report as create_saved_report,
    delete_report as delete_saved_report,
    ensure_csv_access_token as ensure_saved_report_csv_access_token,
    ensure_unique_slug as ensure_saved_report_unique_slug,
    get_report as get_saved_report,
    list_reports as list_saved_reports,
    manifest_path as saved_reports_manifest_path,
    rotate_csv_access_token as rotate_saved_report_csv_access_token,
    slugify as saved_report_slugify,
    update_report as update_saved_report,
)
from services.reports import (
    items_by_program as _items_by_program,
    items_by_benefit_type as _items_by_benefit_type,
    items_by_atc_level as _items_by_atc_level,
    price_changes as _price_changes,
    restriction_changes as _restriction_changes,
    parse_pbs_codes,
    resolve_start_date,
    build_report_url,
    build_csv_download_url,
    VALID_VAR,
    VALID_RPT_FMT,
)
from utils import escape_like

logger = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_MEDICARE_FETCH_SEMAPHORE = asyncio.Semaphore(1)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


def _is_admin_request(request: Request) -> bool:
    return getattr(request.state, "web_auth_role", "") == "admin"


def _require_admin_request(request: Request) -> None:
    if not _is_admin_request(request):
        raise HTTPException(status_code=403, detail="Admin access required")


def _psd_enabled(request: Request) -> bool:
    return bool(getattr(request.state, "enable_psd", True))


def _request_username(request: Request) -> str:
    return str(getattr(request.state, "web_auth_user", "") or "").strip()


def _request_role(request: Request) -> str:
    return str(getattr(request.state, "web_auth_role", "") or "").strip()


def _available_saved_report_users(request: Request) -> list[str]:
    usernames = {user.get("username", "") for user in list_auth_users()}
    settings = get_settings()
    if settings.server.web_username:
        usernames.add(settings.server.web_username)
    current_user = _request_username(request)
    if current_user:
        usernames.add(current_user)
    return sorted({username.strip() for username in usernames if str(username).strip()}, key=str.lower)


def _format_admin_date(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M %Z",
        "%Y-%m-%d %H:%M UTC",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            if "H:%M" in fmt or "T%H:%M:%S" in fmt:
                return datetime.strptime(raw, fmt).strftime("%d-%b-%Y %I:%M %p")
            return datetime.strptime(raw, fmt).strftime("%d-%b-%Y")
        except ValueError:
            continue
    return raw


def _format_admin_effective_date(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "Unknown"
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
    except ValueError:
        return raw


def _get_setting_value(db: Session, key: str) -> str | None:
    return db.execute(select(AppSetting.value).where(AppSetting.key == key)).scalar()


def _set_setting_value(db: Session, key: str, value: str) -> None:
    existing = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        db.add(AppSetting(key=key, value=value, updated_at=now))


async def _pbs_schedule_status_payload(db: Session) -> dict:
    incremental = IncrementalSync(db)
    current_db_schedule = await incremental.get_current_db_schedule()
    latest_api_schedule = _get_setting_value(db, PBS_SCHEDULE_LATEST_API_KEY)
    latest_api_effective_date = _get_setting_value(db, PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY)
    last_checked_at = _get_setting_value(db, PBS_SCHEDULE_LAST_CHECKED_AT_KEY)
    last_check_status = _get_setting_value(db, PBS_SCHEDULE_LAST_CHECK_STATUS_KEY) or "Not checked yet"
    current_db_effective_date = db.execute(
        select(Schedule.effective_date).where(Schedule.schedule_code == current_db_schedule)
    ).scalar() if current_db_schedule else None

    if not latest_api_schedule and current_db_schedule:
        latest_api_schedule = current_db_schedule
    if not latest_api_effective_date and current_db_effective_date:
        latest_api_effective_date = current_db_effective_date.isoformat()

    return {
        "latest_api_schedule": latest_api_schedule or "Unknown",
        "latest_api_schedule_label": _format_admin_effective_date(latest_api_effective_date),
        "current_db_schedule": current_db_schedule or "Unknown",
        "current_db_schedule_label": _format_admin_effective_date(current_db_effective_date.isoformat() if current_db_effective_date else ""),
        "last_checked_at": _format_admin_date(last_checked_at),
        "last_check_status": last_check_status,
        "new_schedule_available": bool(latest_api_schedule and current_db_schedule and latest_api_schedule != current_db_schedule),
    }

PROGRAM_CODE_METADATA = {
    "EP": {"schedule": "General", "pbs_program": "Extemporaneous Preparations"},
    "GE": {"schedule": "General", "pbs_program": "Generally Available Pharmaceutical Benefits"},
    "PL": {"schedule": "General", "pbs_program": "Palliative Care"},
    "DB": {"schedule": "General", "pbs_program": "Prescriber Bag"},
    "R1": {"schedule": "RPBS", "pbs_program": "Repatriation Pharmaceutical Benefits Scheme only"},
    "MF": {"schedule": "Section 100", "pbs_program": "Botulinum Toxin Program"},
    "IN": {"schedule": "Section 100", "pbs_program": "Efficient Funding of Chemotherapy - Private Hospital - infusibles"},
    "IP": {"schedule": "Section 100", "pbs_program": "Efficient Funding of Chemotherapy - Public Hospital - infusibles"},
    "CT": {"schedule": "Section 100", "pbs_program": "Efficient Funding of Chemotherapy - Related Benefits"},
    "TY": {"schedule": "Section 100", "pbs_program": "Efficient Funding of Chemotherapy - Private Hospital - Trastuzumab"},
    "TZ": {"schedule": "Section 100", "pbs_program": "Efficient Funding of Chemotherapy - Public Hospital - Trastuzumab"},
    "GH": {"schedule": "Section 100", "pbs_program": "Growth Hormone Program"},
    "HS": {"schedule": "Section 100", "pbs_program": "Highly Specialised Drugs Program - Private Hospital"},
    "HB": {"schedule": "Section 100", "pbs_program": "Highly Specialised Drugs Program - Public Hospital"},
    "CA": {"schedule": "Section 100", "pbs_program": "Highly Specialised Drugs Program - Community Access"},
    "IF": {"schedule": "Section 100", "pbs_program": "IVF Program"},
    "MD": {"schedule": "Section 100", "pbs_program": "Opiate Dependence Treatment Program"},
    "PQ": {"schedule": "Section 100", "pbs_program": "Paraplegic and Quadriplegic Program"},
}

DISPENSING_RULE_LABELS = {
    "s90-cp": "Section 90 Community Pharmacy",
    "s94-private": "Section 94 Private Hospital",
    "s94-public": "Section 94 Public Hospital",
}

SPA_PRESCRIBING_TEXT_ID = 7608
SPA_PRESCRIBING_TEXT = "Special Pricing Arrangements apply."
STATE_HEADERS = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT", "TOTAL"}
MEDICARE_END_DATE_KEY = "medicare_stats_end_date"
MEDICARE_LAST_CHECKED_AT_KEY = "medicare_stats_last_checked_at"
MEDICARE_LAST_CHECK_STATUS_KEY = "medicare_stats_last_check_status"
MEDICARE_LAST_PROBE_REPORT_KEY = "medicare_stats_last_probe_report"
PBS_SCHEDULE_LAST_CHECKED_AT_KEY = "pbs_schedule_last_checked_at"
PBS_SCHEDULE_LAST_CHECK_STATUS_KEY = "pbs_schedule_last_check_status"
PBS_SCHEDULE_LATEST_API_KEY = "pbs_schedule_latest_api"
PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY = "pbs_schedule_latest_effective_date"
REPORT_FORMAT_LABELS = {
    "1": "Scheme by state",
    "2": "Scheme + month by state",
    "3": "Scheme + financial year by state",
    "4": "Scheme + calendar year by state",
    "5": "Patient category",
    "6": "Month by patient category",
    "7": "Financial year by patient category",
    "8": "Calendar year by patient category",
}

BENEFIT_TYPE_LABELS = {
    "U": "Unrestricted",
    "R": "Restricted",
    "A": "Authority Required",
    "S": "Authority Required: Streamlined",
}


def _medicare_upstream_error_detail(action: str, reason: str) -> str:
    return f"Could not {action} because the Services Australia Medicare source did not respond as expected. {reason}"


class _SimpleHTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._current_col = 0
        self._current_colspan = 1
        self._current_rowspan = 1
        self._rowspans: dict[int, int] = {}
        self._table_width = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = {name: value for name, value in attrs}
        if tag == "table":
            self._current_table = []
            self._rowspans = {}
            self._table_width = 0
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
            self._current_col = 0
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
            try:
                self._current_colspan = max(1, int(attrs_map.get("colspan", "1") or "1"))
            except ValueError:
                self._current_colspan = 1
            try:
                self._current_rowspan = max(1, int(attrs_map.get("rowspan", "1") or "1"))
            except ValueError:
                self._current_rowspan = 1
        elif tag == "br" and self._current_cell is not None:
            self._current_cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def _consume_rowspans(self) -> None:
        while self._current_row is not None and self._current_col in self._rowspans:
            self._current_row.append("")
            remaining = self._rowspans[self._current_col] - 1
            if remaining <= 0:
                del self._rowspans[self._current_col]
            else:
                self._rowspans[self._current_col] = remaining
            self._current_col += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._consume_rowspans()
            value = " ".join(part.strip() for part in self._current_cell if part.strip()).strip()
            self._current_row.append(value)
            if self._current_rowspan > 1:
                for offset in range(self._current_colspan):
                    self._rowspans[self._current_col + offset] = self._current_rowspan - 1
            for _ in range(self._current_colspan - 1):
                self._current_row.append("")
            self._current_col += self._current_colspan
            self._table_width = max(self._table_width, len(self._current_row))
            self._current_cell = None
            self._current_colspan = 1
            self._current_rowspan = 1
        elif tag == "tr" and self._current_table is not None and self._current_row is not None:
            self._consume_rowspans()
            while len(self._current_row) < self._table_width:
                self._current_row.append("")
            if any(cell.strip() for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._current_table is not None:
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = None


def _extract_main_report_table(html: str) -> list[list[str]]:
    parser = _SimpleHTMLTableParser()
    parser.feed(html)
    candidate_tables = [
        table
        for table in parser.tables
        if len(table) >= 2 and max((len(row) for row in table), default=0) >= 3
    ]
    if not candidate_tables:
        raise HTTPException(status_code=502, detail="Could not find a data table in the Medicare Statistics report")
    return max(candidate_tables, key=lambda table: len(table) * max((len(row) for row in table), default=0))


def _parse_numeric_value(value: str) -> str:
    cleaned = value.replace(",", "").replace("$", "").strip()
    return cleaned


def _canonical_month_value(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        if len(raw) == 6:
            return raw
        try:
            excel_base = datetime(1899, 12, 30)
            converted = excel_base + timedelta(days=int(raw))
            return converted.strftime("%Y%m")
        except ValueError:
            return raw

    upper = raw.upper()
    for fmt in ("%b%Y", "%B%Y", "%b-%Y", "%B-%Y", "%b %Y", "%B %Y", "%Y-%m", "%m/%Y"):
        try:
            return datetime.strptime(upper, fmt.upper()).strftime("%Y%m")
        except ValueError:
            pass
        try:
            return datetime.strptime(raw, fmt).strftime("%Y%m")
        except ValueError:
            pass
    return raw


def _is_scheme_label(value: str) -> bool:
    return str(value or "").strip().upper() in {"PBS", "RPBS", "TOTAL"}


def _is_period_header(value: str) -> bool:
    return str(value or "").strip().upper() in {"MONTH", "FINANCIAL YEAR", "CALENDAR YEAR"}


def _looks_like_period(value: str, rpt_fmt: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    upper = raw.upper()
    if upper == "TOTAL":
        return True
    if rpt_fmt in {"2", "6"}:
        if raw.isdigit():
            return len(raw) == 6 or 30000 <= int(raw) <= 70000
        month_formats = ("%b%Y", "%B%Y", "%b-%Y", "%B-%Y", "%b %Y", "%B %Y", "%Y-%m", "%m/%Y")
        for fmt in month_formats:
            try:
                datetime.strptime(raw, fmt)
                return True
            except ValueError:
                try:
                    datetime.strptime(upper, fmt.upper())
                    return True
                except ValueError:
                    continue
        return False
    if rpt_fmt in {"3", "7"}:
        return bool(_re.match(r"^\d{4}(?:-\d{2,4})?$", raw))
    if rpt_fmt in {"4", "8"}:
        return raw.isdigit() and len(raw) == 4
    return False


def _find_header_row(table: list[list[str]], rpt_fmt: str) -> int:
    best_index = 0
    best_score = -1
    for index, row in enumerate(table[:10]):
        cells = [cell.strip().upper() for cell in row if cell.strip()]
        if not cells:
            continue
        if rpt_fmt in {"1", "2", "3", "4"}:
            score = sum(1 for cell in cells if cell in STATE_HEADERS)
        else:
            score = sum(
                1
                for cell in cells
                if "GENERAL" in cell or "CONCESSIONAL" in cell or "RPBS" in cell or cell == "TOTAL"
            )
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def _row_dimension_labels(rpt_fmt: str) -> tuple[list[str], str]:
    if rpt_fmt == "1":
        return ["item", "scheme"], "state"
    if rpt_fmt == "2":
        return ["item", "scheme", "month"], "state"
    if rpt_fmt == "3":
        return ["item", "scheme", "financial_year"], "state"
    if rpt_fmt == "4":
        return ["item", "scheme", "calendar_year"], "state"
    if rpt_fmt == "5":
        return ["item"], "patient_category"
    if rpt_fmt == "6":
        return ["item", "month"], "patient_category"
    if rpt_fmt == "7":
        return ["item", "financial_year"], "patient_category"
    if rpt_fmt == "8":
        return ["item", "calendar_year"], "patient_category"
    return [], "column"


def _normalise_report_table(
    table: list[list[str]],
    selected_codes: list[str],
    start_date: str,
    end_date: str,
    var: str,
    rpt_fmt: str,
) -> list[dict[str, str]]:
    header_index = _find_header_row(table, rpt_fmt)
    row_labels, column_dimension_name = _row_dimension_labels(rpt_fmt)
    header_rows = table[max(0, header_index - 1): header_index + 1]
    max_header_len = max((len(row) for row in header_rows), default=0)
    combined_header: list[str] = []
    for column_index in range(max_header_len):
        label = ""
        for header_row in reversed(header_rows):
            if column_index < len(header_row) and str(header_row[column_index]).strip():
                label = str(header_row[column_index]).strip()
                break
        combined_header.append(label)

    if rpt_fmt in {"1", "2", "3", "4"}:
        header_cells_upper = {
            str(cell).strip().upper()
            for row in header_rows
            for cell in row
            if str(cell).strip()
        }
        metric_labels = [state for state in ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT", "TOTAL"] if state in header_cells_upper]
    else:
        metric_labels = [
            label
            for label in combined_header
            if label and ("GENERAL" in label.upper() or "CONCESSIONAL" in label.upper() or "RPBS" in label.upper() or label.upper() == "TOTAL")
        ]

    metric_count = len(metric_labels)
    if metric_count == 0:
        return []

    records: list[dict[str, str]] = []
    max_width = max((len(row) for row in table), default=0)
    context = {label: "" for label in row_labels}
    pending_metric_cells: list[str] | None = None

    def emit_values(item_value: str, scheme_value: str, period_value: str, metric_cells: list[str]) -> None:
        canonical_period = _canonical_month_value(period_value) if "month" in row_labels else str(period_value or "").strip()
        if not item_value or not canonical_period:
            return
        for column_label, value in zip(metric_labels, metric_cells):
            if not column_label:
                continue
            cleaned_value = _parse_numeric_value(value)
            if cleaned_value == "":
                continue
            record = {
                "requested_pbs_codes": ",".join(selected_codes),
                "requested_code_count": str(len(selected_codes)),
                "metric": var,
                "report_format": rpt_fmt,
                "report_start_date": start_date,
                "report_end_date": end_date,
                column_dimension_name: column_label,
                "value": cleaned_value,
                "item": item_value,
            }
            if "scheme" in row_labels:
                record["scheme"] = scheme_value or ""
            if "month" in row_labels:
                record["month"] = canonical_period
            if "financial_year" in row_labels:
                record["financial_year"] = canonical_period
            if "calendar_year" in row_labels:
                record["calendar_year"] = canonical_period
            records.append(record)

    for raw_row in table[header_index + 1:]:
        row = [str(cell).strip() for cell in raw_row] + [""] * max(0, max_width - len(raw_row))
        if not any(row):
            continue
        upper_cells = [cell.upper() for cell in row if cell]
        if upper_cells and all(cell in {"SERVICES", "BENEFIT", "STATE"} for cell in upper_cells):
            continue
        if len(row) <= metric_count:
            continue

        lead_cells = row[:-metric_count]
        metric_cells = row[-metric_count:]
        metrics_present = any(cell.strip() for cell in metric_cells)
        item_cell = lead_cells[0].strip() if lead_cells else ""
        scheme_cell = lead_cells[1].strip() if len(lead_cells) > 1 else ""
        period_cell = lead_cells[2].strip() if len(lead_cells) > 2 else ""

        if item_cell.upper() == "ITEM":
            pending_metric_cells = metric_cells if metrics_present else None
            continue

        if item_cell and item_cell.upper() != "TOTAL" and not _looks_like_period(item_cell, rpt_fmt):
            context["item"] = item_cell

        if _is_scheme_label(scheme_cell):
            context["scheme"] = scheme_cell

        if item_cell.upper() == "TOTAL" or period_cell.upper() == "TOTAL":
            pending_metric_cells = None
            continue

        if _is_period_header(period_cell):
            pending_metric_cells = metric_cells if metrics_present else None
            continue

        period_value = ""
        if len(lead_cells) > 2 and _looks_like_period(period_cell, rpt_fmt):
            period_value = period_cell
        elif context.get("item", "") == "All items" and _looks_like_period(item_cell, rpt_fmt):
            period_value = item_cell
        elif len(lead_cells) > 1 and _looks_like_period(scheme_cell, rpt_fmt):
            period_value = scheme_cell

        if not period_value:
            if metrics_present:
                pending_metric_cells = metric_cells
            continue

        metric_source = metric_cells if metrics_present else pending_metric_cells
        if metric_source:
            item_value = context.get("item", "").strip()
            scheme_value = context.get("scheme", "").strip()
            emit_values(item_value, scheme_value, period_value, metric_source)
            pending_metric_cells = None

    return records


def _month_display(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if raw.isdigit():
        if len(raw) == 6:
            try:
                return datetime.strptime(raw, "%Y%m").strftime("%b-%Y")
            except ValueError:
                pass
        try:
            excel_base = datetime(1899, 12, 30)
            return (excel_base + timedelta(days=int(raw))).strftime("%b-%Y")
        except ValueError:
            pass
    for fmt in ("%Y%m", "%Y-%m", "%b %Y", "%b-%Y", "%B %Y", "%B-%Y", "%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%b-%Y")
        except ValueError:
            continue
    return raw


def _field_for_report_format(rpt_fmt: str) -> tuple[str, str]:
    if rpt_fmt in {"2", "6"}:
        return "month", "Month"
    if rpt_fmt in {"3", "7"}:
        return "financial_year", "Financial Year"
    if rpt_fmt in {"4", "8"}:
        return "calendar_year", "Calendar Year"
    return "", "Group"


def _ordered_chart_columns(values: list[str], rpt_fmt: str) -> list[str]:
    cleaned = [value for value in values if value]
    if rpt_fmt in {"1", "2", "3", "4"}:
        preferred = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT", "TOTAL"]
        present = {value.upper() for value in cleaned}
        ordered = [name for name in preferred if name in present or name == "ACT"]
        if "TOTAL" not in ordered:
            ordered.append("TOTAL")
        return ordered
    return sorted(cleaned, key=lambda value: (value.upper() == "TOTAL", value))


def _month_sequence(start_date: str, end_date: str) -> list[str]:
    if not start_date or not end_date or len(start_date) != 6 or len(end_date) != 6:
        return []
    current = start_date
    months = []
    while current <= end_date:
        months.append(current)
        current = _subtract_months(current, -1)
    return months


def _period_sort_key(value: str, rpt_fmt: str) -> tuple[int, str]:
    raw = str(value or "").strip()
    if rpt_fmt in {"2", "6"} and len(raw) == 6 and raw.isdigit():
        return (0, raw)
    return (1, raw)


def _wide_chart_rows(
    records: list[dict[str, str]],
    rpt_fmt: str,
    start_date: str,
    end_date: str,
    program_labels: dict[str, str] | None = None,
    benefit_type_labels: dict[str, str] | None = None,
    treatment_phase_labels: dict[str, str] | None = None,
    drug_labels: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    period_key, period_label = _field_for_report_format(rpt_fmt)
    column_key = "state" if rpt_fmt in {"1", "2", "3", "4"} else "patient_category"
    program_labels = program_labels or {}
    benefit_type_labels = benefit_type_labels or {}
    treatment_phase_labels = treatment_phase_labels or {}
    drug_labels = drug_labels or {}

    filtered_records = [
        record
        for record in records
        if record.get("item", "").strip()
        and record.get("item", "").strip().upper() != "ALL ITEMS"
        and record.get("scheme", "").strip().upper() != "TOTAL"
    ]
    if period_key == "month":
        filtered_records = [
            record for record in filtered_records
            if (
                record.get(period_key, "").strip().isdigit()
                and len(record.get(period_key, "").strip()) == 6
                and start_date <= record.get(period_key, "").strip() <= end_date
            )
        ]

    column_values = _ordered_chart_columns(
        sorted({record.get(column_key, "").strip() for record in filtered_records if record.get(column_key, "").strip()}),
        rpt_fmt,
    )
    items = sorted({record.get("item", "").strip() for record in filtered_records if record.get("item", "").strip()})
    if period_key == "month":
        periods = _month_sequence(start_date, end_date)
    else:
        periods = sorted(
            {record.get(period_key, "").strip() for record in filtered_records if record.get(period_key, "").strip()},
            key=lambda value: _period_sort_key(value, rpt_fmt),
        )
    if not periods:
        periods = [""]

    def _label_value(item: str, mapping: dict[str, str], *, default_all: str = "All") -> str:
        if item.strip().upper() == "ALL ITEMS":
            return default_all
        return mapping.get(item, "")

    row_map: dict[tuple[str, str], dict[str, str]] = {}
    for item in items:
        for period_value in periods:
            display_value = _month_display(period_value) if period_key == "month" else (period_value or "")
            row_map[(item, period_value)] = {
                "Drug Name": _label_value(item, drug_labels),
                "Item code": item,
                "PBS Program": _label_value(item, program_labels),
                "Benefit Type": _label_value(item, benefit_type_labels),
                "Treatment Phase": _label_value(item, treatment_phase_labels),
                period_label: display_value,
                **{column_name: "0" for column_name in column_values},
            }

    for record in filtered_records:
        item = record.get("item", "").strip()
        period_value = record.get(period_key, "").strip() if period_key else ""
        key = (item, period_value or "")
        row = row_map.setdefault(
            key,
            {
                "Drug Name": _label_value(item, drug_labels),
                "Item code": item,
                "PBS Program": _label_value(item, program_labels),
                "Benefit Type": _label_value(item, benefit_type_labels),
                "Treatment Phase": _label_value(item, treatment_phase_labels),
                period_label: _month_display(period_value) if period_key == "month" else (period_value or ""),
                **{column_name: "0" for column_name in column_values},
            },
        )
        column_name = record.get(column_key, "").strip()
        if column_name:
            row[column_name] = _sum_chart_values(row.get(column_name, "0"), record.get("value", "0") or "0")

    rows = [
        row_map[key]
        for key in sorted(
            row_map.keys(),
            key=lambda pair: (pair[0], _period_sort_key(pair[1], rpt_fmt)),
        )
    ]
    fieldnames = ["Drug Name", "Item code", "PBS Program", "Benefit Type", "Treatment Phase", period_label] + column_values
    return fieldnames, rows


def _sum_chart_values(existing: str, incoming: str) -> str:
    existing_raw = str(existing or "0").strip() or "0"
    incoming_raw = str(incoming or "0").strip() or "0"
    try:
        total = Decimal(existing_raw) + Decimal(incoming_raw)
    except (InvalidOperation, ValueError):
        return incoming_raw or existing_raw
    if total == total.to_integral():
        return str(total.quantize(Decimal("1")))
    normalized = format(total.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _subtract_months(yyyymm: str, months: int) -> str:
    year = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    absolute = year * 12 + (month - 1) - months
    target_year = absolute // 12
    target_month = absolute % 12 + 1
    return f"{target_year:04d}{target_month:02d}"


def _resolve_saved_report_window(definition: dict, db: Session, codes: list[str]) -> tuple[str, str]:
    report = definition.get("report", {})
    window = report.get("window", {}) or {}
    mode = window.get("type", "rolling_months")
    end_date = _get_medicare_end_date(db)

    if mode == "explicit":
        start_date = window.get("start_date") or resolve_start_date(db, codes, None)
        end_date = window.get("end_date") or end_date
        return start_date, end_date

    if mode == "since_first_listing":
        return resolve_start_date(db, codes, None), end_date

    months = int(window.get("months", 12))
    return _subtract_months(end_date, max(months - 1, 0)), end_date


def _resolve_saved_report_start_date(definition: dict, db: Session, codes: list[str]) -> str:
    report = definition.get("report", {})
    window = report.get("window", {}) or {}
    mode = window.get("type", "rolling_months")
    if mode == "explicit":
        return window.get("start_date") or resolve_start_date(db, codes, None)
    if mode == "since_first_listing":
        return resolve_start_date(db, codes, None)
    return resolve_start_date(db, codes, None)


def _matching_indication_pbs_codes_subquery(
    *,
    indication: str | None = None,
    episodicity: str | None = None,
    latest_schedule_code: str | None = None,
    schedule_mode: str = "all",
):
    from db.models.relationships import (
        ItemRestrictionRelationship,
        RestrictionPrescribingTextRelationship,
    )

    query = (
        select(ItemRestrictionRelationship.pbs_code.label("pbs_code"))
        .select_from(ItemRestrictionRelationship)
        .join(
            RestrictionPrescribingTextRelationship,
            and_(
                ItemRestrictionRelationship.res_code == RestrictionPrescribingTextRelationship.res_code,
                ItemRestrictionRelationship.schedule_code == RestrictionPrescribingTextRelationship.schedule_code,
            ),
        )
        .join(
            Indication,
            and_(
                RestrictionPrescribingTextRelationship.prescribing_text_id == Indication.indication_prescribing_txt_id,
                RestrictionPrescribingTextRelationship.schedule_code == Indication.schedule_code,
            ),
        )
    )

    if latest_schedule_code and schedule_mode == "current":
        query = query.where(ItemRestrictionRelationship.schedule_code == latest_schedule_code)
    elif latest_schedule_code and schedule_mode == "historical":
        query = query.where(ItemRestrictionRelationship.schedule_code != latest_schedule_code)

    if indication:
        query = query.where(Indication.condition.ilike(f"%{escape_like(indication)}%"))
    if episodicity:
        query = query.where(Indication.episodicity == episodicity)

    return query.distinct().subquery()


def _search_matching_pbs_codes(
    db: Session,
    *,
    drug_name: str | None = None,
    brand_name: str | None = None,
    pbs_code: str | None = None,
    program_code: str | None = None,
    benefit_type_code: str | None = None,
    indication: str | None = None,
    episodicity: str | None = None,
    schedule_mode: str = "all",
    limit: int = 25,
) -> list[str]:
    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = select(Item.pbs_code).where(Item.pbs_code.isnot(None))

    if drug_name:
        query = query.where(Item.drug_name.ilike(f"%{escape_like(drug_name)}%"))
    if brand_name:
        query = query.where(Item.brand_name.ilike(f"%{escape_like(brand_name)}%"))
    if pbs_code:
        query = query.where(Item.pbs_code.ilike(f"%{escape_like(pbs_code)}%"))
    if program_code:
        query = query.where(Item.program_code == program_code)
    if benefit_type_code:
        query = query.where(Item.benefit_type_code == benefit_type_code)

    if latest_schedule_code and schedule_mode == "current":
        query = query.where(Item.schedule_code == latest_schedule_code)
    elif latest_schedule_code and schedule_mode == "historical":
        query = query.where(Item.schedule_code != latest_schedule_code)

    if indication or episodicity:
        matching_codes = _matching_indication_pbs_codes_subquery(
            indication=indication,
            episodicity=episodicity,
            latest_schedule_code=latest_schedule_code,
            schedule_mode=schedule_mode,
        )
        query = query.where(Item.pbs_code.in_(select(matching_codes.c.pbs_code)))

    rows = db.execute(
        query.distinct().order_by(Item.pbs_code).limit(limit)
    ).all()
    return [row[0] for row in rows if row[0]]


def _resolve_saved_report_codes(definition: dict, db: Session, limit: int = 25) -> list[str]:
    source_type = definition.get("source_type", "search_based")
    if source_type == "fixed_codes":
        codes = definition.get("codes", []) or []
        seen: set[str] = set()
        resolved: list[str] = []
        for code in codes:
            value = str(code).strip()
            if value and value not in seen:
                seen.add(value)
                resolved.append(value)
        return resolved[:limit]

    search = definition.get("search", {}) or {}
    return _search_matching_pbs_codes(
        db,
        drug_name=search.get("drug_name"),
        brand_name=search.get("brand_name"),
        pbs_code=search.get("pbs_code"),
        program_code=search.get("program_code"),
        benefit_type_code=search.get("benefit_type_code"),
        indication=search.get("indication"),
        episodicity=search.get("episodicity"),
        schedule_mode=search.get("schedule_mode", "all"),
        limit=limit,
    )


def _get_cached_saved_report_codes(definition: dict, limit: int = 25) -> list[str]:
    cached = definition.get("cached_validation", {}) or {}
    codes = cached.get("resolved_codes", []) or []
    seen: set[str] = set()
    resolved: list[str] = []
    for code in codes:
        value = str(code).strip()
        if value and value not in seen:
            seen.add(value)
            resolved.append(value)
    return resolved[:limit]


def _resolve_saved_report_codes_for_run(definition: dict, db: Session, limit: int = 25) -> list[str]:
    cached_codes = _get_cached_saved_report_codes(definition, limit=limit)
    if cached_codes:
        return cached_codes
    return _resolve_saved_report_codes(definition, db, limit=limit)


def _saved_report_needs_narrowing(definition: dict) -> bool:
    if definition.get("source_type", "search_based") != "search_based":
        return False
    search = definition.get("search", {}) or {}
    return not any(
        str(search.get(key) or "").strip()
        for key in ["drug_name", "brand_name", "pbs_code"]
    )


def _saved_report_code_summaries(db: Session, codes: list[str]) -> list[dict[str, str]]:
    if not codes:
        return []

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = (
        select(Item.pbs_code, Item.drug_name, Item.brand_name)
        .where(Item.pbs_code.in_(codes))
        .where(Item.pbs_code.isnot(None))
    )
    if latest_schedule_code:
        query = query.where(Item.schedule_code == latest_schedule_code)

    rows = db.execute(query.order_by(Item.pbs_code)).all()
    mapped = {
        str(row[0]): {
            "pbs_code": str(row[0] or ""),
            "drug_name": str(row[1] or ""),
            "brand_name": str(row[2] or ""),
        }
        for row in rows
        if row[0]
    }
    return [mapped.get(code, {"pbs_code": code, "drug_name": "", "brand_name": ""}) for code in codes]


def _chart_program_labels(db: Session, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = (
        select(Item.pbs_code, Program.program_title, Item.program_code)
        .select_from(Item)
        .join(
            Program,
            and_(Program.program_code == Item.program_code, Program.schedule_code == Item.schedule_code),
            isouter=True,
        )
        .where(Item.pbs_code.in_(codes))
    )
    if latest_schedule_code:
        query = query.where(Item.schedule_code == latest_schedule_code)

    rows = db.execute(query).all()
    labels: dict[str, str] = {}
    for row in rows:
        if not row.pbs_code:
            continue
        labels[str(row.pbs_code)] = str(row.program_title or row.program_code or "")
    return labels


def _chart_benefit_type_labels(db: Session, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = select(Item.pbs_code, Item.benefit_type_code).where(Item.pbs_code.in_(codes))
    if latest_schedule_code:
        query = query.where(Item.schedule_code == latest_schedule_code)

    rows = db.execute(query).all()
    labels_by_code: dict[str, set[str]] = {}
    for row in rows:
        if not row.pbs_code:
            continue
        label = BENEFIT_TYPE_LABELS.get(str(row.benefit_type_code or "").strip(), str(row.benefit_type_code or "").strip())
        if not label:
            continue
        labels_by_code.setdefault(str(row.pbs_code), set()).add(label)

    return {
        pbs_code: " | ".join(sorted(labels))
        for pbs_code, labels in labels_by_code.items()
    }


def _chart_treatment_phase_labels(db: Session, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = (
        select(Item.pbs_code, Restriction.treatment_phase)
        .select_from(Item)
        .join(
            ItemRestrictionRelationship,
            and_(
                ItemRestrictionRelationship.pbs_code == Item.pbs_code,
                ItemRestrictionRelationship.schedule_code == Item.schedule_code,
            ),
        )
        .join(
            Restriction,
            and_(
                Restriction.res_code == ItemRestrictionRelationship.res_code,
                Restriction.schedule_code == ItemRestrictionRelationship.schedule_code,
            ),
        )
        .where(Item.pbs_code.in_(codes))
    )
    if latest_schedule_code:
        query = query.where(Item.schedule_code == latest_schedule_code)

    rows = db.execute(query).all()
    labels_by_code: dict[str, set[str]] = {}
    for row in rows:
        if not row.pbs_code:
            continue
        label = str(row.treatment_phase or "").strip()
        if not label:
            continue
        labels_by_code.setdefault(str(row.pbs_code), set()).add(label)

    return {
        pbs_code: " | ".join(sorted(labels))
        for pbs_code, labels in labels_by_code.items()
    }


def _chart_drug_labels(db: Session, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = select(Item.pbs_code, Item.drug_name).where(Item.pbs_code.in_(codes))
    if latest_schedule_code:
        query = query.where(Item.schedule_code == latest_schedule_code)

    rows = db.execute(query).all()
    labels: dict[str, str] = {}
    for row in rows:
        if not row.pbs_code:
            continue
        labels[str(row.pbs_code)] = str(row.drug_name or "")
    return labels


def _window_fields_for_form(report: dict) -> dict[str, str]:
    window = (report.get("report", {}) or {}).get("window", {}) or {}
    window_type = str(window.get("type") or "since_first_listing")
    return {
        "window_type": window_type,
        "window_months": str(window.get("months", 12)) if window_type == "rolling_months" else "12",
        "window_start_date": _yyyymm_to_input_month(str(window.get("start_date") or "")),
        "window_end_date": _yyyymm_to_input_month(str(window.get("end_date") or "")),
    }


def _yyyymm_to_input_month(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) == 6 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:]}"
    return ""


def _saved_report_form_initial(report: dict | None = None) -> dict[str, str]:
    report = report or {}
    source_type = str(report.get("source_type") or "search_based")
    search = report.get("search", {}) or {}
    window_fields = _window_fields_for_form(report)
    return {
        "name": str(report.get("name") or ""),
        "description": str(report.get("description") or ""),
        "source_type": source_type,
        "var": str((report.get("report", {}) or {}).get("var") or "SERVICES"),
        "rpt_fmt": str((report.get("report", {}) or {}).get("rpt_fmt") or "2"),
        "window_type": window_fields["window_type"],
        "window_months": window_fields["window_months"],
        "window_start_date": window_fields["window_start_date"],
        "window_end_date": window_fields["window_end_date"],
        "drug_name": str(search.get("drug_name") or ""),
        "brand_name": str(search.get("brand_name") or ""),
        "pbs_code": str(search.get("pbs_code") or ""),
        "program_code": str(search.get("program_code") or ""),
        "benefit_type_code": str(search.get("benefit_type_code") or ""),
        "indication": str(search.get("indication") or ""),
        "episodicity": str(search.get("episodicity") or ""),
        "schedule_mode": str(search.get("schedule_mode") or "all"),
        "fixed_codes": ", ".join(str(code).strip() for code in (report.get("codes") or []) if str(code).strip()),
    }


def _build_saved_report_definition_from_form(
    parsed: dict[str, list[str]],
    *,
    owner: str,
    existing_slug: str | None = None,
    existing_token: str | None = None,
    existing_shared_with: list[str] | None = None,
) -> dict[str, object]:
    def form_value(name: str) -> str:
        values = parsed.get(name, [""])
        return values[0]

    name = str(form_value("name") or "").strip()
    if not name:
        raise ValueError("Name is required")

    slug = existing_slug or saved_report_slugify(name)
    if not slug:
        raise ValueError("Slug could not be derived")
    if not existing_slug:
        slug = ensure_saved_report_unique_slug(slug)

    source_type = str(form_value("source_type") or "search_based")
    if source_type not in {"search_based", "fixed_codes"}:
        raise ValueError("Invalid source type")

    var = str(form_value("var") or "SERVICES")
    rpt_fmt = str(form_value("rpt_fmt") or "2")
    if var not in VALID_VAR or rpt_fmt not in VALID_RPT_FMT:
        raise ValueError("Invalid report settings")

    window_type = str(form_value("window_type") or "since_first_listing")
    window: dict[str, str | int] = {"type": window_type}
    if window_type == "rolling_months":
        months_raw = str(form_value("window_months") or "12").strip()
        try:
            months = max(1, int(months_raw))
        except ValueError as exc:
            raise ValueError("Window months must be a number") from exc
        window["months"] = months
    elif window_type == "explicit":
        start_date = str(form_value("window_start_date") or "").replace("-", "")
        end_date = str(form_value("window_end_date") or "").replace("-", "")
        if not start_date or not end_date:
            raise ValueError("Explicit window dates are required")
        window["start_date"] = start_date
        window["end_date"] = end_date
    elif window_type != "since_first_listing":
        raise ValueError("Invalid window type")

    report_definition: dict[str, object] = {
        "slug": slug,
        "name": name,
        "owner": owner,
        "shared_with": sorted({str(username).strip() for username in (existing_shared_with or []) if str(username).strip() and str(username).strip() != owner}, key=str.lower),
        "description": str(form_value("description") or "").strip(),
        "source_type": source_type,
        "report": {
            "var": var,
            "rpt_fmt": rpt_fmt,
            "window": window,
        },
        "cached_validation": {},
    }
    if existing_token:
        report_definition["csv_access_token"] = existing_token

    if source_type == "search_based":
        drug_name = str(form_value("drug_name") or "").strip()
        brand_name = str(form_value("brand_name") or "").strip()
        if not drug_name and not brand_name:
            raise ValueError("Search-based reports must include at least one Drug or Brand value")

        report_definition["search"] = {
            "drug_name": drug_name,
            "brand_name": brand_name,
            "pbs_code": str(form_value("pbs_code") or "").strip(),
            "program_code": str(form_value("program_code") or "").strip(),
            "benefit_type_code": str(form_value("benefit_type_code") or "").strip(),
            "indication": str(form_value("indication") or "").strip(),
            "episodicity": str(form_value("episodicity") or "").strip(),
            "schedule_mode": str(form_value("schedule_mode") or "all"),
        }
    else:
        codes = [
            code.strip()
            for code in str(form_value("fixed_codes") or "").replace("\n", ",").split(",")
            if code.strip()
        ]
        if not codes:
            raise ValueError("At least one fixed code is required")
        report_definition["codes"] = codes

    return report_definition


async def _fetch_sas_report_html(codes: list[str], start_date: str, end_date: str, var: str, rpt_fmt: str) -> str:
    import time

    MAX_ATTEMPTS = 2
    last_error: Exception | None = None

    async with _MEDICARE_FETCH_SEMAPHORE:
        logger.info(
            "Acquired Medicare fetch slot for codes=%s rpt_fmt=%s start=%s end=%s",
            ",".join(codes),
            rpt_fmt,
            start_date,
            end_date,
        )
        for attempt in range(1, MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                logger.info(
                    "[chart attempt %d/%d] Fetching SAS HTML report for codes=%s rpt_fmt=%s start=%s end=%s",
                    attempt, MAX_ATTEMPTS, ",".join(codes), rpt_fmt, start_date, end_date,
                )
                html = await _fetch_sas_report_html_once(
                    codes,
                    start_date,
                    end_date,
                    var,
                    rpt_fmt,
                    connect_timeout=10.0,
                    read_timeout=20.0,
                )
                elapsed = time.monotonic() - t0
                logger.info(
                    "[chart attempt %d/%d] SAS HTML response: status=200 size=%d elapsed=%.1fs",
                    attempt, MAX_ATTEMPTS, len(html), elapsed,
                )
                return html
            except httpx.HTTPError as exc:
                elapsed = time.monotonic() - t0
                logger.warning(
                    "[chart attempt %d/%d] SAS HTML fetch failed after %.1fs: %s",
                    attempt, MAX_ATTEMPTS, elapsed, exc,
                )
                last_error = exc
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(1)
                    continue

    logger.error("All %d attempts to fetch SAS HTML report failed", MAX_ATTEMPTS)
    raise HTTPException(
        status_code=502,
        detail=_medicare_upstream_error_detail(
            "build the chart-ready CSV",
            f"Attempted {MAX_ATTEMPTS} time(s). Last upstream error: {last_error}",
        ),
    )


def _build_chart_csv_content(
    html: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    var: str,
    rpt_fmt: str,
    program_labels: dict[str, str] | None = None,
    benefit_type_labels: dict[str, str] | None = None,
    treatment_phase_labels: dict[str, str] | None = None,
    drug_labels: dict[str, str] | None = None,
) -> tuple[str, str]:
    logger.info(
        "Building chart CSV for %d code(s), rpt_fmt=%s, window=%s-%s",
        len(codes), rpt_fmt, start_date, end_date,
    )
    table = _extract_main_report_table(html)
    logger.info("Extracted main report table with %d rows", len(table))
    records = _normalise_report_table(table, codes, start_date, end_date, var, rpt_fmt)
    logger.info("Normalised %d report records", len(records))
    if not records:
        raise HTTPException(
            status_code=502,
            detail=_medicare_upstream_error_detail(
                "build the chart-ready CSV",
                "The upstream report did not contain the expected tabular rows.",
            ),
        )
    fieldnames, wide_rows = _wide_chart_rows(
        records,
        rpt_fmt,
        start_date,
        end_date,
        program_labels,
        benefit_type_labels,
        treatment_phase_labels,
        drug_labels,
    )
    logger.info("Chart CSV shape: %d columns x %d rows", len(fieldnames), len(wide_rows))
    if not wide_rows:
        raise HTTPException(
            status_code=502,
            detail=_medicare_upstream_error_detail(
                "build the chart-ready CSV",
                "The upstream report format could not be reshaped into chart rows.",
            ),
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(fieldnames)
    for row in wide_rows:
        writer.writerow([row.get(fieldname, "") for fieldname in fieldnames])
    generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pbs_report_chart_{var.lower()}_{rpt_fmt}_{start_date}_{end_date}_{generated_at}.csv"
    return output.getvalue(), filename


def _format_month_year(value) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%b-%Y")
    return str(value)


def _format_currency(value) -> str:
    if value in (None, "", "None"):
        return ""
    if value == "Multiple":
        return "Multiple"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"${numeric:,.2f}"


def _build_filter_options(items: list[dict]) -> dict[str, list[str]]:
    filter_keys = [
        "drug_name",
        "brand_name",
        "pbs_code",
        "indications",
        "form_summary",
        "status",
        "first_listed_date_display",
        "item_code_status",
        "aemp_filter_values",
        "dispensed_price_display",
        "spa_flag",
        "schedule_label",
        "pbs_program_label",
        "pbac_meeting_date_display",
        "pbac_outcome_published",
        "max_qty_packs",
        "max_qty_units",
        "formulary",
        "episodicity",
    ]
    options: dict[str, list[str]] = {}
    for key in filter_keys:
        values_set: set[str] = set()
        for item in items:
            value = item.get(key)
            if isinstance(value, list):
                values_set.update(
                    str(entry).strip()
                    for entry in value
                    if entry not in (None, "", "None")
                )
            elif value not in (None, "", "None"):
                values_set.add(str(value).strip())
        values = sorted(values_set)
        options[key] = values
    return options


def _format_dispensing_rule(value: str | None) -> str:
    if not value:
        return ""
    return DISPENSING_RULE_LABELS.get(value, value.replace("-", " ").upper())


def _load_psd_manifest() -> dict:
    return summarize_manifest("data/pbs_documents/manifest.json")


def _get_medicare_end_date(db: Session) -> str:
    """Read the medicare_stats_end_date setting from the DB, with dynamic fallback."""
    row = db.execute(
        select(AppSetting.value).where(AppSetting.key == MEDICARE_END_DATE_KEY)
    ).scalar()
    if row:
        return row
    # Dynamic fallback: current month in YYYYMM format
    return datetime.now().strftime("%Y%m")


def _get_app_setting(db: Session, key: str) -> str:
    return db.execute(select(AppSetting.value).where(AppSetting.key == key)).scalar() or ""


def _set_medicare_end_date(db: Session, value: str) -> None:
    existing = db.execute(
        select(AppSetting).where(AppSetting.key == MEDICARE_END_DATE_KEY)
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        db.add(AppSetting(key=MEDICARE_END_DATE_KEY, value=value, updated_at=now))
    db.commit()


def _set_app_setting(db: Session, key: str, value: str) -> None:
    existing = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        db.add(AppSetting(key=key, value=value, updated_at=now))


def _commit_app_settings(db: Session) -> None:
    db.commit()


def _format_medicare_status_month(value: str) -> str:
    if value and value.isdigit() and len(value) == 6:
        try:
            return datetime.strptime(value, "%Y%m").strftime("%b %Y")
        except ValueError:
            return value
    return value or "Unknown"


def _format_display_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) >= 16 and raw[4] == "-" and raw[7] == "-" and raw[10] == " " and raw[13] == ":":
        try:
            date_part = datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
            time_part = datetime.strptime(raw[11:16], "%H:%M").strftime("%I:%M %p")
            suffix = raw[16:].strip()
            return f"{date_part} {time_part}{(' ' + suffix) if suffix else ''}"
        except ValueError:
            pass
    for fmt in (
        "%Y-%m-%d %H:%M %Z",
        "%Y-%m-%d %H:%M UTC",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            if "H:%M" in fmt or "T%H:%M:%S" in fmt:
                return datetime.strptime(raw, fmt).strftime("%d-%b-%Y %I:%M %p")
            return datetime.strptime(raw, fmt).strftime("%d-%b-%Y")
        except ValueError:
            continue
    return raw


def _medicare_status_payload(db: Session) -> dict[str, str]:
    return {
        "end_date": _get_medicare_end_date(db),
        "end_date_label": _format_medicare_status_month(_get_medicare_end_date(db)),
        "last_checked_at": _format_display_date(_get_app_setting(db, MEDICARE_LAST_CHECKED_AT_KEY)),
        "last_check_status": _get_app_setting(db, MEDICARE_LAST_CHECK_STATUS_KEY) or "Not checked yet",
        "last_probe_report": _get_app_setting(db, MEDICARE_LAST_PROBE_REPORT_KEY),
    }


def _select_medicare_probe_report() -> tuple[str, list[str]] | None:
    for report in list_saved_reports():
        slug = str(report.get("slug") or "").strip()
        if not slug:
            continue
        cached_validation = report.get("cached_validation", {}) or {}
        codes = [str(code).strip() for code in cached_validation.get("resolved_codes", []) if str(code).strip()]
        if codes:
            return slug, codes[:20]

    for report in list_saved_reports():
        slug = str(report.get("slug") or "").strip()
        if not slug:
            continue
        fixed_codes = [str(code).strip() for code in report.get("codes", []) if str(code).strip()]
        if fixed_codes:
            return slug, fixed_codes[:20]
    return None


async def _strip_referer(request: httpx.Request) -> None:
    if "referer" in request.headers:
        del request.headers["referer"]


async def _fetch_sas_report_html_once(
    codes: list[str],
    start_date: str,
    end_date: str,
    var: str,
    rpt_fmt: str,
    *,
    connect_timeout: float = 15.0,
    read_timeout: float = 40.0,
) -> str:
    report_url = build_report_url(codes, start_date, end_date, var, rpt_fmt)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(connect=connect_timeout, read=read_timeout, write=15.0, pool=15.0),
        event_hooks={"request": [_strip_referer]},
    ) as client:
        response = await client.get(report_url)
        response.raise_for_status()
        return response.text


def _probe_rpt_fmt(rpt_fmt: str) -> str:
    return "2" if rpt_fmt in {"1", "2", "3", "4"} else "6"


def _latest_available_month_from_html(
    html: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    var: str,
    rpt_fmt: str,
) -> str | None:
    table = _extract_main_report_table(html)
    probe_records = _normalise_report_table(table, codes, start_date, end_date, var, rpt_fmt)
    months = sorted(
        {
            record.get("month", "").strip()
            for record in probe_records
            if record.get("month", "").strip().isdigit() and len(record.get("month", "").strip()) == 6
        }
    )
    return months[-1] if months else None


async def _resolve_medicare_end_date_for_run(
    db: Session,
    codes: list[str],
    start_date: str,
    var: str,
    rpt_fmt: str,
    explicit_end_date: str | None = None,
    probe_latest: bool = False,
) -> tuple[str, str | None]:
    if explicit_end_date:
        return explicit_end_date, None

    if not probe_latest:
        return _get_medicare_end_date(db), None

    current_month = datetime.now().strftime("%Y%m")
    cached_month = _get_medicare_end_date(db)
    probe_format = _probe_rpt_fmt(rpt_fmt)

    candidate_months: list[str] = []
    for offset in range(0, 7):
        candidate_months.append(_subtract_months(current_month, offset))
    if cached_month not in candidate_months:
        candidate_months.append(cached_month)

    last_error: Exception | None = None
    for candidate in candidate_months:
        logger.info(
            "Probing Medicare end month candidate=%s for codes=%s probe_rpt_fmt=%s",
            candidate, ",".join(codes), probe_format,
        )
        try:
            html = await _fetch_sas_report_html_once(
                codes,
                start_date,
                candidate,
                var,
                probe_format,
                connect_timeout=12.0,
                read_timeout=25.0,
            )
            latest_month = _latest_available_month_from_html(
                html,
                codes,
                start_date,
                candidate,
                var,
                probe_format,
            )
            resolved_month = latest_month or candidate
            logger.info(
                "Resolved Medicare end month candidate=%s to actual=%s",
                candidate,
                resolved_month,
            )
            if resolved_month != cached_month:
                _set_medicare_end_date(db, resolved_month)
            if probe_format == rpt_fmt and resolved_month == candidate:
                return resolved_month, html
            return resolved_month, None
        except Exception as exc:
            last_error = exc
            logger.warning("Medicare end month probe failed for candidate=%s: %s", candidate, exc)
            continue

    fallback = cached_month or _subtract_months(current_month, 1)
    logger.warning(
        "Falling back to cached Medicare end month %s after probe failures; last_error=%s",
        fallback,
        last_error,
    )
    return fallback, None


async def refresh_latest_medicare_data() -> dict[str, str]:
    with get_session() as db:
        probe = _select_medicare_probe_report()
        checked_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

        if not probe:
            _set_app_setting(db, MEDICARE_LAST_CHECKED_AT_KEY, checked_at)
            _set_app_setting(db, MEDICARE_LAST_CHECK_STATUS_KEY, "No saved report with validated codes is available yet.")
            _set_app_setting(db, MEDICARE_LAST_PROBE_REPORT_KEY, "")
            _commit_app_settings(db)
            return _medicare_status_payload(db)

        probe_slug, codes = probe
        try:
            current_month = datetime.now().strftime("%Y%m")
            probe_start = _subtract_months(current_month, 11)
            end_date, _ = await _resolve_medicare_end_date_for_run(
                db,
                codes,
                probe_start,
                "SERVICES",
                "2",
                explicit_end_date=None,
                probe_latest=True,
            )
            _set_app_setting(db, MEDICARE_LAST_CHECKED_AT_KEY, checked_at)
            _set_app_setting(
                db,
                MEDICARE_LAST_CHECK_STATUS_KEY,
                f"Latest Medicare month confirmed as {_format_medicare_status_month(end_date)}.",
            )
            _set_app_setting(db, MEDICARE_LAST_PROBE_REPORT_KEY, probe_slug)
            _commit_app_settings(db)
        except Exception as exc:
            logger.warning("Automatic Medicare latest-month refresh failed: %s", exc)
            _set_app_setting(db, MEDICARE_LAST_CHECKED_AT_KEY, checked_at)
            _set_app_setting(
                db,
                MEDICARE_LAST_CHECK_STATUS_KEY,
                f"Last refresh failed. Keeping cached month {_format_medicare_status_month(_get_medicare_end_date(db))}.",
            )
            _set_app_setting(db, MEDICARE_LAST_PROBE_REPORT_KEY, probe_slug)
            _commit_app_settings(db)

        return _medicare_status_payload(db)
