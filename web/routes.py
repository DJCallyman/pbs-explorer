from __future__ import annotations

import re as _re
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import ATCCode, Item, Indication, Organisation, PrescribingText, Schedule, SummaryOfChange
from db.models.app_setting import AppSetting
from services.sync.status_store import status_store
from services.sync.orchestrator import SyncOrchestrator
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

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


def _get_medicare_end_date(db: Session) -> str:
    """Read the medicare_stats_end_date setting from the DB, with dynamic fallback."""
    row = db.execute(
        select(AppSetting.value).where(AppSetting.key == "medicare_stats_end_date")
    ).scalar()
    if row:
        return row
    # Dynamic fallback: current month in YYYYMM format
    return datetime.now(timezone.utc).strftime("%Y%m")


@router.get("/web/settings/medicare-end-date")
def get_medicare_end_date(db: Session = Depends(get_db)):
    return {"end_date": _get_medicare_end_date(db)}


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/search")
def search(request: Request, db: Session = Depends(get_db)):
    end_date = _get_medicare_end_date(db)
    return templates.TemplateResponse("search.html", {
        "request": request,
        "medicare_end_date": end_date,
    })


@router.get("/browse")
def browse(request: Request):
    return templates.TemplateResponse("browse.html", {"request": request})


@router.get("/browse/atc")
def browse_atc(request: Request, db: Session = Depends(get_db)):
    atc_codes = db.execute(select(ATCCode).order_by(ATCCode.atc_code)).scalars().all()
    return templates.TemplateResponse(
        "partials/browse_list.html",
        {"request": request, "title": "ATC Codes", "items": atc_codes, "type": "atc"},
    )


@router.get("/browse/programs")
def browse_programs(request: Request, db: Session = Depends(get_db)):
    programs = db.execute(
        select(func.count(Item.li_item_id).label("count"), Item.program_code)
        .group_by(Item.program_code)
        .order_by(Item.program_code)
    ).all()
    return templates.TemplateResponse(
        "partials/browse_list.html",
        {"request": request, "title": "Programs", "items": programs, "type": "program"},
    )


@router.get("/browse/manufacturers")
def browse_manufacturers(request: Request, db: Session = Depends(get_db)):
    orgs = db.execute(select(func.count(Item.li_item_id).label("count"), Organisation.name).join(Organisation, Item.organisation_id == Organisation.organisation_id).group_by(Organisation.organisation_id, Organisation.name).order_by(Organisation.name)).all()
    return templates.TemplateResponse(
        "partials/browse_list.html",
        {"request": request, "title": "Manufacturers", "items": orgs, "type": "manufacturer"},
    )


@router.get("/browse/therapeutic-groups")
def browse_therapeutic_groups(request: Request, db: Session = Depends(get_db)):
    groups = db.execute(
        select(Item.therapeutic_group_id, Item.therapeutic_group_title, func.count(Item.li_item_id).label("count"))
        .where(Item.therapeutic_group_id.isnot(None))
        .group_by(Item.therapeutic_group_id, Item.therapeutic_group_title)
        .order_by(Item.therapeutic_group_title)
    ).all()
    return templates.TemplateResponse(
        "partials/browse_list.html",
        {"request": request, "title": "Therapeutic Groups", "items": groups, "type": "therapeutic_group"},
    )


@router.get("/item/{li_item_id}")
def item_detail(request: Request, li_item_id: str):
    return templates.TemplateResponse(
        "item_detail.html",
        {"request": request, "li_item_id": li_item_id},
    )


@router.get("/reports")
def reports(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})


@router.get("/reports/items-by-program")
def reports_items_by_program(request: Request, db: Session = Depends(get_db)):
    data = [{"program_code": r.get("program_code") or "(none)", "count": r["count"]} for r in _items_by_program(db)]
    columns = [{"key": "program_code", "label": "Program"}, {"key": "count", "label": "Item Count"}]
    return templates.TemplateResponse(
        "partials/report_list.html",
        {"request": request, "title": "Items by Program", "data": data, "columns": columns},
    )


@router.get("/reports/items-by-benefit-type")
def reports_items_by_benefit_type(request: Request, db: Session = Depends(get_db)):
    data = _items_by_benefit_type(db)
    columns = [{"key": "benefit_type_code", "label": "Benefit Type"}, {"key": "count", "label": "Item Count"}]
    return templates.TemplateResponse(
        "partials/report_list.html",
        {"request": request, "title": "Items by Benefit Type", "data": data, "columns": columns},
    )


