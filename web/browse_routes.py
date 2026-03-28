from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import ATCCode, Item, Organisation
from web.helpers import _load_psd_manifest, _psd_enabled, templates

router = APIRouter(include_in_schema=False)


@router.get("/browse")
def browse(request: Request):
    return templates.TemplateResponse("browse.html", {"request": request})


@router.get("/psd")
def psd_library(request: Request):
    if not _psd_enabled(request):
        raise HTTPException(status_code=404, detail="PSD Search is not enabled in this deployment")
    return templates.TemplateResponse(
        "psd.html",
        {
            "request": request,
            "psd_manifest": _load_psd_manifest(),
        },
    )


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
    orgs = db.execute(
        select(func.count(Item.li_item_id).label("count"), Organisation.name)
        .join(Organisation, Item.organisation_id == Organisation.organisation_id)
        .group_by(Organisation.organisation_id, Organisation.name)
        .order_by(Organisation.name)
    ).all()
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
