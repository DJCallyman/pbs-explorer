from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode, quote

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import ATCCode, Item, Indication, Organisation, PrescribingText, Schedule
from services.sync.status_store import status_store
from services.sync.orchestrator import SyncOrchestrator

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/search")
def search(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})


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
        select(func.count(Item.li_item_id).label("count"), Item.therapeutic_group_id, Item.therapeutic_group_title)
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
    data = db.execute(
        select(func.count(Item.li_item_id).label("count"), Item.program_code)
        .group_by(Item.program_code)
        .order_by(func.count(Item.li_item_id).desc())
    ).all()
    return templates.TemplateResponse(
        "partials/report_list.html",
        {"request": request, "title": "Items by Program", "data": data},
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
        query = query.where(Item.drug_name.ilike(f"%{drug_name}%"))
    if brand_name:
        query = query.where(Item.brand_name.ilike(f"%{brand_name}%"))
    if pbs_code:
        query = query.where(Item.pbs_code.ilike(f"%{pbs_code}%"))
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
            .where(Indication.condition.ilike(f"%{indication}%"))
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
            .where(Indication.severity.ilike(f"%{severity}%"))
            .distinct()
        )
        query = query.where(Item.pbs_code.in_(sev_subq))

    items = db.execute(query.limit(50)).scalars().all()
    
    items_with_data = []
    for item in items:
        # Get indications via the proper relationship chain:
        # item -> item_restriction_relationship -> restriction_prescribing_text_relationship -> indication
        # Also join PrescribingText for prescribing_type
        from db.models.relationships import (
            ItemRestrictionRelationship,
            RestrictionPrescribingTextRelationship,
        )
        
        indication_data = db.execute(
            select(Indication.condition, Indication.severity, PrescribingText.prescribing_type)
            .join(
                RestrictionPrescribingTextRelationship,
                Indication.indication_prescribing_txt_id == RestrictionPrescribingTextRelationship.prescribing_text_id
            )
            .join(
                PrescribingText,
                RestrictionPrescribingTextRelationship.prescribing_text_id == PrescribingText.prescribing_txt_id
            )
            .join(
                ItemRestrictionRelationship,
                RestrictionPrescribingTextRelationship.res_code == ItemRestrictionRelationship.res_code
            )
            .where(ItemRestrictionRelationship.pbs_code == item.pbs_code)
            .distinct()
            .limit(3)
        ).all()
        
        conditions = [row.condition for row in indication_data if row.condition]
        severities = [row.severity for row in indication_data if row.severity]
        prescribing_types = [row.prescribing_type for row in indication_data if row.prescribing_type]
        
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
            "indications": "; ".join(conditions) if conditions else "",
            "severity": "; ".join(severities) if severities else "",
            "prescribing_type": "; ".join(prescribing_types) if prescribing_types else "",
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


@router.get("/web/pbs-report")
def pbs_report(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    """Generate a Medicare Statistics report URL and redirect to it."""
    # Parse PBS codes (comma-separated, optionally quoted)
    import re
    codes = re.findall(r"'([^']+)'", pbs_codes)
    if not codes:
        codes = pbs_codes.split(',')
    codes = [c.strip() for c in codes if c.strip()]
    
    if not codes:
        raise HTTPException(status_code=400, detail="No PBS codes provided")
    
    # Get earliest first_listed_date from items if not provided
    if not start_date:
        earliest = db.execute(
            select(func.min(Item.first_listed_date))
            .where(Item.pbs_code.in_(codes))
        ).scalar_one_or_none()
        if earliest:
            start_date = earliest.strftime("%Y%m")
        else:
            start_date = "202501"
    
    # Use provided end_date or fixed end date
    if not end_date:
        end_date = "202511"
    
    # Build the report URL - exact format matching working URL
    base_url = "https://medicarestatistics.humanservices.gov.au/SASStoredProcess/guest"
    program = "SBIP://METASERVER/Shared Data/sasdata/prod/VEA0032/SAS.StoredProcess/statistics/pbs_item_standard_report"
    
    # Format: '','code1','code2','' with leading and trailing empty quotes
    # No LIST parameter, ITEMCNT goes after itemlst
    itemlst = "''" + ",'" + "','".join(codes) + "',''"
    
    # Build URL in exact order: _PROGRAM, itemlst, ITEMCNT, VAR, RPT_FMT, start_dt, end_dt
    redirect_url = base_url + "?_PROGRAM=" + quote(program, safe='') + "&itemlst=" + itemlst + "&ITEMCNT=" + str(len(codes)) + "&VAR=SERVICES&RPT_FMT=2&start_dt=" + start_date + "&end_dt=" + end_date
    
    return RedirectResponse(url=redirect_url, status_code=302)