@router.get("/reports/items-by-atc-level")
def reports_items_by_atc_level(request: Request, db: Session = Depends(get_db)):
    data = _items_by_atc_level(db)
    columns = [{"key": "atc_level", "label": "ATC Level"}, {"key": "count", "label": "Code Count"}]
    return templates.TemplateResponse(
        "partials/report_list.html",
        {"request": request, "title": "Items by ATC Level", "data": data, "columns": columns},
    )


@router.get("/reports/price-changes")
def reports_price_changes(request: Request, db: Session = Depends(get_db)):
    data = _price_changes(db)
    columns = [
        {"key": "pbs_code", "label": "PBS Code"},
        {"key": "drug_name", "label": "Drug"},
        {"key": "brand_name", "label": "Brand"},
        {"key": "price", "label": "Price"},
        {"key": "updated", "label": "Last Updated"},
    ]
    return templates.TemplateResponse(
        "partials/report_list.html",
        {"request": request, "title": "Price Changes", "data": data, "columns": columns},
    )


@router.get("/reports/restriction-changes")
def reports_restriction_changes(request: Request, db: Session = Depends(get_db)):
    data = _restriction_changes(db)
    columns = [
        {"key": "table", "label": "Table"},
        {"key": "change_type", "label": "Change Type"},
        {"key": "endpoint", "label": "Endpoint"},
        {"key": "from_schedule", "label": "From Schedule"},
        {"key": "to_schedule", "label": "To Schedule"},
    ]
    return templates.TemplateResponse(
        "partials/report_list.html",
        {"request": request, "title": "Restriction Changes", "data": data, "columns": columns},
    )


@router.get("/admin")
def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/web/items")
def web_items(
    request: Request,
    drug_name: str | None = None,
    brand_name: str | None = None,
    pbs_code: str | None = None,
    program_code: str | None = None,
    benefit_type_code: str | None = None,
    indication: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
):
    from db.models.relationships import (
        ItemRestrictionRelationship,
        RestrictionPrescribingTextRelationship,
    )

    query = select(Item).distinct()
    
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
    
    # Filter by indication
    if indication:
        ind_subq = (
            select(Item.pbs_code)
            .join(
                ItemRestrictionRelationship,
                Item.pbs_code == ItemRestrictionRelationship.pbs_code
            )
            .join(
                RestrictionPrescribingTextRelationship,
                ItemRestrictionRelationship.res_code == RestrictionPrescribingTextRelationship.res_code
            )
            .join(
                Indication,
                RestrictionPrescribingTextRelationship.prescribing_text_id == Indication.indication_prescribing_txt_id
            )
            .where(Indication.condition.ilike(f"%{escape_like(indication)}%"))
            .distinct()
        )
        query = query.where(Item.pbs_code.in_(ind_subq))
    
    # Filter by severity
    if severity:
        sev_subq = (
            select(Item.pbs_code)
            .join(
                ItemRestrictionRelationship,
                Item.pbs_code == ItemRestrictionRelationship.pbs_code
            )
            .join(
                RestrictionPrescribingTextRelationship,
                ItemRestrictionRelationship.res_code == RestrictionPrescribingTextRelationship.res_code
            )
            .join(
                Indication,
                RestrictionPrescribingTextRelationship.prescribing_text_id == Indication.indication_prescribing_txt_id
            )
            .where(Indication.severity.ilike(f"%{escape_like(severity)}%"))
            .distinct()
        )
        query = query.where(Item.pbs_code.in_(sev_subq))

    items = db.execute(query.limit(50)).scalars().all()

    # --- Fix N+1: batch-fetch indication data for ALL items in one query ---
    pbs_codes = [item.pbs_code for item in items if item.pbs_code]
    indication_map: dict[str, dict] = {}

    if pbs_codes:
        indication_rows = db.execute(
            select(
                ItemRestrictionRelationship.pbs_code,
                Indication.condition,
                Indication.severity,
                PrescribingText.prescribing_type,
            )
            .join(
                RestrictionPrescribingTextRelationship,
                Indication.indication_prescribing_txt_id == RestrictionPrescribingTextRelationship.prescribing_text_id,
            )
            .join(
                PrescribingText,
                RestrictionPrescribingTextRelationship.prescribing_text_id == PrescribingText.prescribing_txt_id,
            )
            .join(
                ItemRestrictionRelationship,
                RestrictionPrescribingTextRelationship.res_code == ItemRestrictionRelationship.res_code,
            )
            .where(ItemRestrictionRelationship.pbs_code.in_(pbs_codes))
            .distinct()
        ).all()

        for row in indication_rows:
            entry = indication_map.setdefault(row.pbs_code, {"conditions": [], "severities": [], "types": []})
            if row.condition and row.condition not in entry["conditions"]:
                entry["conditions"].append(row.condition)
            if row.severity and row.severity not in entry["severities"]:
                entry["severities"].append(row.severity)
            if row.prescribing_type and row.prescribing_type not in entry["types"]:
                entry["types"].append(row.prescribing_type)
    
    items_with_data = []
    for item in items:
        ind = indication_map.get(item.pbs_code, {})
        item_dict = {
            "li_item_id": item.li_item_id,
            "drug_name": item.drug_name,
            "brand_name": item.brand_name,
            "pbs_code": item.pbs_code,
            "program_code": item.program_code,
            "benefit_type_code": item.benefit_type_code,
            "determined_price": item.determined_price,
            "first_listed_date": item.first_listed_date,
            "maximum_amount": item.maximum_amount,
            "indications": "; ".join(ind.get("conditions", [])[:3]),
            "severity": "; ".join(ind.get("severities", [])[:3]),
            "prescribing_type": "; ".join(ind.get("types", [])[:3]),
        }
        items_with_data.append(item_dict)
    
    return templates.TemplateResponse(
        "partials/items_table.html",
        {"request": request, "items": items_with_data},
    )


