from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import ATCCode, Item, Organisation, Schedule
from services.sync.status_store import status_store

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
    atc_codes = db.execute(select(ATCCode.order_by(ATCCode.atc_code))).scalars().all()
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
    program_code: str | None = None,
    benefit_type_code: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(Item)
    if drug_name:
        query = query.where(Item.drug_name.ilike(f"%{drug_name}%"))
    if brand_name:
        query = query.where(Item.brand_name.ilike(f"%{brand_name}%"))
    if program_code:
        query = query.where(Item.program_code == program_code)
    if benefit_type_code:
        query = query.where(Item.benefit_type_code == benefit_type_code)

    items = db.execute(query.limit(50)).scalars().all()
    return templates.TemplateResponse(
        "partials/items_table.html",
        {"request": request, "items": items},
    )


@router.get("/web/stats")
def web_stats(request: Request, db: Session = Depends(get_db)):
    total_items = db.execute(select(func.count(Item.li_item_id))).scalar()
    latest_schedule = db.execute(select(Schedule.schedule_code).order_by(Schedule.effective_date.desc()).limit(1)).scalar()
    return templates.TemplateResponse(
        "partials/home_stats.html",
        {"request": request, "total_items": total_items or 0, "latest_schedule": latest_schedule or "N/A", "last_sync": "N/A"},
    )
