from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.deps import get_db
from services.auth_store import list_users as list_auth_users
from services.reports import VALID_RPT_FMT, VALID_VAR, parse_pbs_codes, resolve_start_date
from web.helpers import (
    _extract_main_report_table,
    _fetch_sas_report_html,
    _normalise_report_table,
    _require_admin_request,
    _resolve_medicare_end_date_for_run,
    templates,
)

router = APIRouter(include_in_schema=False)


@router.get("/admin")
def admin(request: Request):
    _require_admin_request(request)
    return RedirectResponse(url="/admin/sync", status_code=303)


def _render_admin_page(request: Request, section: str):
    _require_admin_request(request)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "admin_section": section,
            "managed_users": list_auth_users(),
        },
    )


@router.get("/admin/sync")
def admin_sync(request: Request):
    return _render_admin_page(request, "sync")


@router.get("/admin/users")
def admin_users(request: Request):
    return _render_admin_page(request, "users")


@router.get("/web/admin/medicare-treatment-phases")
async def medicare_treatment_phases_debug(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    _require_admin_request(request)

    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        return JSONResponse({"detail": "No PBS codes provided"}, status_code=400)
    if len(codes) > 20:
        return JSONResponse(
            {"detail": "Medicare Statistics allows up to 20 item codes per report"},
            status_code=400,
        )
    if var not in VALID_VAR:
        return JSONResponse({"detail": f"Invalid var: {var}. Must be one of {VALID_VAR}"}, status_code=400)
    if rpt_fmt not in VALID_RPT_FMT:
        return JSONResponse(
            {"detail": f"Invalid rpt_fmt: {rpt_fmt}. Must be one of {VALID_RPT_FMT}"},
            status_code=400,
        )

    start_date = resolve_start_date(db, codes, start_date)
    end_date, probed_html = await _resolve_medicare_end_date_for_run(db, codes, start_date, var, rpt_fmt, end_date)
    html = probed_html or await _fetch_sas_report_html(codes, start_date, end_date, var, rpt_fmt)
    table = _extract_main_report_table(html)
    records = _normalise_report_table(table, codes, start_date, end_date, var, rpt_fmt)

    counts: dict[str, int] = {}
    sample_rows: dict[str, dict[str, str]] = {}
    for record in records:
        raw_value = str(record.get("scheme") or "").strip()
        if not raw_value:
            continue
        counts[raw_value] = counts.get(raw_value, 0) + 1
        sample_rows.setdefault(
            raw_value,
            {
                "item_code": str(record.get("item") or ""),
                "period": str(record.get("month") or record.get("financial_year") or record.get("calendar_year") or ""),
                "dimension": str(record.get("state") or record.get("patient_category") or ""),
            },
        )

    values = [
        {
            "raw_value": raw_value,
            "count": counts[raw_value],
            "sample_item_code": sample_rows.get(raw_value, {}).get("item_code", ""),
            "sample_period": sample_rows.get(raw_value, {}).get("period", ""),
            "sample_dimension": sample_rows.get(raw_value, {}).get("dimension", ""),
        }
        for raw_value in sorted(counts)
    ]

    return {
        "pbs_codes": codes,
        "start_date": start_date,
        "end_date": end_date,
        "var": var,
        "rpt_fmt": rpt_fmt,
        "raw_treatment_phases": values,
        "row_count": len(records),
    }