@router.get("/web/stats")
def web_stats(request: Request, db: Session = Depends(get_db)):
    total_items = db.execute(select(func.count(Item.li_item_id))).scalar()
    latest_schedule = db.execute(select(Schedule.schedule_code).order_by(Schedule.effective_date.desc()).limit(1)).scalar()
    orchestrator = SyncOrchestrator(db)
    sync_status = orchestrator.get_sync_status()
    last_sync = sync_status.get("last_sync")
    last_sync_display = "Never"
    if last_sync and last_sync.get("at"):
        last_sync_display = last_sync["at"][:10] if "T" in last_sync["at"] else last_sync["at"]
    return templates.TemplateResponse(
        "partials/home_stats.html",
        {"request": request, "total_items": total_items or 0, "latest_schedule": latest_schedule or "N/A", "last_sync": last_sync_display},
    )


VALID_VAR = {"SERVICES", "BENEFIT"}
VALID_RPT_FMT = {"1", "2", "3", "4", "5", "6", "7", "8"}


@router.get("/web/pbs-report")
def pbs_report(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    """Generate a Medicare Statistics report URL and redirect to it."""
    if var not in VALID_VAR:
        raise HTTPException(status_code=400, detail=f"Invalid var: {var}. Must be one of {VALID_VAR}")
    if rpt_fmt not in VALID_RPT_FMT:
        raise HTTPException(status_code=400, detail=f"Invalid rpt_fmt: {rpt_fmt}. Must be one of {VALID_RPT_FMT}")

    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        raise HTTPException(status_code=400, detail="No PBS codes provided")

    start_date = resolve_start_date(db, codes, start_date)
    if not end_date:
        end_date = _get_medicare_end_date(db)

    redirect_url = build_report_url(codes, start_date, end_date, var, rpt_fmt)
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/web/pbs-report-warmup")
async def pbs_report_warmup(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    """Fire-and-forget: hit the SAS server to trigger report generation
    so the result is cached by the time the user clicks Download Excel.
    Returns 202 immediately; the actual request runs in the background.
    """
    import asyncio

    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        return Response(status_code=202)

    start_date = resolve_start_date(db, codes, start_date)
    if not end_date:
        end_date = _get_medicare_end_date(db)

    # Sanitise var / rpt_fmt – fall back to defaults for the non-critical warmup
    if var not in VALID_VAR:
        var = "SERVICES"
    if rpt_fmt not in VALID_RPT_FMT:
        rpt_fmt = "2"

    report_url = build_report_url(codes, start_date, end_date, var, rpt_fmt)

    async def _warmup():
        """Background task: hit SAS to warm the cache, ignore result."""
        async def _strip_referer(req: httpx.Request) -> None:
            if "referer" in req.headers:
                del req.headers["referer"]
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=15.0),
                event_hooks={"request": [_strip_referer]},
            ) as client:
                logger.info("[warmup] Hitting SAS to pre-generate report…")
                resp = await client.get(report_url)
                logger.info("[warmup] Done: status=%s  size=%d bytes", resp.status_code, len(resp.content))
        except Exception as exc:
            logger.debug("[warmup] Failed (non-critical): %s", exc)

    asyncio.create_task(_warmup())
    return Response(status_code=202)


