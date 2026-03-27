from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.deps import get_db
from services.reports import (
    items_by_atc_level as _items_by_atc_level,
    items_by_benefit_type as _items_by_benefit_type,
    items_by_program as _items_by_program,
    price_changes as _price_changes,
    restriction_changes as _restriction_changes,
)
from web.helpers import templates

router = APIRouter(include_in_schema=False)


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
