"""Shared report query helpers used by both the API and web layers.

Centralises the database queries for PBS reports so that
``api.routers.reports`` and ``web.routes`` do not duplicate logic.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import ATCCode, Item, SummaryOfChange


# ---------------------------------------------------------------------------
# Report queries
# ---------------------------------------------------------------------------

def items_by_program(db: Session) -> List[Dict[str, Any]]:
    """Return item counts grouped by program code."""
    rows = db.execute(
        select(Item.program_code, func.count(Item.li_item_id).label("count"))
        .group_by(Item.program_code)
        .order_by(func.count(Item.li_item_id).desc())
    ).all()
    return [
        {"program_code": r.program_code if r.program_code is not None else "(none)", "count": r.count}
        for r in rows
    ]


def items_by_benefit_type(db: Session) -> List[Dict[str, Any]]:
    """Return item counts grouped by benefit type code."""
    rows = db.execute(
        select(Item.benefit_type_code, func.count(Item.li_item_id).label("count"))
        .where(Item.benefit_type_code.isnot(None))
        .group_by(Item.benefit_type_code)
        .order_by(func.count(Item.li_item_id).desc())
    ).all()
    return [{"benefit_type_code": r.benefit_type_code, "count": r.count} for r in rows]


def items_by_atc_level(db: Session) -> List[Dict[str, Any]]:
    """Return ATC code counts grouped by level."""
    rows = db.execute(
        select(ATCCode.atc_level, func.count(ATCCode.atc_code).label("count"))
        .where(ATCCode.atc_level.isnot(None))
        .group_by(ATCCode.atc_level)
        .order_by(ATCCode.atc_level)
    ).all()
    return [{"atc_level": r.atc_level, "count": r.count} for r in rows]


def price_changes(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """Return items with recent price updates."""
    rows = db.execute(
        select(
            Item.li_item_id,
            Item.pbs_code,
            Item.drug_name,
            Item.brand_name,
            Item.determined_price,
            Item.updated_at,
        )
        .where(Item.updated_at.isnot(None))
        .order_by(Item.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "li_item_id": r.li_item_id,
            "pbs_code": r.pbs_code,
            "drug_name": r.drug_name,
            "brand_name": r.brand_name,
            "current_price": float(r.determined_price) if r.determined_price else None,
            "price": str(r.determined_price) if r.determined_price else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "updated": r.updated_at.strftime("%Y-%m-%d %H:%M") if r.updated_at else "",
        }
        for r in rows
    ]


def restriction_changes(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent restriction-related changes from summary-of-changes."""
    rows = db.execute(
        select(
            SummaryOfChange.changed_table,
            SummaryOfChange.table_keys,
            SummaryOfChange.change_type,
            SummaryOfChange.changed_endpoint,
            SummaryOfChange.source_schedule_code,
            SummaryOfChange.schedule_code,
        )
        .where(SummaryOfChange.changed_endpoint.like("%restriction%"))
        .order_by(SummaryOfChange.schedule_code.desc())
        .limit(limit)
    ).all()
    return [
        {
            "changed_table": r.changed_table,
            "table": r.changed_table,
            "table_keys": r.table_keys,
            "change_type": r.change_type,
            "changed_endpoint": r.changed_endpoint,
            "endpoint": r.changed_endpoint,
            "from_schedule": r.source_schedule_code,
            "to_schedule": r.schedule_code,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Medicare Statistics URL builder
# ---------------------------------------------------------------------------

VALID_VAR = {"SERVICES", "BENEFIT"}
VALID_RPT_FMT = {"1", "2", "3", "4", "5", "6", "7", "8"}

_SAS_BASE_URL = "https://medicarestatistics.humanservices.gov.au/SASStoredProcess/guest"
_SAS_REPORT_PROGRAM = "SBIP://METASERVER/Shared Data/sasdata/prod/VEA0032/SAS.StoredProcess/statistics/pbs_item_standard_report"
_SAS_CSV_PROGRAM = "SBIP://METASERVER/Shared Data/sasdata/prod/VEA0032/SAS.StoredProcess/statistics/mbs_csv"


def parse_pbs_codes(raw: str) -> List[str]:
    """Parse a comma-separated string of PBS codes (optionally single-quoted)."""
    codes = re.findall(r"'([^',]+)'", raw)
    if not codes:
        codes = raw.split(",")
    return [c.strip() for c in codes if c.strip()]


def resolve_start_date(db: Session, codes: Sequence[str], start_date: Optional[str]) -> str:
    """Return *start_date* or derive it from the earliest ``first_listed_date``."""
    if start_date:
        return start_date
    earliest = db.execute(
        select(func.min(Item.first_listed_date)).where(Item.pbs_code.in_(codes))
    ).scalar_one_or_none()
    return earliest.strftime("%Y%m") if earliest else "202501"


def build_report_url(
    codes: Sequence[str],
    start_date: str,
    end_date: str,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
) -> str:
    """Construct the full Medicare Statistics SAS report URL."""
    itemlst = ",".join(f"'{c.zfill(6)}'" for c in codes)
    list_param = ",".join(codes)
    return (
        _SAS_BASE_URL
        + "?_PROGRAM=" + quote(_SAS_REPORT_PROGRAM, safe="")
        + "&itemlst=" + itemlst
        + "&ITEMCNT=" + str(len(codes))
        + "&LIST=" + quote(list_param, safe="")
        + "&VAR=" + var
        + "&RPT_FMT=" + rpt_fmt
        + "&start_dt=" + start_date
        + "&end_dt=" + end_date
    )


def build_csv_download_url(report_name: str, title1: str) -> str:
    """Construct the SAS CSV/Excel download URL for a rendered report."""
    return (
        _SAS_BASE_URL
        + "?_PROGRAM=" + quote(_SAS_CSV_PROGRAM, safe="")
        + "&report_name=" + quote(report_name, safe="")
        + "&title1=" + quote(title1, safe="")
        + "&mca_pgm=PBS"
    )