@router.get("/web/pbs-report-excel")
async def pbs_report_excel(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    """Fetch the Medicare Statistics report server-side, extract the
    session-specific report_name, then proxy the Excel (CSV) download
    back to the user.  The SAS server requires a two-step flow:
      1. Render the HTML report (creates a temp file on the server).
      2. Hit the mbs_csv stored process with the temp file name.

    The SAS server can be slow on the first request (report generation)
    but caches results for subsequent requests.  We retry automatically
    to handle transient failures/timeouts.
    """
    import re
    import asyncio
    import time

    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        raise HTTPException(status_code=400, detail="No PBS codes provided")

    if var not in VALID_VAR:
        raise HTTPException(status_code=400, detail=f"Invalid var: {var}. Must be one of {VALID_VAR}")
    if rpt_fmt not in VALID_RPT_FMT:
        raise HTTPException(status_code=400, detail=f"Invalid rpt_fmt: {rpt_fmt}. Must be one of {VALID_RPT_FMT}")

    start_date = resolve_start_date(db, codes, start_date)
    if not end_date:
        end_date = _get_medicare_end_date(db)

    report_url = build_report_url(codes, start_date, end_date, var, rpt_fmt)

    async def _strip_referer(request: httpx.Request) -> None:
        if "referer" in request.headers:
            del request.headers["referer"]

    MAX_ATTEMPTS = 3
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(connect=15.0, read=20.0, write=15.0, pool=15.0),
                event_hooks={"request": [_strip_referer]},
            ) as client:
                # Step 1 – render the HTML report so the server creates the temp file
                logger.info("[attempt %d/%d] Fetching SAS HTML report…", attempt, MAX_ATTEMPTS)
                html_resp = await client.get(report_url)
                t1 = time.monotonic()
                logger.info(
                    "[attempt %d/%d] HTML response: status=%s  size=%d bytes  elapsed=%.1fs",
                    attempt, MAX_ATTEMPTS, html_resp.status_code, len(html_resp.text), t1 - t0,
                )
                html_resp.raise_for_status()

                # Extract report_name and title1 from the download form
                m = re.search(r'name=["\']report_name["\']\s+value=["\']([^"\']+)["\']', html_resp.text)
                t = re.search(r'name=["\']title1["\']\s+value=["\']([^"\']+)["\']', html_resp.text)
                if not m:
                    logger.warning(
                        "[attempt %d/%d] report_name not found. Response snippet: %s",
                        attempt, MAX_ATTEMPTS, html_resp.text[:500],
                    )
                    if attempt < MAX_ATTEMPTS:
                        logger.info("Retrying in 1 s …")
                        await asyncio.sleep(1)
                        continue
                    raise HTTPException(
                        status_code=502,
                        detail="Could not find report_name in upstream response",
                    )
                report_name = m.group(1)
                title1 = t.group(1) if t else report_name
                logger.info("[attempt %d/%d] report_name=%s", attempt, MAX_ATTEMPTS, report_name)

                # Step 2 – request the CSV/Excel download
                csv_url = build_csv_download_url(report_name, title1)
                logger.info("[attempt %d/%d] Fetching Excel file…", attempt, MAX_ATTEMPTS)
                csv_resp = await client.get(csv_url)
                t2 = time.monotonic()
                logger.info(
                    "[attempt %d/%d] Excel response: status=%s  size=%d bytes  elapsed=%.1fs  total=%.1fs",
                    attempt, MAX_ATTEMPTS, csv_resp.status_code, len(csv_resp.content), t2 - t1, t2 - t0,
                )
                csv_resp.raise_for_status()

                # Determine filename
                filename = "pbs_report.xls"
                cd = csv_resp.headers.get("content-disposition", "")
                fn_match = re.search(r'filename=["\']?([^"\'\s;]+)', cd)
                if fn_match:
                    filename = fn_match.group(1)

                return Response(
                    content=csv_resp.content,
                    media_type=csv_resp.headers.get("content-type", "text/csv"),
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )

        except httpx.HTTPError as exc:
            elapsed = time.monotonic() - t0
            logger.warning(
                "[attempt %d/%d] SAS request failed after %.1fs: %s",
                attempt, MAX_ATTEMPTS, elapsed, exc,
            )
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                logger.info("Retrying in 1 s …")
                await asyncio.sleep(1)
                continue

    # All attempts exhausted
    logger.error("All %d attempts to fetch SAS report failed", MAX_ATTEMPTS)
    raise HTTPException(
        status_code=502,
        detail=f"Failed to fetch report from Medicare Statistics after {MAX_ATTEMPTS} attempts: {last_error}",
    )
